import argparse
import asyncio
import os
import time
from datetime import datetime
from types import SimpleNamespace
from loguru import logger
import yaml

from database.db import init_db, get_db
from database.models import Campaign, Lead, UserPersona, APIKeys
from scraper.google_maps import extract_google_maps_leads
from scraper.website_scraper import scrape_website_html
from scraper.screenshot import capture_screenshot
from auditor.rule_engine import audit_html
from auditor.scorer import calculate_opportunity_score, format_audit_summary_for_ai
from ai.email_generator import generate_cold_email
from output.csv_writer import export_leads_to_csv
from scraper.enrichment import find_decision_maker_email

# Load Config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)
    log_dir = config.get("log_folder", "logs/")

os.makedirs(log_dir, exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
logger.add(os.path.join(log_dir, f"run_{timestamp}.log"), rotation="5 MB", level="INFO")


def make_fallback_draft(business_name: str) -> str:
    """Always returns a usable email draft even if AI fails."""
    first_name = business_name.split()[0].replace(",", "").replace(".", "") if business_name else "there"
    return f"""Subject: Quick question about your website

Hi {first_name},

I was looking at your website and spotted a few quick wins that could bring in more leads without any ad spend.

Would it be worth a quick 10-minute chat?

Best,
Faizan"""


def snapshot_persona(persona: UserPersona | None):
    """Copy persona fields before the SQLAlchemy session closes."""
    if not persona:
        return None
    return SimpleNamespace(
        name=persona.name,
        objective=persona.objective,
        resume_text=persona.resume_text or "",
        skills=persona.skills or "",
        value_proposition=persona.value_proposition or "",
    )


async def process_campaign(
    niche: str,
    location: str,
    max_leads: int,
    pre_campaign_id: int = None,
    screenshot_enabled: bool = True,
):
    runtime_start = time.time()

    logger.info("=" * 60)
    logger.info(f"STARTING CAMPAIGN: {niche} in {location}")
    logger.info("=" * 60)

    # 1. Init Database & Campaign
    init_db()

    persona = None
    hunter_api_key = ""
    if pre_campaign_id:
        campaign_id = pre_campaign_id
        logger.info(f"Using provided Campaign ID from API: {campaign_id}")
        with get_db() as db:
            camp = db.query(Campaign).filter(Campaign.id == campaign_id).first()
            if camp and camp.persona_id:
                persona = snapshot_persona(db.query(UserPersona).filter(UserPersona.id == camp.persona_id).first())
            keys = db.query(APIKeys).order_by(APIKeys.id.desc()).first()
            if keys: hunter_api_key = keys.hunter_api_key
    else:
        with get_db() as db:
            if db:
                campaign = Campaign(name=f"{niche} in {location} - {timestamp}", niche=niche, location=location)
                db.add(campaign)
                db.commit()
                db.refresh(campaign)
                campaign_id = campaign.id
                keys = db.query(APIKeys).order_by(APIKeys.id.desc()).first()
                if keys: hunter_api_key = keys.hunter_api_key
            else:
                campaign_id = None
                logger.warning("Running without PostgreSQL connection. Data won't be saved to DB.")

    # 2. Scrape Google Maps
    initial_leads = await extract_google_maps_leads(niche, location, max_leads)

    if not initial_leads:
        logger.error("No leads found. Aborting pipeline.")
        return

    enriched_leads = []
    stats = {"scraped": len(initial_leads), "audited": 0, "emails": 0, "errors": 0}

    # 3. Process Each Lead
    for idx, lead_data in enumerate(initial_leads, 1):
        try:
            name = lead_data["business_name"]
            url = lead_data["website"]
            logger.info(f"[{idx}/{len(initial_leads)}] Processing: {name}")

            if not url:
                logger.warning(f"  Skipping deep audit for {name} - No website found.")
                lead_data["status"] = "skipped"
                enriched_leads.append(lead_data)
                continue

            # Phase 3a: Website HTML Scrape
            site_data = scrape_website_html(url)

            if site_data["blocked"]:
                logger.warning(f"  {name} blocked our scraper. Marking as site_blocked.")
                lead_data["status"] = "site_blocked"
                enriched_leads.append(lead_data)
                continue

            # Merge scraped socials and emails
            for key in ["email", "facebook", "instagram", "linkedin"]:
                if site_data.get(key): lead_data[key] = site_data[key]

            # Phase 3b: Optional Automated Screenshot
            if screenshot_enabled:
                try:
                    screenshot_path = await capture_screenshot(url, name)
                    lead_data["screenshot_path"] = screenshot_path
                except Exception as e:
                    logger.warning(f"  Screenshot failed for {name}: {e}")
                    lead_data["screenshot_path"] = None
            else:
                lead_data["screenshot_path"] = None

            # Phase 4a: Rule-based Audit
            findings = audit_html(site_data["html"], url)
            lead_data["tech_stack"] = findings["tech"]["stack"]

            # Phase 4.5: Deep Context Engine (Hunter.io Sniper)
            enriched_contact = None
            if hunter_api_key:
                try:
                    logger.info(f"  Sniping decision-makers via Hunter.io for {name}...")
                    persona_obj = persona.objective if persona else "b2b_agency"
                    enriched_contact = find_decision_maker_email(url, persona_obj, hunter_api_key)
                except Exception as e:
                    logger.warning(f"  Hunter.io failed for {name}: {e}")

            if enriched_contact:
                lead_data["email"] = enriched_contact["email"]
                lead_data["first_name"] = enriched_contact["first_name"]
                logger.info(f"  SNIPE SUCCESS: Found {enriched_contact['position']} at {enriched_contact['email']}")
            elif not lead_data.get("email") and findings.get("contact", {}).get("emails"):
                lead_data["email"] = findings["contact"]["emails"][0]

            # Phase 4b: Opportunity Scoring
            score = calculate_opportunity_score(findings, lead_data.get("review_count", 0))
            lead_data["opportunity_score"] = score
            lead_data["audit_findings"] = findings

            summary = format_audit_summary_for_ai(findings)
            lead_data["audit_findings_summary"] = summary
            stats["audited"] += 1

            # Phase 5: AI Email Generation — NEVER let this crash the lead
            draft = ""
            angle = "General Pitch"
            try:
                draft, angle = generate_cold_email(name, summary, persona, lead_data.get("first_name"))
                if draft:
                    stats["emails"] += 1
                    logger.info(f"  AI email generated successfully.")
                else:
                    logger.warning(f"  AI returned empty draft for {name}. Using fallback.")
            except Exception as e:
                logger.warning(f"  AI email generation failed for {name}: {e}. Using fallback.")

            # Always assign a draft — use fallback if AI failed
            if not draft:
                draft = make_fallback_draft(name)
                angle = "General Pitch (Fallback)"
                stats["emails"] += 1

            lead_data["email_draft"] = draft
            lead_data["pitch_angle_used"] = angle

            # *** KEY FIX: status is audited if we have email, regardless of earlier errors ***
            lead_data["status"] = "audited"
            enriched_leads.append(lead_data)
            logger.info(f"  Successfully enriched & audited {name} (Score: {score})")

        except Exception as e:
            logger.error(f"Failed processing lead {lead_data.get('business_name')}: {e}")
            stats["errors"] += 1

            # Even on error — if we have an email, generate a fallback draft and mark audited
            if lead_data.get("email"):
                lead_data["email_draft"] = make_fallback_draft(lead_data.get("business_name", "there"))
                lead_data["pitch_angle_used"] = "General Pitch (Fallback)"
                lead_data["status"] = "audited"
                logger.info(f"  Saved with fallback draft despite error.")
            else:
                lead_data["status"] = "error"

            enriched_leads.append(lead_data)

    # 4. Save to Database
    if campaign_id:
        with get_db() as db:
            for ld in enriched_leads:
                db_lead = Lead(
                    campaign_id=campaign_id,
                    business_name=ld.get("business_name"),
                    address=ld.get("address"),
                    phone=ld.get("phone"),
                    email=ld.get("email"),
                    website=ld.get("website"),
                    instagram=ld.get("instagram"),
                    facebook=ld.get("facebook"),
                    linkedin=ld.get("linkedin"),
                    rating=str(ld.get("rating", "")),
                    review_count=ld.get("review_count", 0),
                    tech_stack=ld.get("tech_stack"),
                    screenshot_path=ld.get("screenshot_path"),
                    opportunity_score=ld.get("opportunity_score", 0),
                    audit_findings=ld.get("audit_findings", {}),
                    email_draft=ld.get("email_draft"),
                    pitch_angle_used=ld.get("pitch_angle_used"),
                    status=ld.get("status")
                )
                db.add(db_lead)
            db.commit()
            logger.info("Saved all enriched leads to DB successfully.")

    # 5. Export to CSV
    export_leads_to_csv(enriched_leads)

    # 6. End Run Logging Summary
    runtime_m, runtime_s = divmod(int(time.time() - runtime_start), 60)
    logger.info("=" * 60)
    logger.info("RUN COMPLETE")
    logger.info(f"Scraped: {stats['scraped']} | Audited: {stats['audited']} | Emails: {stats['emails']} | Errors: {stats['errors']} | Runtime: {runtime_m}m {runtime_s}s")
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LeadForge AI Prospecting SaaS")
    parser.add_argument("--niche", type=str, required=True)
    parser.add_argument("--location", type=str, required=True)
    parser.add_argument("--max-leads", type=int, default=10)
    parser.add_argument("--campaign-id", type=int, default=None)
    parser.add_argument("--skip-screenshots", action="store_true")

    args = parser.parse_args()

    with open("config.yaml", "r") as f:
        conf = yaml.safe_load(f)
        max_limit = conf.get("max_leads_per_run", 50)
        final_max = min(args.max_leads, max_limit)

    asyncio.run(process_campaign(args.niche, args.location, final_max, args.campaign_id, not args.skip_screenshots))
