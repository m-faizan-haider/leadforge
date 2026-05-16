from contextlib import asynccontextmanager, suppress
import base64
import hashlib
import hmac
import json
import secrets
import time

import requests
from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
import asyncio
import sys
from loguru import logger

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
import io
import csv
from fastapi.responses import StreamingResponse

from config import settings
from database.db import engine, init_db, SessionLocal
from database.models import AppUser, Campaign, Lead, SMTPConfig, EmailLog, UserPersona, APIKeys
from output.smtp_sender import send_email_blast
from output.csv_writer import build_campaign_summary
from ai.email_generator import generate_followup_email
from main import process_campaign

MASKED_SECRET = "********"
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7


def parse_allowed_origins() -> list[str]:
    return settings.allowed_origins


def mask_secret(value: str | None) -> str:
    return MASKED_SECRET if value else ""


def get_auth_secret() -> str:
    return settings.auth_secret


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    return f"pbkdf2_sha256$200000${salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations))
        return hmac.compare_digest(digest.hex(), expected)
    except Exception:
        return False


def encode_token(payload: dict) -> str:
    body = dict(payload)
    body["exp"] = int(time.time()) + TOKEN_TTL_SECONDS
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    signature = hmac.new(get_auth_secret().encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def decode_token(token: str) -> dict:
    try:
        encoded, signature = token.split(".", 1)
        expected = hmac.new(get_auth_secret().encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Bad token signature")
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("Token expired")
        return payload
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token") from exc

def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db_session),
) -> AppUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    payload = decode_token(authorization.removeprefix("Bearer ").strip())
    user = db.query(AppUser).filter(AppUser.id == payload.get("sub"), AppUser.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    sequence_task = asyncio.create_task(background_sequence_worker())
    try:
        yield
    finally:
        sequence_task.cancel()
        with suppress(asyncio.CancelledError):
            await sequence_task


app = FastAPI(title="LeadForge API SaaS", lifespan=lifespan)

# Allow Frontend to hit the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_allowed_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CampaignRequest(BaseModel):
    niche: str
    location: str
    max_leads: int = 10
    persona_id: int = None
    screenshot_enabled: bool = True

class AuthRequest(BaseModel):
    email: str
    password: str

class PersonaRequest(BaseModel):
    name: str
    objective: str
    resume_text: str = ""
    skills: str = ""
    value_proposition: str = ""

class SMTPConfigRequest(BaseModel):
    host: str
    port: int
    username: str
    password: str

class APIKeysRequest(BaseModel):
    hunter_api_key: str

def advance_campaign_sequence(campaign_id: int, db: Session, smtp_config: dict, force: bool = False):
    leads = db.query(Lead).filter(Lead.campaign_id == campaign_id, Lead.status == 'emailed').all()
    results = {"advanced": 0, "errors": 0}
    for lead in leads:
        last_log = db.query(EmailLog).filter(EmailLog.lead_id == lead.id).order_by(EmailLog.step_number.desc()).first()
        if not last_log or last_log.status != "emailed":
            continue
            
        now = datetime.utcnow()
        days_since_sent = (now - last_log.sent_at).days
        # Override for testing: pretend days passed if testing
        if force:
             days_since_sent += 5
             
        next_step = 0
        if last_log.step_number == 1 and days_since_sent >= 3:
            next_step = 2
        elif last_log.step_number == 2 and days_since_sent >= 4:
            next_step = 3
            
        if next_step > 0:
            logger.info(f"Advancing Lead {lead.id} to sequence step {next_step}...")
            draft = generate_followup_email(lead.business_name, next_step, lead.email_draft)
            if not draft: continue
            lead_dict = [{"id": lead.id, "business_name": lead.business_name, "email": lead.email, "email_draft": draft}]
            try:
                blast_res = send_email_blast(lead_dict, smtp_config=smtp_config)
                for detail in blast_res.get("details", []):
                    status = detail["status"]
                    db.add(EmailLog(lead_id=lead.id, campaign_id=campaign_id, step_number=next_step, status=status, error_message=detail.get("reason", "")))
                    if status == "emailed":
                        results["advanced"] += 1
            except Exception as e:
                logger.error(f"Sequence Error: {e}")
                results["errors"] += 1
    db.commit()
    return results

def advance_all_sequences(db: Session):
    config = db.query(SMTPConfig).order_by(SMTPConfig.id.desc()).first()
    if not config or not config.username: return
    smtp_config = {"host": config.host, "port": config.port, "username": config.username, "password": config.password}
    for camp in db.query(Campaign).all():
        try:
             advance_campaign_sequence(camp.id, db, smtp_config)
        except Exception as e:
             logger.error(f"Error testing campaign {camp.id}: {e}")

async def background_sequence_worker():
    """Endless loop that checks for daily sequences."""
    while True:
        try:
            logger.info("Running Automatic Sequence Worker...")
            db = SessionLocal()
            try:
                advance_all_sequences(db)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Sequence worker error: {e}")
        await asyncio.sleep(3600)


def update_campaign_status(campaign_id: int, status: str):
    db = SessionLocal()
    try:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if campaign:
            campaign.status = status
            db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to update campaign {campaign_id} status to {status}: {exc}")
    finally:
        db.close()


def run_campaign_background(niche: str, location: str, max_leads: int, campaign_id: int, screenshot_enabled: bool):
    update_campaign_status(campaign_id, "running")
    try:
        asyncio.run(process_campaign(niche, location, max_leads, campaign_id, screenshot_enabled))
        update_campaign_status(campaign_id, "completed")
    except Exception as exc:
        logger.exception(f"Campaign {campaign_id} failed in background task: {exc}")
        update_campaign_status(campaign_id, "failed")


def auth_response(user: AppUser) -> dict:
    return {
        "token": encode_token({"sub": user.id, "email": user.email}),
        "user": {"id": user.id, "email": user.email},
    }


def check_database_health() -> dict:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        logger.warning(f"Database health check failed: {exc}")
        return {"status": "error", "detail": str(exc)}


def check_serpapi_usage() -> dict:
    if settings.scraper_mode != "serpapi":
        return {"enabled": False, "reason": "SCRAPER_MODE is not serpapi"}
    if not settings.serpapi_key:
        return {"enabled": True, "status": "missing_key"}

    try:
        response = requests.get(
            "https://serpapi.com/account.json",
            params={"api_key": settings.serpapi_key},
            timeout=8,
        )
        response.raise_for_status()
        data = response.json()
        return {
            "enabled": True,
            "status": "ok",
            "total_searches_left": data.get("total_searches_left"),
            "plan_searches_left": data.get("plan_searches_left"),
            "this_month_usage": data.get("this_month_usage"),
            "account_rate_limit_per_hour": data.get("account_rate_limit_per_hour"),
        }
    except Exception as exc:
        logger.warning(f"SerpAPI account health check failed: {exc}")
        return {"enabled": True, "status": "error", "detail": str(exc)}


@app.get("/health")
def health():
    database = check_database_health()
    serpapi = check_serpapi_usage()
    return {
        "api": {"status": "ok", "environment": settings.app_env},
        "database": database,
        "scraper": {
            "mode": settings.scraper_mode,
            "serpapi": serpapi,
        },
    }


@app.post("/api/auth/signup")
def signup(req: AuthRequest, db: Session = Depends(get_db_session)):
    email = req.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email is required")
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    existing = db.query(AppUser).filter(AppUser.email == email).first()
    if existing:
        raise HTTPException(status_code=409, detail="An account already exists for this email")
    user = AppUser(email=email, password_hash=hash_password(req.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return auth_response(user)


@app.post("/api/auth/login")
def login(req: AuthRequest, db: Session = Depends(get_db_session)):
    email = req.email.strip().lower()
    user = db.query(AppUser).filter(AppUser.email == email, AppUser.is_active == True).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return auth_response(user)


@app.get("/api/auth/me")
def auth_me(current_user: AppUser = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email}

@app.get("/api/personas")
def list_personas(db: Session = Depends(get_db_session), current_user: AppUser = Depends(get_current_user)):
    return db.query(UserPersona).all()

@app.post("/api/personas")
def create_persona(req: PersonaRequest, db: Session = Depends(get_db_session), current_user: AppUser = Depends(get_current_user)):
    persona = UserPersona(
        name=req.name,
        objective=req.objective,
        resume_text=req.resume_text,
        skills=req.skills,
        value_proposition=req.value_proposition
    )
    db.add(persona)
    db.commit()
    db.refresh(persona)
    return persona

@app.post("/api/campaigns")
def create_campaign(
    req: CampaignRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
    current_user: AppUser = Depends(get_current_user),
):
    # 1. Instantly create the database record
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"{req.niche} in {req.location} - {timestamp}"
    
    new_campaign = Campaign(name=name, niche=req.niche, location=req.location, persona_id=req.persona_id, status="queued")
    db.add(new_campaign)
    db.commit()
    db.refresh(new_campaign)
    
    background_tasks.add_task(
        run_campaign_background,
        req.niche,
        req.location,
        req.max_leads,
        new_campaign.id,
        req.screenshot_enabled,
    )
    
    return {"message": "Campaign queued successfully", "campaign_id": new_campaign.id, "name": new_campaign.name}

@app.get("/api/settings/smtp")
def get_smtp_config(db: Session = Depends(get_db_session), current_user: AppUser = Depends(get_current_user)):
    config = db.query(SMTPConfig).order_by(SMTPConfig.id.desc()).first()
    if config:
        return {
            "host": config.host or "smtp.gmail.com",
            "port": config.port or 587,
            "username": config.username or "",
            "password": mask_secret(config.password),
            "smtp_password": mask_secret(config.password),
            "is_active": config.is_active
        }
    return {"host": "smtp.gmail.com", "port": 587, "username": "", "password": "", "smtp_password": ""}

@app.post("/api/settings/smtp")
def save_smtp_config(req: SMTPConfigRequest, db: Session = Depends(get_db_session), current_user: AppUser = Depends(get_current_user)):
    config = db.query(SMTPConfig).order_by(SMTPConfig.id.desc()).first()
    if not config:
        config = SMTPConfig()
        db.add(config)
    config.host = req.host
    config.port = req.port
    config.username = req.username
    if req.password != MASKED_SECRET:
        config.password = req.password
    db.commit()
    return {"message": "SMTP configuration saved"}

@app.get("/api/settings/keys")
def get_api_keys(db: Session = Depends(get_db_session), current_user: AppUser = Depends(get_current_user)):
    keys = db.query(APIKeys).order_by(APIKeys.id.desc()).first()
    if keys:
        return {
            "hunter_api_key": mask_secret(keys.hunter_api_key),
            "hunter_api_key_configured": bool(keys.hunter_api_key),
        }
    return {"hunter_api_key": "", "hunter_api_key_configured": False}

@app.post("/api/settings/keys")
def save_api_keys(req: APIKeysRequest, db: Session = Depends(get_db_session), current_user: AppUser = Depends(get_current_user)):
    keys = db.query(APIKeys).order_by(APIKeys.id.desc()).first()
    if not keys:
        keys = APIKeys()
        db.add(keys)
    if req.hunter_api_key != MASKED_SECRET:
        keys.hunter_api_key = req.hunter_api_key
    db.commit()
    return {"message": "API Keys saved"}

@app.get("/api/campaigns")
def list_campaigns(db: Session = Depends(get_db_session), current_user: AppUser = Depends(get_current_user)):
    campaigns = db.query(Campaign).order_by(Campaign.created_at.desc()).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "niche": c.niche,
            "location": c.location,
            "status": c.status,
            "created_at": c.created_at
        }
        for c in campaigns
    ]

@app.get("/api/campaigns/{campaign_id}")
def get_campaign(campaign_id: int, db: Session = Depends(get_db_session), current_user: AppUser = Depends(get_current_user)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    leads = db.query(Lead).filter(Lead.campaign_id == campaign_id).all()
    return {
        "campaign": {
            "id": campaign.id,
            "name": campaign.name,
            "niche": campaign.niche,
            "location": campaign.location,
            "status": campaign.status,
            "created_at": campaign.created_at
        },
        "leads": [
            {
                "id": l.id,
                "business_name": l.business_name,
                "phone": l.phone,
                "website": l.website,
                "opportunity_score": l.opportunity_score,
                "tech_stack": l.tech_stack,
                "status": l.status,
                "email_draft": l.email_draft
            } for l in leads
        ],
        "leads_count": len(leads)
    }

@app.get("/api/leads/{lead_id}")
def get_lead(lead_id: int, db: Session = Depends(get_db_session), current_user: AppUser = Depends(get_current_user)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead

@app.post("/api/leads/{lead_id}/replied")
def mark_lead_replied(lead_id: int, db: Session = Depends(get_db_session), current_user: AppUser = Depends(get_current_user)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead.status = "replied"
    db.commit()
    return {"message": "Lead marked as replied. Sequence stopped."}

@app.post("/api/campaigns/{campaign_id}/force_sequence")
def force_sequence(campaign_id: int, db: Session = Depends(get_db_session), current_user: AppUser = Depends(get_current_user)):
    config = db.query(SMTPConfig).order_by(SMTPConfig.id.desc()).first()
    if not config or not config.username:
         raise HTTPException(status_code=400, detail="SMTP Configuration missing.")
    smtp_config = {"host": config.host, "port": config.port, "username": config.username, "password": config.password}
    
    res = advance_campaign_sequence(campaign_id, db, smtp_config, force=True)
    
    return {"message": "Force sequence check complete", "results": res}

@app.post("/api/campaigns/{campaign_id}/send")
def send_campaign_emails(campaign_id: int, db: Session = Depends(get_db_session), current_user: AppUser = Depends(get_current_user)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    # Get all audited leads that haven't been sent yet and actually have an email
    leads = db.query(Lead).filter(
        Lead.campaign_id == campaign_id,
        Lead.status.in_(["audited", "error"]),
        Lead.email != None,
        Lead.email != "",
        Lead.email_draft != None
    ).all()
    
    if not leads:
        return {"message": "No valid leads found ready to email. (Must have an email extracted)", "results": {"success": 0}}
        
    # Serialize to dictionary for the SMTP function
    dict_leads = [{"id": l.id, "business_name": l.business_name, "email": l.email, "email_draft": l.email_draft} for l in leads]
        
    config = db.query(SMTPConfig).order_by(SMTPConfig.id.desc()).first()
    smtp_config = None
    if config and config.username and config.password:
        smtp_config = {
            "host": config.host,
            "port": config.port,
            "username": config.username,
            "password": config.password
        }

    # Fire the SMTP pipeline
    try:
        results = send_email_blast(dict_leads, smtp_config=smtp_config)
    except Exception as e:
         raise HTTPException(status_code=500, detail=f"SMTP Infrastructure Error: {e}")
         
    # Update DB status based on SMTP results
    for detail in results.get("details", []):
         lead_id = detail["id"]
         status = detail["status"] # "emailed", "failed"
         
         # Save EmailLog
         error_msg = detail.get("reason", "")
         email_log = EmailLog(lead_id=lead_id, campaign_id=campaign_id, step_number=1, status=status, error_message=error_msg)
         db.add(email_log)
         
         if status == "emailed":
              db_lead = db.query(Lead).filter(Lead.id == lead_id).first()
              if db_lead:
                  db_lead.status = "emailed"
                  
    db.commit()
    return {"message": "Email sequence complete", "results": results}

@app.get("/api/campaigns/{campaign_id}/export")
def export_campaign_csv(campaign_id: int, db: Session = Depends(get_db_session), current_user: AppUser = Depends(get_current_user)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    leads = db.query(Lead).filter(Lead.campaign_id == campaign_id).all()
    
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)

    lead_dicts = [
        {
            "email": l.email,
            "email_draft": l.email_draft,
            "opportunity_score": l.opportunity_score,
            "status": l.status,
        }
        for l in leads
    ]
    summary = build_campaign_summary(lead_dicts)

    writer.writerow(["Campaign Summary"])
    for key, value in summary.items():
        writer.writerow([key, value])
    writer.writerow([])
    writer.writerow(["Lead Details"])
    
    # Write headers
    writer.writerow([
        "Business Name", "Phone", "Email", "Website", "Address",
        "Opportunity Score", "Status", "Tech Stack", "Facebook", "Instagram", "LinkedIn", "AI Pitch Angle", "Email Draft"
    ])
    
    for l in leads:
        writer.writerow([
            l.business_name,
            l.phone,
            l.email,
            l.website,
            l.address,
            l.opportunity_score,
            l.status,
            l.tech_stack,
            l.facebook,
            l.instagram,
            l.linkedin,
            l.pitch_angle_used,
            l.email_draft
        ])
        
    output.seek(0)
    
    # Format a safe filename
    safe_name = "".join(c for c in campaign.name if c.isalnum() or c in (' ', '_', '-')).replace(' ', '_')
    filename = f"LeadForge_{safe_name}.csv"
    
    response = StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv"
    )
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response
