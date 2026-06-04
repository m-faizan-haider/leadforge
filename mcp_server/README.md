# LeadForge AI — MCP Server

## What is this?

This is a **Model Context Protocol (MCP) server** for LeadForge AI. It exposes LeadForge's
lead generation tools directly to Claude Desktop (and any other MCP-compatible LLM),
so you can run full scraping campaigns, read audit results, and send cold emails
just by talking to Claude — no UI required.

---

## Available Tools (what Claude can call)

| Tool | What it does |
|---|---|
| `scrape_leads` | Start a scraping campaign on Google Maps |
| `list_campaigns` | See all past campaigns |
| `get_campaign_leads` | Get all leads + scores for a campaign |
| `get_lead_details` | Full audit + AI email for one lead |
| `create_persona` | Set up your sales persona |
| `list_personas` | List saved personas |
| `send_campaign_emails` | Fire the email blast |
| `export_campaign_csv` | Download leads as CSV |

---

## Setup (4 Steps)

### Step 1 — Make sure LeadForge Backend is running
```powershell
cd D:\lead-scraper-agent
.\start.bat
```
Or manually:
```powershell
venv\Scripts\python.exe -m uvicorn api.server:app --port 8000
```

### Step 2 — Get your API token
Run this in PowerShell:
```powershell
Invoke-RestMethod -Uri http://localhost:8000/api/auth/login -Method POST `
  -ContentType 'application/json' `
  -Body '{"email": "your@email.com", "password": "yourpassword"}'
```
Copy the `token` value from the response and paste it into
`claude_desktop_config.json` under `LEADFORGE_API_TOKEN`.

### Step 3 — Register with Claude Desktop
Copy the config to Claude Desktop's config directory:
```
%APPDATA%\Claude\claude_desktop_config.json
```
```powershell
Copy-Item "claude_desktop_config.json" "$env:APPDATA\Claude\claude_desktop_config.json" -Force
```

### Step 4 — Restart Claude Desktop
Fully quit and reopen Claude Desktop. You will see a hammer icon (🔨)
in the chat input box — that means LeadForge tools are connected!

---

## Example Conversation with Claude Desktop

```
You: Create a persona for me — I'm a web dev freelancer. My skills are React,
     Next.js, and SEO. My value prop is: "I rebuild outdated local business
     websites in 2 weeks for a flat fee."

Claude: [calls create_persona] ✅ Persona created! ID: 1

You: Now scrape 5 plumbers in Dubai using persona 1.

Claude: [calls scrape_leads] 🚀 Campaign launched! ID: 3. Check back in 2 mins.

You: Show me the leads now.

Claude: [calls get_campaign_leads] 🎯 Campaign: Plumbers in Dubai...
        🔥 Al Madina Plumbing (Score: 85/100) — email draft ready
        ⚡ Fix-It Fast Services (Score: 45/100) — email draft ready
        ...

You: Generate LinkedIn and WhatsApp messages for campaign 3.

Claude: [calls generate_outreach_messages] 📱 Multi-channel messages generated!
        Leads processed: 5/5, Channels: linkedin, whatsapp

You: Show me all messages for lead 12.

Claude: [calls get_lead_messages]
        ✉️  EMAIL: Subject: Quick question about your website...
        🔗 LINKEDIN: Hi Ahmed — great reviews on Google Maps...
        💬 WHATSAPP: Hi Ahmed 👋 Your plumbing business has solid reviews...
        📱 SMS: Hi Ahmed, your site isn't mobile-friendly. Reply YES for free audit.

You: Send the emails for campaign 3.

Claude: [calls send_campaign_emails] 📨 Sent to 4 leads successfully!
```

---

## For the Loom Recording

**Script to follow:**
1. Open VS Code → show the project folder structure
2. Show `mcp_server/server.py` — explain: *"This is how I wire my AI directly into my product"*
3. Open Claude Desktop → show the hammer icon proving MCP is connected
4. Type: *"List my campaigns"* → Claude calls the API live
5. Type: *"Scrape 3 dentists in London"* → watch it launch
6. Explain: *"Every tool here talks to a FastAPI backend that uses Playwright + Groq AI"*

This demonstrates:
- **File Setup**: Modular Python project (scraper/, ai/, api/, mcp_server/)
- **Agents**: The main.py orchestration pipeline is an autonomous agent
- **MCPs**: Live demo of Claude calling real tools via MCP protocol
