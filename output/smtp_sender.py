import os
import smtplib
import re
from email.message import EmailMessage
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SIMULATE_EMAIL = os.getenv("SIMULATE_EMAIL", "True").lower() == "true"

def send_email_blast(leads_to_email: list, smtp_config: dict = None):
    """
    Takes a list of lead database dictionary proxies and dispatches their drafted emails.
    Optionally accepts a smtp_config dict: {"host": "...", "port": 587, "username": "...", "password": "..."}.
    Returns a dictionary of success/failures.
    """
    results = {"success": 0, "failed": 0, "skipped": 0, "details": []}
    
    # Defaults to env if not provided via config
    host = smtp_config.get("host", SMTP_HOST) if smtp_config else SMTP_HOST
    port = smtp_config.get("port", SMTP_PORT) if smtp_config else SMTP_PORT
    username = smtp_config.get("username", SMTP_USER) if smtp_config else SMTP_USER
    password = smtp_config.get("password", SMTP_PASS) if smtp_config else SMTP_PASS
    
    # We ignore simulate_email if user explicitly passed full config from UI
    is_simulation = SIMULATE_EMAIL
    if smtp_config and username and password:
        is_simulation = False
        
    if is_simulation:
        logger.info("SIMULATE_EMAIL is True or no config provided. Preparing to safely pretend to send emails.")
    elif not username or not password:
        logger.error("SMTP credentials missing.")
        raise ValueError("SMTP username and password must be provided to disable simulation.")

    # If actually sending, connect to SMTP Server once for bulk speed
    server = None
    if not is_simulation:
        try:
            server = smtplib.SMTP(host, int(port))
            server.starttls()
            server.login(username, password)
        except Exception as e:
            logger.error(f"Failed to connect to SMTP server: {e}")
            raise

    try:
        for lead in leads_to_email:
            email_addr = lead.get("email")
            draft = lead.get("email_draft")
            business = lead.get("business_name")
            lead_id = lead.get("id")
            
            if not email_addr or not draft:
                results["skipped"] += 1
                results["details"].append({"id": lead_id, "status": "skipped", "reason": "No valid contact email or AI draft was generated."})
                continue
                
            logger.info(f"Targeting {business} at {email_addr}...")
            
            if SIMULATE_EMAIL:
                # Pretend it worked
                results["success"] += 1
                results["details"].append({"id": lead_id, "status": "emailed"})
                logger.debug(f"[SIMULATION] AI Pipeline successfully skipped SMTP layer and injected into `{email_addr}`")
            else:
                try:
                    msg = EmailMessage()
                    
                    # Robust Subject Extraction
                    subject = "Quick question about your website" # fallback
                    body = draft
                    
                    match = re.search(r"Subject:\s*(.*)", draft, re.IGNORECASE)
                    if match:
                        subject = match.group(1).strip()
                        # Remove the subject line neatly from the body
                        body = re.sub(r"Subject:\s*.*\n?", "", draft, count=1, flags=re.IGNORECASE).strip()
                        
                    msg.set_content(body)
                    msg['Subject'] = subject
                    msg['From'] = username
                    msg['To'] = email_addr
                    
                    server.send_message(msg)
                    results["success"] += 1
                    results["details"].append({"id": lead_id, "status": "emailed"})
                    logger.debug(f"Email successfully dispatched to {email_addr}")
                except Exception as e:
                    logger.error(f"Failed sending to {email_addr}: {e}")
                    results["failed"] += 1
                    results["details"].append({"id": lead_id, "status": "failed", "reason": str(e)})
                    
    finally:
        if server:
            server.quit()
            
    return results
