"""
Multi-channel message generator for LeadForge AI.

Generates platform-tailored outreach messages (LinkedIn, WhatsApp, SMS)
from the same audit data that powers email generation. This module
complements email_generator.py — it does NOT replace it.

Usage:
    from ai.message_generator import generate_all_channel_messages

    messages = generate_all_channel_messages(
        business_name="Ahmed's Plumbing",
        weaknesses_summary="Missing SSL, no H1 tag, ...",
        persona=persona_obj,
        first_name="Ahmed",
        channels=["linkedin", "whatsapp", "sms"]
    )
"""

import os
from typing import Dict, List, Optional
from groq import Groq
from loguru import logger
import yaml
import requests
from dotenv import load_dotenv

from ai.channel_prompts import (
    linkedin_connection_prompt,
    linkedin_followup_prompt,
    whatsapp_prompt,
    sms_prompt,
    enforce_char_limit,
    LINKEDIN_CONNECTION_LIMIT,
    SMS_CHAR_LIMIT,
)
from ai.spam_checker import clean_spam_words

load_dotenv()

# Load Config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)
    LLM_PROVIDER = config.get("llm_provider", "groq")
    GROQ_MODEL = config.get("groq_model", "llama3-8b-8192")
    OLLAMA_MODEL = config.get("ollama_model", "llama3")

ALL_CHANNELS = ["linkedin", "whatsapp", "sms"]


def _get_groq_client():
    """Initialize and return a Groq client."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.warning("GROQ_API_KEY not found in environment!")
        return None
    try:
        return Groq(api_key=api_key.strip())
    except Exception as e:
        logger.warning(f"Groq Client init error: {e}")
        return None


def _call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 250) -> str:
    """Call the LLM (Groq with Ollama fallback) and return raw text."""
    draft = ""

    if LLM_PROVIDER == "groq":
        groq_client = _get_groq_client()
        if groq_client:
            try:
                completion = groq_client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.7,
                    max_tokens=max_tokens,
                )
                draft = completion.choices[0].message.content
            except Exception as e:
                logger.error(f"Groq generation failed: {e}. Falling back to Ollama...")
                draft = _ollama_fallback(system_prompt, user_prompt)
        else:
            logger.error("Groq client could not be initialized. Falling back to Ollama...")
            draft = _ollama_fallback(system_prompt, user_prompt)
    else:
        draft = _ollama_fallback(system_prompt, user_prompt)

    return draft.strip() if draft else ""


def _ollama_fallback(system_prompt: str, user_prompt: str) -> str:
    """Local fallback using Ollama API."""
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    endpoint = f"{ollama_url}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "system": system_prompt,
        "prompt": user_prompt,
        "stream": False,
    }
    try:
        resp = requests.post(endpoint, json=payload, timeout=30)
        if resp.status_code == 200:
            return resp.json().get("response", "")
    except Exception as e:
        logger.error(f"Ollama fallback also failed: {e}")
    return ""


def _resolve_first_name(business_name: str, provided_first_name: Optional[str] = None) -> str:
    """Extract a first name from business name or use the provided one."""
    if provided_first_name:
        return provided_first_name
    return business_name.split()[0].replace(",", "").replace(".", "") if business_name else "there"


# ──────────────────────────────────────────────
#  INDIVIDUAL CHANNEL GENERATORS
# ──────────────────────────────────────────────

def generate_linkedin_messages(
    business_name: str,
    weaknesses_summary: str,
    persona=None,
    first_name: Optional[str] = None,
) -> Dict[str, str]:
    """
    Generate LinkedIn connection note + follow-up message.

    Returns:
        {
            "linkedin_connection_note": "...",
            "linkedin_followup": "..."
        }
    """
    first_name = _resolve_first_name(business_name, first_name)
    result = {"linkedin_connection_note": "", "linkedin_followup": ""}

    if not weaknesses_summary or "surprisingly healthy" in weaknesses_summary.lower():
        return result

    # Connection note (300 chars max)
    try:
        system_prompt = linkedin_connection_prompt(first_name, business_name, weaknesses_summary, persona)
        raw = _call_llm(system_prompt, f"Write the LinkedIn connection note for {first_name}.", max_tokens=100)
        if raw:
            raw = clean_spam_words(raw)
            result["linkedin_connection_note"] = enforce_char_limit(raw, LINKEDIN_CONNECTION_LIMIT)
            logger.info(f"  LinkedIn connection note generated ({len(result['linkedin_connection_note'])} chars)")
    except Exception as e:
        logger.error(f"LinkedIn connection note failed: {e}")

    # Follow-up message
    try:
        system_prompt = linkedin_followup_prompt(first_name, business_name, weaknesses_summary, persona)
        raw = _call_llm(system_prompt, f"Write the LinkedIn follow-up message for {first_name}.", max_tokens=200)
        if raw:
            result["linkedin_followup"] = clean_spam_words(raw)
            logger.info(f"  LinkedIn follow-up generated")
    except Exception as e:
        logger.error(f"LinkedIn follow-up failed: {e}")

    return result


def generate_whatsapp_message(
    business_name: str,
    weaknesses_summary: str,
    persona=None,
    first_name: Optional[str] = None,
) -> str:
    """Generate a WhatsApp outreach message. Returns empty string on failure."""
    first_name = _resolve_first_name(business_name, first_name)

    if not weaknesses_summary or "surprisingly healthy" in weaknesses_summary.lower():
        return ""

    try:
        system_prompt = whatsapp_prompt(first_name, business_name, weaknesses_summary, persona)
        raw = _call_llm(system_prompt, f"Write the WhatsApp message for {first_name}.", max_tokens=150)
        if raw:
            draft = clean_spam_words(raw)
            logger.info(f"  WhatsApp message generated")
            return draft
    except Exception as e:
        logger.error(f"WhatsApp message failed: {e}")

    return ""


def generate_sms_message(
    business_name: str,
    weaknesses_summary: str,
    persona=None,
    first_name: Optional[str] = None,
) -> str:
    """Generate an SMS message (160 chars max). Returns empty string on failure."""
    first_name = _resolve_first_name(business_name, first_name)

    if not weaknesses_summary or "surprisingly healthy" in weaknesses_summary.lower():
        return ""

    try:
        system_prompt = sms_prompt(first_name, business_name, weaknesses_summary, persona)
        raw = _call_llm(system_prompt, f"Write the SMS for {first_name}.", max_tokens=80)
        if raw:
            draft = clean_spam_words(raw)
            result = enforce_char_limit(draft, SMS_CHAR_LIMIT)
            logger.info(f"  SMS generated ({len(result)} chars)")
            return result
    except Exception as e:
        logger.error(f"SMS message failed: {e}")

    return ""


# ──────────────────────────────────────────────
#  ORCHESTRATOR
# ──────────────────────────────────────────────

def generate_all_channel_messages(
    business_name: str,
    weaknesses_summary: str,
    persona=None,
    first_name: Optional[str] = None,
    channels: Optional[List[str]] = None,
) -> Dict[str, str]:
    """
    Generate outreach messages for all requested channels.

    Args:
        business_name: The lead's business name
        weaknesses_summary: Audit findings summary string
        persona: UserPersona or SimpleNamespace with persona fields
        first_name: Optional first name of the lead contact
        channels: List of channels to generate for. Default: all channels.
                  Valid values: "linkedin", "whatsapp", "sms"

    Returns:
        {
            "linkedin_connection_note": "...",
            "linkedin_followup": "...",
            "whatsapp_message": "...",
            "sms_message": "..."
        }
    """
    if channels is None:
        channels = ALL_CHANNELS

    result = {
        "linkedin_connection_note": "",
        "linkedin_followup": "",
        "whatsapp_message": "",
        "sms_message": "",
    }

    if not weaknesses_summary or "surprisingly healthy" in weaknesses_summary.lower():
        logger.info(f"  Skipping multi-channel for {business_name} — no significant weaknesses.")
        return result

    first_name = _resolve_first_name(business_name, first_name)

    # Generate for each requested channel
    if "linkedin" in channels:
        linkedin_msgs = generate_linkedin_messages(business_name, weaknesses_summary, persona, first_name)
        result["linkedin_connection_note"] = linkedin_msgs["linkedin_connection_note"]
        result["linkedin_followup"] = linkedin_msgs["linkedin_followup"]

    if "whatsapp" in channels:
        result["whatsapp_message"] = generate_whatsapp_message(
            business_name, weaknesses_summary, persona, first_name
        )

    if "sms" in channels:
        result["sms_message"] = generate_sms_message(
            business_name, weaknesses_summary, persona, first_name
        )

    generated_count = sum(1 for v in result.values() if v)
    logger.info(f"  Multi-channel: generated {generated_count} messages for {business_name}")

    return result
