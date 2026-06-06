
# LeadForge AI

LeadForge AI is an AI-powered local business prospecting system. It finds businesses from Google Maps data, audits their websites for missed conversion opportunities, scores each lead, and generates personalized cold outreach emails from the audit findings.

The project is built as a production-oriented SaaS prototype with a FastAPI backend, Next.js dashboard, hosted PostgreSQL support, login/signup, SerpAPI lead sourcing, optional website screenshots, CSV exports, and SMTP sequence tooling.

## Live Demo

(https://leadforge-bice.vercel.app/)

Backend health check: `/health`

## Screenshots

Add screenshots here before publishing the portfolio:

- Dashboard campaign list
- New campaign form
- Campaign lead table
- AI email modal
- Settings page
- CSV export preview

## Core Features

- User signup and login with bearer-token authentication
- Google Maps lead sourcing through SerpAPI
- Playwright fallback scraper for local/manual fallback mode
- Website HTML scraping and contact/social extraction
- Rule-based website audit for SEO, mobile UX, trust, analytics, and tech stack
- Opportunity scoring from 0 to 100
- Persona-based AI cold email generation
- Optional website screenshot capture per campaign
- Hosted PostgreSQL support through `DATABASE_URL`
- CSV export with campaign summary and Excel-friendly UTF-8 encoding
- SMTP campaign sending and follow-up sequence support
- `/health` endpoint for API, database, and SerpAPI status

## Tech Stack

Backend:

- Python 3.10
- FastAPI
- Uvicorn
- SQLAlchemy
- PostgreSQL / Neon
- Playwright
- playwright-stealth
- SerpAPI
- BeautifulSoup
- curl_cffi
- pandas
- loguru
- python-dotenv
- PyYAML

AI and APIs:

- Groq API
- Ollama fallback
- Hunter.io enrichment hook
- SerpAPI Google Maps API
- SMTP email providers

Frontend:

- Next.js
- React
- TypeScript
- ESLint

Infrastructure:

- Docker
- Docker Compose
- Hosted PostgreSQL-ready configuration

## Workflow

1. User signs up or logs in.
2. User creates an outreach persona.
3. User launches a campaign with niche, location, lead count, and optional screenshots.
4. Backend fetches Google Maps leads through SerpAPI.
5. Each lead website is fetched and audited.
6. Lead score is calculated from website weaknesses.
7. AI generates a personalized cold email.
8. Leads are saved to PostgreSQL.
9. User reviews leads, downloads CSV, or starts an email sequence.

## Local Setup

Clone the project:

```bash
git clone <your-repo-url>
cd lead-scraper-agent
```

Create a Python virtual environment:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

Install frontend dependencies:

```bash
cd frontend
npm install
cd ..
```

Create `.env` from the template:

```bash
copy .env.example .env
```

For local development with hosted Neon PostgreSQL, set:

```env
APP_ENV=development
DATABASE_URL="postgresql://USER:PASSWORD@HOST/neondb?sslmode=require&channel_binding=require"
AUTH_SECRET=replace_with_a_long_random_secret
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
SCRAPER_MODE=serpapi
SERPAPI_KEY=your_serpapi_key
REQUIRE_SERPAPI=false
GROQ_API_KEY=your_groq_api_key
SIMULATE_EMAIL=True
```

Start the app:

```bash
start.bat
```

Frontend:

```text
http://localhost:3000
```

Backend docs:

```text
http://127.0.0.1:8000/docs
```

Health check:

```text
http://127.0.0.1:8000/health
```

## Docker Setup

Create `.env`, then run:

```bash
docker compose up --build
```

This starts:

- FastAPI backend on port `8000`
- PostgreSQL container on port `5432`

For a fully local Docker database, use:

```env
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/leadforge
```

For production, use hosted PostgreSQL instead of the local Docker database.

## Production Deployment

Recommended beginner-friendly deployment:

- Database: Neon PostgreSQL
- Backend: Render, Railway, Fly.io, or VPS Docker deployment
- Frontend: Vercel

Backend production env example:

```env
APP_ENV=production
DATABASE_URL="postgresql://USER:PASSWORD@HOST/neondb?sslmode=require&channel_binding=require"
AUTH_SECRET=use_a_long_random_secret
ALLOWED_ORIGINS=https://your-frontend-domain.com
SCRAPER_MODE=serpapi
SERPAPI_KEY=your_serpapi_key
REQUIRE_SERPAPI=true
GROQ_API_KEY=your_groq_api_key
SIMULATE_EMAIL=True
```

Frontend production env:

```env
NEXT_PUBLIC_API_URL=https://your-backend-domain.com
```

## Important Security Notes

- Do not commit `.env`.
- Rotate any API key or database password that was shared publicly.
- Use hosted PostgreSQL for production.
- Use a strong `AUTH_SECRET`.
- Keep `SIMULATE_EMAIL=True` until SMTP compliance is ready.
- Add unsubscribe and suppression-list support before real cold email campaigns.

## Current Limitations

- Authentication is implemented, but true multi-tenant data isolation is still a future upgrade.
- Database schema is created with SQLAlchemy `create_all`; Alembic migrations should be added before serious production use.
- SMTP sending exists, but deliverability, unsubscribe, bounce handling, and compliance tooling need hardening.
- Playwright fallback scraping can still be blocked by websites or Google UI changes.
- Website screenshots are optional because many sites are slow or block browser automation.

## Roadmap

- Add Alembic migrations
- Add user-owned campaigns, personas, leads, SMTP settings, and API keys
- Add unsubscribe and suppression list
- Add email verification and bounce handling
- Add campaign analytics dashboard
- Add deployment guide for Render/Railway/Vercel
- Add automated tests for backend routes and scoring logic

## License

MIT
