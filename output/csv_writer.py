import os
import pandas as pd
from datetime import datetime
from loguru import logger


def build_campaign_summary(leads: list) -> dict:
    total = len(leads)
    scores = [int(lead.get("opportunity_score") or 0) for lead in leads]
    statuses = [str(lead.get("status") or "") for lead in leads]
    return {
        "total_leads_found": total,
        "average_opportunity_score": round(sum(scores) / total, 2) if total else 0,
        "leads_with_emails": sum(1 for lead in leads if lead.get("email")),
        "emails_generated": sum(1 for lead in leads if lead.get("email_draft")),
        "audited_leads": sum(1 for status in statuses if status == "audited"),
        "skipped_or_blocked_leads": sum(1 for status in statuses if status in {"skipped", "site_blocked"}),
    }


def export_leads_to_csv(leads: list, output_dir: str = "output/"):
    """
    Takes a list of structured Lead dictionaries and exports them 
    to a precisely formatted CSV using Pandas.
    """
    if not leads:
        logger.warning("No leads to export.")
        return
        
    os.makedirs(output_dir, exist_ok=True)
    
    # Required strict ordering as per user prompt:
    columns_order = [
         "business_name", "address", "phone", "email", "website", 
         "instagram", "facebook", "linkedin", "rating", "review_count", 
         "tech_stack", "opportunity_score", "priority_tier", "https_missing", 
         "mobile_friendly", "has_h1", "has_meta_desc", "has_contact_form",
         "has_tracking", "screenshot_path", "email_draft", "pitch_angle_used", 
         "audit_findings_summary", "status"
    ]
    
    df_data = []
    
    for lead in leads:
        # Extract boolean states mathematically so they are clean Yes/No
        audit = lead.get("audit_findings", {})
        trust = audit.get("trust", {})
        ux = audit.get("ux", {})
        seo = audit.get("seo", {})
        
        score = lead.get("opportunity_score", 0)
        priority = "High" if score > 70 else ("Medium" if score > 30 else "Low")
        
        row = {
            "business_name": lead.get("business_name", ""),
            "address": lead.get("address", ""),
            "phone": lead.get("phone", ""),
            "email": lead.get("email", ""),
            "website": lead.get("website", ""),
            "instagram": lead.get("instagram", ""),
            "facebook": lead.get("facebook", ""),
            "linkedin": lead.get("linkedin", ""),
            "rating": lead.get("rating", ""),
            "review_count": lead.get("review_count", 0),
            "tech_stack": lead.get("tech_stack", ""),
            "opportunity_score": score,
            "priority_tier": priority,  # Added for color-coding in Excel
            "https_missing": "No" if trust.get("has_ssl", True) else "Yes",
            "mobile_friendly": "Yes" if ux.get("has_viewport", False) else "No",
            "has_h1": "Yes" if seo.get("has_h1", False) else "No",
            "has_meta_desc": "Yes" if seo.get("has_meta_desc", False) else "No",
            "has_contact_form": "Yes" if trust.get("has_contact_form", False) else "No",
            "has_tracking": "Yes" if trust.get("has_tracking_pixel", False) else "No",
            "screenshot_path": lead.get("screenshot_path", ""),
            "email_draft": lead.get("email_draft", ""),
            "pitch_angle_used": lead.get("pitch_angle_used", ""),
            "audit_findings_summary": lead.get("audit_findings_summary", ""),
            "status": lead.get("status", "new")
        }
        df_data.append(row)
        
    df = pd.DataFrame(df_data)
    
    # Reorder columns and sort by opportunity_score descending
    df = df.reindex(columns=columns_order)
    df = df.sort_values(by="opportunity_score", ascending=False)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(output_dir, f"leadforge_export_{timestamp}.csv")
    
    summary = build_campaign_summary(leads)
    with open(filename, "w", encoding="utf-8-sig", newline="") as f:
        f.write("Campaign Summary\n")
        for key, value in summary.items():
            f.write(f"{key},{value}\n")
        f.write("\nLead Details\n")
        df.to_csv(f, index=False)

    logger.info(f"Successfully exported {len(df)} leads to {filename}")
    logger.info("Excel Tip: Map Conditional Formatting on 'priority_tier' column (High=Green, Medium=Yellow, Low=Red)")
