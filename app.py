import html
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Tuple
from urllib.parse import urlparse

import gradio as gr
import requests

from ai.spam_checker import clean_spam_words
from auditor.rule_engine import audit_html
from auditor.scorer import calculate_opportunity_score, format_audit_summary_for_ai


CAMPAIGNS: List[Dict] = []
GEMINI_MODEL = "gemini-2.5-flash"
OUTSCRAPER_ENDPOINT = "https://api.outscraper.com/google-maps-search"


@dataclass
class DemoPersona:
    name: str
    objective: str
    skills: str = ""
    resume_text: str = ""
    value_proposition: str = ""


def build_persona(persona_name: str, objective: str, skills: str, value_proposition: str) -> DemoPersona:
    objective_map = {
        "B2B Agency / Sales": "b2b_agency",
        "Freelance Client Hunt": "freelance",
        "Job / Internship Search": "job_hunt",
    }
    return DemoPersona(
        name=persona_name.strip() or "LeadForge Demo Persona",
        objective=objective_map.get(objective, "b2b_agency"),
        skills=skills.strip(),
        value_proposition=value_proposition.strip() or "We fix website weaknesses to capture more leads.",
        resume_text=value_proposition.strip(),
    )


def first_present(item: Dict, keys: List[str], default=""):
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return default


def parse_review_count(value) -> int:
    if isinstance(value, int):
        return value
    if not value:
        return 0
    digits = re.sub(r"[^0-9]", "", str(value))
    return int(digits) if digits else 0


def normalize_website(url: str) -> str:
    if not url:
        return ""
    return url if url.startswith(("http://", "https://")) else f"https://{url}"


def domain_from_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(normalize_website(url))
    return parsed.netloc.replace("www.", "")


def fetch_real_leads(niche: str, location: str, max_leads: int) -> List[Dict]:
    api_key = os.getenv("OUTSCRAPER_API_KEY")
    if not api_key:
        raise gr.Error("Add OUTSCRAPER_API_KEY in Hugging Face Spaces Secrets to generate real leads.")

    query = f"{niche.strip()} in {location.strip()}"
    response = requests.get(
        OUTSCRAPER_ENDPOINT,
        headers={"X-API-KEY": api_key.strip()},
        params={
            "query": query,
            "limit": int(max_leads),
            "async": "false",
            "language": "en",
        },
        timeout=90,
    )
    response.raise_for_status()
    payload = response.json()
    raw_results = payload.get("data", payload)
    if raw_results and isinstance(raw_results[0], list):
        raw_results = raw_results[0]

    leads = []
    for item in raw_results[: int(max_leads)]:
        website = normalize_website(first_present(item, ["site", "website", "url"]))
        domain = domain_from_url(website)
        email = first_present(item, ["email", "email_1", "email_2", "email_3"])
        leads.append(
            {
                "business_name": first_present(item, ["name", "title", "business_name"], "Unknown business"),
                "address": first_present(item, ["full_address", "address", "street"]),
                "phone": first_present(item, ["phone", "phone_number"]),
                "email": email,
                "website": website,
                "rating": first_present(item, ["rating", "reviews_rating"], ""),
                "review_count": parse_review_count(first_present(item, ["reviews", "reviews_count", "review_count"], 0)),
                "facebook": first_present(item, ["facebook", "facebook_url"]),
                "instagram": first_present(item, ["instagram", "instagram_url"]),
                "linkedin": first_present(item, ["linkedin", "linkedin_url"]),
                "first_name": "",
                "source_domain": domain,
            }
        )
    if not leads:
        raise gr.Error("No real leads returned. Try a broader niche/location or check your Outscraper account.")
    return leads


def scrape_real_website_html(url: str) -> Dict:
    result = {"html": "", "email": "", "blocked": False}
    if not url:
        return result
    try:
        response = requests.get(
            normalize_website(url),
            headers={"User-Agent": "Mozilla/5.0 LeadForgeAI/1.0"},
            timeout=12,
        )
        result["blocked"] = response.status_code in {401, 403, 429}
        if response.ok:
            result["html"] = response.text
            emails = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", response.text)
            result["email"] = emails[0].lower() if emails else ""
    except requests.RequestException:
        pass
    return result


def generate_gemini_email(
    business_name: str,
    weaknesses_summary: str,
    persona: DemoPersona,
    provided_first_name: str,
) -> Tuple[str, str]:
    if not weaknesses_summary or "surprisingly healthy" in weaknesses_summary.lower():
        return "", "No significant weaknesses found to construct pitch."

    first_name = provided_first_name or business_name.split()[0].replace(",", "").replace(".", "")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "", "Missing GEMINI_API_KEY"

    if persona.objective == "job_hunt":
        angle_name = "Career Alignment Pitch"
        copywriter_rule = f"Pitch yourself for a job/internship. Mention your skills: {persona.skills}."
        cta = "Would you be open to a quick chat about potentially joining your team?"
    elif persona.objective == "freelance":
        angle_name = "Freelance Expert Pitch"
        copywriter_rule = f"Pitch your freelance services based on these skills: {persona.skills}. Your value proposition: {persona.value_proposition}."
        cta = "Are you open to having a quick chat to see if I can help out as a freelancer?"
    else:
        angle_name = "Website Opportunity Pitch"
        copywriter_rule = f"Pitch them B2B services. Your value prop is: {persona.value_proposition}"
        cta = "Would it be worth a quick 10-minute chat?"

    prompt = f"""
You are a professional copywriter sending a cold email to {first_name}.
Your goal is to get a reply. Keep it extremely short, maximum 5 sentences.

CRITICAL RULES:
1. The first line must be exactly "Subject: [Your Subject Here]".
2. The second line should be the greeting and must address {first_name}.
3. End exactly with this soft CTA: "{cta}"
4. {copywriter_rule}
5. Pitch angle to use: {angle_name}

Write the email using these exact findings about their website/business:
{weaknesses_summary}
"""

    try:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
        response = requests.post(
            endpoint,
            params={"key": api_key.strip()},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=45,
        )
        response.raise_for_status()
        data = response.json()
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts)
        draft = clean_spam_words(text).strip()
        return draft, angle_name if draft else "Failed to generate email."
    except Exception as exc:
        return f"AI Error: {exc}", angle_name


def run_demo(
    niche: str,
    location: str,
    persona_name: str,
    objective: str,
    skills: str,
    value_proposition: str,
    max_leads: int,
) -> Tuple[List[List], str, str]:
    if not niche.strip() or not location.strip():
        raise gr.Error("Please enter both a niche and location.")

    persona = build_persona(persona_name, objective, skills, value_proposition)
    leads = fetch_real_leads(niche, location, int(max_leads))
    enriched = []

    for lead in leads:
        site_data = scrape_real_website_html(lead["website"])
        html_content = site_data["html"]
        if site_data["email"] and not lead.get("email"):
            lead["email"] = site_data["email"]
        findings = audit_html(html_content, lead["website"])
        score = calculate_opportunity_score(findings, lead["review_count"])
        summary = format_audit_summary_for_ai(findings)
        draft, angle = generate_gemini_email(
            lead["business_name"],
            summary,
            persona,
            lead.get("first_name"),
        )
        lead.update(
            {
                "tech_stack": findings["tech"]["stack"],
                "opportunity_score": score,
                "audit_findings": findings,
                "audit_findings_summary": summary,
                "email_draft": draft or "Email generation failed. Add GEMINI_API_KEY in HF Spaces Secrets.",
                "pitch_angle_used": angle,
                "status": "audited",
            }
        )
        enriched.append(lead)

    enriched.sort(key=lambda item: item.get("opportunity_score", 0), reverse=True)
    CAMPAIGNS.append(
        {
            "created_at": datetime.utcnow().isoformat(timespec="seconds"),
            "niche": niche,
            "location": location,
            "persona": persona.name,
            "leads": enriched,
        }
    )

    table = [
        [
            lead["business_name"],
            lead["address"],
            lead["phone"],
            lead["email"],
            lead["website"],
            lead["rating"],
            lead["review_count"],
            lead["tech_stack"],
            lead["opportunity_score"],
            lead["pitch_angle_used"],
        ]
        for lead in enriched
    ]

    first_email = enriched[0]["email_draft"] if enriched else ""
    details = render_lead_cards(enriched)
    return table, details, first_email


def render_lead_cards(leads: List[Dict]) -> str:
    cards = []
    for lead in leads:
        summary = html.escape(lead["audit_findings_summary"]).replace("\n", "<br>")
        email_draft = html.escape(lead["email_draft"]).replace("\n", "<br>")
        cards.append(
            f"""
            <section class="lead-card">
              <div class="lead-head">
                <div>
                  <h3>{html.escape(lead['business_name'])}</h3>
                  <p>{html.escape(lead['website'])}</p>
                </div>
                <strong>{lead['opportunity_score']}/100</strong>
              </div>
              <p><b>Audit findings</b><br>{summary}</p>
              <p><b>AI outreach draft</b><br>{email_draft}</p>
            </section>
            """
        )
    return "\n".join(cards)


CSS = """
.gradio-container { max-width: 1180px !important; margin: auto; }
.lead-card {
  border: 1px solid #dbeafe;
  border-radius: 8px;
  padding: 16px;
  margin: 12px 0;
  background: #ffffff;
}
.lead-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.lead-head h3 { margin: 0 0 4px 0; }
.lead-head p { margin: 0; color: #475569; }
.lead-head strong {
  background: #1d4ed8;
  color: white;
  border-radius: 6px;
  padding: 6px 10px;
  white-space: nowrap;
}
"""


with gr.Blocks(title="LeadForge AI", css=CSS) as demo:
    gr.Markdown(
        """
        # LeadForge AI
        Autonomous B2B lead generation using real Google Maps business data, the LeadForge audit engine, and Gemini-powered outreach generation.
        """
    )

    with gr.Row():
        with gr.Column(scale=1):
            niche = gr.Textbox(label="Target niche", value="Dentists")
            location = gr.Textbox(label="Location", value="Austin, TX")
            persona_name = gr.Textbox(label="Persona name", value="Growth Agency Owner")
            objective = gr.Dropdown(
                label="Persona objective",
                choices=["B2B Agency / Sales", "Freelance Client Hunt", "Job / Internship Search"],
                value="B2B Agency / Sales",
            )
            skills = gr.Textbox(label="Skills or services", value="SEO, conversion design, local business websites")
            value_proposition = gr.Textbox(
                label="Value proposition / resume context",
                value="We rebuild underperforming local business websites so more visitors turn into booked calls.",
                lines=3,
            )
            max_leads = gr.Slider(label="Real leads", minimum=1, maximum=20, value=5, step=1)
            run_button = gr.Button("Generate LeadForge Campaign", variant="primary")

        with gr.Column(scale=2):
            lead_table = gr.Dataframe(
                label="Realistic lead list",
                headers=[
                    "Business Name",
                    "Location",
                    "Phone",
                    "Email",
                    "Website",
                    "Rating",
                    "Reviews",
                    "Tech Stack",
                    "Opportunity Score",
                    "Pitch Angle",
                ],
                wrap=True,
            )
            first_email = gr.Textbox(label="Top lead AI email", lines=10)

    lead_details = gr.HTML(label="Lead audit and outreach details")

    run_button.click(
        run_demo,
        inputs=[niche, location, persona_name, objective, skills, value_proposition, max_leads],
        outputs=[lead_table, lead_details, first_email],
    )


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.getenv("PORT", "7860")),
    )
