#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║           LeadForge AI — MCP Server                      ║
║  Exposes LeadForge tools to Claude & other LLMs          ║
║  via the Model Context Protocol (MCP)                    ║
╚══════════════════════════════════════════════════════════╝

This server lets any MCP-compatible LLM (Claude Desktop, etc.)
directly call LeadForge's scraping, auditing, and email tools.

SETUP:
  1. Make sure LeadForge backend is running: uvicorn api.server:app --port 8000
  2. Register this server in Claude Desktop's config (see claude_desktop_config.json)
  3. Claude can then call tools like: scrape_leads, get_campaign_leads, etc.
"""

import asyncio
import json
import os
import sys
from typing import Any

import httpx
from mcp.server import Server

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions
from mcp.server.stdio import stdio_server
from mcp import types

# ──────────────────────────────────────────────
#  CONFIG
# ──────────────────────────────────────────────
API_BASE = os.getenv("LEADFORGE_API_URL", "http://localhost:8000")
API_TOKEN = os.getenv("LEADFORGE_API_TOKEN", "")

app = Server("leadforge-ai")


# ──────────────────────────────────────────────
#  TOOL DEFINITIONS
# ──────────────────────────────────────────────
@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="scrape_leads",
            description=(
                "🚀 Start a new LeadForge AI campaign. Scrapes Google Maps for businesses "
                "matching the niche and location, visits each website, runs a full SEO/UX/Trust "
                "audit, detects their tech stack, scores the opportunity (0-100), and generates "
                "a personalized AI cold email for each lead. Returns a campaign_id to track progress."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "niche": {
                        "type": "string",
                        "description": "Business type to target (e.g. 'Plumbers', 'Dentists', 'Restaurants', 'Web Design Agencies')"
                    },
                    "location": {
                        "type": "string",
                        "description": "City or area to search (e.g. 'Dubai', 'Lahore', 'New York', 'London')"
                    },
                    "max_leads": {
                        "type": "integer",
                        "description": "Number of leads to scrape. Min 1, Max 50. Default: 5.",
                        "default": 5
                    },
                    "persona_id": {
                        "type": "integer",
                        "description": "Optional: ID of a saved persona to tailor the AI emails. Use list_personas to see available ones."
                    }
                },
                "required": ["niche", "location"]
            }
        ),

        types.Tool(
            name="list_campaigns",
            description="📋 List all LeadForge campaigns ever run, with their IDs, niches, locations, and creation dates.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),

        types.Tool(
            name="get_campaign_leads",
            description=(
                "🎯 Get all leads for a campaign with their opportunity scores, tech stacks, "
                "email addresses, and AI email draft status. Use this after scrape_leads finishes (~2 mins)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "campaign_id": {
                        "type": "integer",
                        "description": "The campaign ID returned by scrape_leads"
                    }
                },
                "required": ["campaign_id"]
            }
        ),

        types.Tool(
            name="get_lead_details",
            description=(
                "🔍 Get the full profile of a single lead: contact info, website audit findings, "
                "tech stack, opportunity score, social links, and the complete AI-generated cold email draft."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "lead_id": {
                        "type": "integer",
                        "description": "The lead ID (visible in get_campaign_leads results)"
                    }
                },
                "required": ["lead_id"]
            }
        ),

        types.Tool(
            name="create_persona",
            description=(
                "👤 Create a sales persona that defines WHO you are and WHAT you're selling. "
                "This persona shapes how LeadForge AI writes cold emails — whether you're a "
                "freelancer, agency owner, or job seeker."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "A label for this persona (e.g. 'Web Dev Agency', 'SEO Freelancer')"
                    },
                    "objective": {
                        "type": "string",
                        "enum": ["b2b_agency", "freelance", "job_hunt"],
                        "description": "Your outreach goal: b2b_agency (selling services), freelance (getting clients), job_hunt (finding a job)"
                    },
                    "skills": {
                        "type": "string",
                        "description": "Your skills or services (e.g. 'React, Node.js, SEO, Google Ads, Figma')"
                    },
                    "value_proposition": {
                        "type": "string",
                        "description": "Your unique pitch (e.g. 'We rebuild slow local business websites to double their Google leads in 30 days')"
                    }
                },
                "required": ["name", "objective", "skills", "value_proposition"]
            }
        ),

        types.Tool(
            name="list_personas",
            description="👤 List all saved personas with their IDs, objectives, and value propositions.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),

        types.Tool(
            name="send_campaign_emails",
            description=(
                "📨 Fire the email blast for a campaign. Sends the AI-generated cold email to every "
                "lead that has a valid email address. Uses the SMTP config saved in settings. "
                "Logs each send attempt and marks leads as 'emailed' in the database."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "campaign_id": {
                        "type": "integer",
                        "description": "The campaign ID to send emails for"
                    }
                },
                "required": ["campaign_id"]
            }
        ),

        types.Tool(
            name="export_campaign_csv",
            description=(
                "📁 Export all leads from a campaign as a CSV file. The CSV includes: business name, "
                "phone, email, website, social links, opportunity score, priority tier (High/Medium/Low), "
                "tech stack, mobile-friendly status, SEO audit results, and the full AI email draft. "
                "Returns the local file path."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "campaign_id": {
                        "type": "integer",
                        "description": "The campaign ID to export"
                    }
                },
                "required": ["campaign_id"]
            }
        ),

        types.Tool(
            name="generate_outreach_messages",
            description=(
                "📱 Generate multi-channel outreach messages (LinkedIn, WhatsApp, SMS) for all leads "
                "in a campaign. Uses the same audit data as email generation but tailors the message "
                "format and tone for each platform. LinkedIn gets a 300-char connection note + follow-up, "
                "WhatsApp gets a casual 3-sentence message, SMS gets a 160-char text. "
                "Run this AFTER a campaign is complete (leads must be audited first)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "campaign_id": {
                        "type": "integer",
                        "description": "The campaign ID to generate messages for"
                    },
                    "channels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Which channels to generate. Options: 'linkedin', 'whatsapp', 'sms'. Default: all three.",
                        "default": ["linkedin", "whatsapp", "sms"]
                    }
                },
                "required": ["campaign_id"]
            }
        ),

        types.Tool(
            name="get_lead_messages",
            description=(
                "💬 Get ALL outreach messages for a lead across every channel: Email, LinkedIn "
                "(connection note + follow-up), WhatsApp, and SMS. Perfect for reviewing and "
                "copy-pasting messages to each platform. Shows which channels have messages ready."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "lead_id": {
                        "type": "integer",
                        "description": "The lead ID to get messages for"
                    }
                },
                "required": ["lead_id"]
            }
        ),
    ]


# ──────────────────────────────────────────────
#  TOOL EXECUTION
# ──────────────────────────────────────────────
def auth_headers() -> dict:
    """Return authorization headers for API requests."""
    return {"Authorization": f"Bearer {API_TOKEN}"}


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:

            # ── scrape_leads ──────────────────────────────
            if name == "scrape_leads":
                payload = {
                    "niche": arguments["niche"],
                    "location": arguments["location"],
                    "max_leads": arguments.get("max_leads", 5),
                    "persona_id": arguments.get("persona_id")
                }
                resp = await client.post(f"{API_BASE}/api/campaigns", json=payload, headers=auth_headers())
                resp.raise_for_status()
                data = resp.json()
                return [types.TextContent(type="text", text=(
                    f"🚀 Campaign launched successfully!\n\n"
                    f"Campaign ID : {data.get('campaign_id')}\n"
                    f"Name        : {data.get('name')}\n\n"
                    f"The scraper is now running in the background — opening a browser, "
                    f"scraping Google Maps, visiting websites, running AI audits, and writing emails.\n\n"
                    f"⏱  Wait ~2-3 minutes, then call:\n"
                    f"  get_campaign_leads(campaign_id={data.get('campaign_id')})"
                ))]

            # ── list_campaigns ────────────────────────────
            elif name == "list_campaigns":
                resp = await client.get(f"{API_BASE}/api/campaigns", headers=auth_headers())
                resp.raise_for_status()
                campaigns = resp.json()
                if not campaigns:
                    return [types.TextContent(type="text", text=(
                        "No campaigns yet. Use scrape_leads to start your first one!"
                    ))]
                lines = ["📋 LeadForge Campaigns\n" + "─" * 40]
                for c in campaigns:
                    lines.append(f"  ID {c['id']:>3} │ {c['niche']:<20} │ {c['location']:<15} │ {str(c['created_at'])[:19]}")
                lines.append("─" * 40)
                lines.append(f"Total: {len(campaigns)} campaigns")
                return [types.TextContent(type="text", text="\n".join(lines))]

            # ── get_campaign_leads ────────────────────────
            elif name == "get_campaign_leads":
                campaign_id = arguments["campaign_id"]
                resp = await client.get(f"{API_BASE}/api/campaigns/{campaign_id}", headers=auth_headers())
                resp.raise_for_status()
                data = resp.json()
                campaign = data.get("campaign", {})
                leads = data.get("leads", [])

                if not leads:
                    return [types.TextContent(type="text", text=(
                        f"Campaign '{campaign.get('name')}' has no leads yet.\n"
                        f"The scraper may still be running. Try again in a minute."
                    ))]

                lines = [
                    f"🎯 Campaign: {campaign.get('name')}",
                    f"Total leads scraped: {len(leads)}\n",
                    f"{'ID':<5} {'Business':<28} {'Score':<7} {'Tech':<14} {'Status':<12} {'Email?'}",
                    "─" * 80
                ]
                for l in leads:
                    score = l.get("opportunity_score", 0)
                    emoji = "🔥" if score > 70 else ("⚡" if score > 30 else "❄️")
                    has_email = "✉️ Yes" if l.get("email_draft") else "—"
                    lines.append(
                        f"{l['id']:<5} {l['business_name'][:27]:<28} "
                        f"{emoji}{score:<5} {str(l.get('tech_stack','?'))[:13]:<14} "
                        f"{l.get('status','?')[:11]:<12} {has_email}"
                    )
                lines.append("─" * 80)
                lines.append(f"\nUse get_lead_details(lead_id=<ID>) to see full audit + email draft for any lead.")
                return [types.TextContent(type="text", text="\n".join(lines))]

            # ── get_lead_details ──────────────────────────
            elif name == "get_lead_details":
                lead_id = arguments["lead_id"]
                resp = await client.get(f"{API_BASE}/api/leads/{lead_id}", headers=auth_headers())
                resp.raise_for_status()
                l = resp.json()

                # Build the audit findings section
                audit = l.get("audit_findings", {}) or {}
                seo = audit.get("seo", {})
                ux = audit.get("ux", {})
                trust = audit.get("trust", {})

                def yn(val): return "✅ Yes" if val else "❌ No"

                text = "\n".join([
                    f"{'─'*55}",
                    f"📊 LEAD PROFILE: {l.get('business_name', 'Unknown')}",
                    f"{'─'*55}",
                    f"🌐 Website   : {l.get('website', 'N/A')}",
                    f"📞 Phone     : {l.get('phone', 'N/A')}",
                    f"📧 Email     : {l.get('email', 'N/A')}",
                    f"📍 Address   : {l.get('address', 'N/A')}",
                    f"⭐ Rating    : {l.get('rating', 'N/A')} ({l.get('review_count', 0)} reviews)",
                    f"💻 Tech Stack: {l.get('tech_stack', 'Unknown')}",
                    f"🎯 Score     : {l.get('opportunity_score', 0)}/100",
                    f"📌 Status    : {l.get('status', 'N/A')}",
                    f"",
                    f"🔗 Socials:",
                    f"   Instagram : {l.get('instagram') or '—'}",
                    f"   Facebook  : {l.get('facebook') or '—'}",
                    f"   LinkedIn  : {l.get('linkedin') or '—'}",
                    f"",
                    f"🔍 WEBSITE AUDIT:",
                    f"   SSL/HTTPS        : {yn(trust.get('has_ssl'))}",
                    f"   Mobile Viewport  : {yn(ux.get('has_viewport'))}",
                    f"   Contact Form     : {yn(trust.get('has_contact_form'))}",
                    f"   H1 Tag           : {yn(seo.get('has_h1'))}",
                    f"   Meta Description : {yn(seo.get('has_meta_desc'))}",
                    f"   Analytics Pixel  : {yn(trust.get('has_tracking_pixel'))}",
                    f"   Call-to-Action   : {yn(ux.get('has_cta'))}",
                    f"",
                    f"✉️  AI COLD EMAIL DRAFT:",
                    f"{'─'*55}",
                    l.get('email_draft') or "No email draft generated (website may have been unreachable).",
                    f"{'─'*55}",
                    f"Pitch angle used: {l.get('pitch_angle_used', 'N/A')}",
                    f"",
                    f"📱 MULTI-CHANNEL OUTREACH:",
                    f"{'─'*55}",
                    f"🔗 LinkedIn Connection Note:",
                    l.get('linkedin_connection_note') or "— Not generated yet. Use generate_outreach_messages.",
                    f"",
                    f"🔗 LinkedIn Follow-up:",
                    l.get('linkedin_followup') or "— Not generated yet.",
                    f"",
                    f"💬 WhatsApp Message:",
                    l.get('whatsapp_message') or "— Not generated yet.",
                    f"",
                    f"📱 SMS Message:",
                    l.get('sms_message') or "— Not generated yet.",
                    f"{'─'*55}",
                ])
                return [types.TextContent(type="text", text=text)]

            # ── create_persona ────────────────────────────
            elif name == "create_persona":
                payload = {
                    "name": arguments["name"],
                    "objective": arguments["objective"],
                    "skills": arguments["skills"],
                    "value_proposition": arguments["value_proposition"],
                    "resume_text": ""
                }
                resp = await client.post(f"{API_BASE}/api/personas", json=payload, headers=auth_headers())
                resp.raise_for_status()
                data = resp.json()
                return [types.TextContent(type="text", text=(
                    f"✅ Persona created!\n\n"
                    f"ID              : {data.get('id')}\n"
                    f"Name            : {data.get('name')}\n"
                    f"Objective       : {data.get('objective')}\n"
                    f"Skills          : {data.get('skills')}\n"
                    f"Value Prop      : {data.get('value_proposition')}\n\n"
                    f"Now use persona_id={data.get('id')} when calling scrape_leads."
                ))]

            # ── list_personas ─────────────────────────────
            elif name == "list_personas":
                resp = await client.get(f"{API_BASE}/api/personas", headers=auth_headers())
                resp.raise_for_status()
                personas = resp.json()
                if not personas:
                    return [types.TextContent(type="text", text=(
                        "No personas yet. Use create_persona to define your sales identity."
                    ))]
                lines = ["👤 Saved Personas\n" + "─" * 50]
                for p in personas:
                    lines.append(f"  ID {p['id']}: {p['name']} [{p['objective']}]")
                    lines.append(f"    Skills    : {p.get('skills', '—')}")
                    lines.append(f"    Value Prop: {p.get('value_proposition', '—')}")
                    lines.append("")
                return [types.TextContent(type="text", text="\n".join(lines))]

            # ── send_campaign_emails ──────────────────────
            elif name == "send_campaign_emails":
                campaign_id = arguments["campaign_id"]
                resp = await client.post(f"{API_BASE}/api/campaigns/{campaign_id}/send", headers=auth_headers())
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", {})
                return [types.TextContent(type="text", text=(
                    f"📨 Email blast complete!\n\n"
                    f"{data.get('message', '')}\n\n"
                    f"Sent successfully : {results.get('success', 0)}\n"
                    f"Failed            : {results.get('failed', 0)}\n\n"
                    f"Leads are now marked as 'emailed' in the database. "
                    f"Follow-up sequences will trigger automatically after 3 days."
                ))]

            # ── export_campaign_csv ───────────────────────
            elif name == "export_campaign_csv":
                campaign_id = arguments["campaign_id"]
                resp = await client.get(f"{API_BASE}/api/campaigns/{campaign_id}/export", headers=auth_headers())
                resp.raise_for_status()

                export_dir = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output"
                )
                os.makedirs(export_dir, exist_ok=True)
                filename = f"leadforge_campaign_{campaign_id}_mcp_export.csv"
                filepath = os.path.join(export_dir, filename)

                with open(filepath, "wb") as f:
                    f.write(resp.content)

                return [types.TextContent(type="text", text=(
                    f"✅ CSV exported!\n\n"
                    f"File saved to: {filepath}\n\n"
                    f"Columns included:\n"
                    f"  business_name, phone, email, website, address,\n"
                    f"  opportunity_score, priority_tier (High/Medium/Low),\n"
                    f"  tech_stack, mobile_friendly, has_h1, has_meta_desc,\n"
                    f"  has_contact_form, has_tracking, instagram, facebook,\n"
                    f"  linkedin, screenshot_path, email_draft, pitch_angle_used\n\n"
                    f"💡 Excel tip: Apply Conditional Formatting on 'priority_tier':\n"
                    f"   High = Green, Medium = Yellow, Low = Red"
                ))]

            # ── generate_outreach_messages ─────────────
            elif name == "generate_outreach_messages":
                campaign_id = arguments["campaign_id"]
                channels = arguments.get("channels", ["linkedin", "whatsapp", "sms"])
                payload = {"channels": channels}
                resp = await client.post(
                    f"{API_BASE}/api/campaigns/{campaign_id}/generate-messages",
                    json=payload,
                    headers=auth_headers(),
                    timeout=300.0,
                )
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", {})
                return [types.TextContent(type="text", text=(
                    f"📱 Multi-channel messages generated!\n\n"
                    f"{data.get('message', '')}\n\n"
                    f"Leads processed : {results.get('generated', 0)} / {results.get('total_leads', 0)}\n"
                    f"Channels        : {', '.join(results.get('channels', []))}\n\n"
                    f"Use get_lead_messages(lead_id=<ID>) to see all messages for a lead.\n"
                    f"Or use get_lead_details(lead_id=<ID>) for the full profile + messages."
                ))]

            # ── get_lead_messages ──────────────────────
            elif name == "get_lead_messages":
                lead_id = arguments["lead_id"]
                resp = await client.get(f"{API_BASE}/api/leads/{lead_id}/messages", headers=auth_headers())
                resp.raise_for_status()
                data = resp.json()
                channels = data.get("channels", {})

                lines = [
                    f"{'─'*55}",
                    f"💬 OUTREACH MESSAGES: {data.get('business_name', 'Unknown')}",
                    f"{'─'*55}",
                ]

                # Email
                email_ch = channels.get("email", {})
                if email_ch.get("available"):
                    lines.append(f"\n✉️  EMAIL ({email_ch.get('pitch_angle', '')}):\n")
                    lines.append(email_ch.get("message", ""))
                else:
                    lines.append("\n✉️  EMAIL: — Not available")

                # LinkedIn
                li_ch = channels.get("linkedin", {})
                if li_ch.get("available"):
                    lines.append(f"\n🔗 LINKEDIN CONNECTION NOTE ({len(li_ch.get('connection_note', ''))} chars):")
                    lines.append(li_ch.get("connection_note", ""))
                    lines.append(f"\n🔗 LINKEDIN FOLLOW-UP:")
                    lines.append(li_ch.get("followup", ""))
                else:
                    lines.append("\n🔗 LINKEDIN: — Not generated yet")

                # WhatsApp
                wa_ch = channels.get("whatsapp", {})
                if wa_ch.get("available"):
                    lines.append(f"\n💬 WHATSAPP:")
                    lines.append(wa_ch.get("message", ""))
                else:
                    lines.append("\n💬 WHATSAPP: — Not generated yet")

                # SMS
                sms_ch = channels.get("sms", {})
                if sms_ch.get("available"):
                    lines.append(f"\n📱 SMS ({len(sms_ch.get('message', ''))} chars):")
                    lines.append(sms_ch.get("message", ""))
                else:
                    lines.append("\n📱 SMS: — Not generated yet")

                lines.append(f"\n{'─'*55}")

                # Summary
                available = [ch for ch, info in channels.items() if info.get("available")]
                lines.append(f"\nChannels ready: {', '.join(available) if available else 'None'}")
                if not li_ch.get("available") or not wa_ch.get("available") or not sms_ch.get("available"):
                    lines.append("💡 Run generate_outreach_messages to create missing channel messages.")

                return [types.TextContent(type="text", text="\n".join(lines))]

            else:
                return [types.TextContent(type="text", text=f"❌ Unknown tool: '{name}'")]

        except httpx.ConnectError:
            return [types.TextContent(type="text", text=(
                f"❌ Cannot reach LeadForge API at {API_BASE}\n\n"
                f"Make sure the backend is running:\n"
                f"  cd D:\\lead-scraper-agent\n"
                f"  venv\\Scripts\\python.exe -m uvicorn api.server:app --port 8000"
            ))]
        except httpx.HTTPStatusError as e:
            return [types.TextContent(type="text", text=f"❌ API Error {e.response.status_code}: {e.response.text}")]
        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ Unexpected error: {type(e).__name__}: {str(e)}")]


# ──────────────────────────────────────────────
#  ENTRYPOINT
# ──────────────────────────────────────────────
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="leadforge-ai",
                server_version="1.0.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )

if __name__ == "__main__":
    if not API_TOKEN or API_TOKEN == "PASTE_YOUR_TOKEN_HERE":
        print(
            "WARNING: LEADFORGE_API_TOKEN is not set. All API calls will fail with 401.\n"
            "  Get your token by running: POST http://localhost:8000/api/auth/login",
            file=sys.stderr,
        )
    asyncio.run(main())

