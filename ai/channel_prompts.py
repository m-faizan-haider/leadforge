"""
Channel-specific AI prompt templates for multi-channel outreach.

Each channel has its own tone, format, length rules, and CTA style.
These prompts are consumed by message_generator.py to produce
platform-tailored messages from the same audit data.
"""


# ──────────────────────────────────────────────
#  CHARACTER LIMITS
# ──────────────────────────────────────────────
LINKEDIN_CONNECTION_LIMIT = 300
SMS_CHAR_LIMIT = 160


def enforce_char_limit(text: str, limit: int) -> str:
    """Truncate text to fit within a character limit, preserving whole words."""
    if len(text) <= limit:
        return text
    truncated = text[:limit]
    # Cut at the last space to avoid breaking a word
    last_space = truncated.rfind(" ")
    if last_space > limit * 0.6:
        truncated = truncated[:last_space]
    return truncated.rstrip(".,!? ")


# ──────────────────────────────────────────────
#  LINKEDIN PROMPTS
# ──────────────────────────────────────────────
def linkedin_connection_prompt(first_name: str, business_name: str, weaknesses_summary: str, persona=None) -> str:
    """System prompt for a LinkedIn connection request note (300 chars max)."""
    value_prop = ""
    if persona:
        value_prop = f"Your value proposition: {persona.value_proposition}. "

    return f"""You are writing a LinkedIn connection request note to {first_name} from {business_name}.

CRITICAL RULES:
1. Maximum 300 characters total. Count carefully.
2. DO NOT pitch or sell. This is just a friendly connection request.
3. Be warm, specific, and reference something about their business.
4. DO NOT use "Subject:" — LinkedIn doesn't have subject lines.
5. DO NOT use a formal greeting like "Dear". Use "Hi {first_name}" or just start talking.
6. End with something like "Would love to connect!" or "Let's connect!"
7. {value_prop}Mention what you do in ONE short phrase.

Context about their business (use subtly, do NOT list these):
{weaknesses_summary}

Write the connection note. Remember: 300 characters MAX."""


def linkedin_followup_prompt(first_name: str, business_name: str, weaknesses_summary: str, persona=None) -> str:
    """System prompt for a LinkedIn follow-up message after they accept the connection."""
    if persona and persona.objective == "job_hunt":
        copywriter_rule = f"You're looking for a job/internship. Your skills: {persona.skills}."
        cta = "Would you be open to a quick chat about opportunities on your team?"
    elif persona and persona.objective == "freelance":
        copywriter_rule = f"You're a freelancer offering: {persona.skills}. Value prop: {persona.value_proposition}."
        cta = "Would it be worth a quick chat to see if I can help?"
    else:
        val_prop = persona.value_proposition if persona else "We help local businesses fix website issues to get more customers."
        copywriter_rule = f"You're offering B2B services. Value prop: {val_prop}"
        cta = "Would it be worth a quick 10-minute chat?"

    return f"""You are writing a LinkedIn follow-up message to {first_name} from {business_name}.
They already accepted your connection request. Now you're sending your first real message.

CRITICAL RULES:
1. Maximum 4 sentences. Keep it short — LinkedIn messages should feel casual.
2. DO NOT use "Subject:" — this is a DM, not an email.
3. Start with "Thanks for connecting, {first_name}!" or similar.
4. Reference ONE specific finding about their website/business (don't list multiple).
5. End exactly with this CTA: "{cta}"
6. Tone: casual-professional, like messaging a colleague. NOT formal.
7. {copywriter_rule}

Website/business findings to reference:
{weaknesses_summary}

Write the follow-up message."""


# ──────────────────────────────────────────────
#  WHATSAPP PROMPTS
# ──────────────────────────────────────────────
def whatsapp_prompt(first_name: str, business_name: str, weaknesses_summary: str, persona=None) -> str:
    """System prompt for a WhatsApp message."""
    if persona and persona.objective == "job_hunt":
        copywriter_rule = f"You're looking for a job/internship. Your skills: {persona.skills}."
        cta = "Would you be open to a quick chat? 🙏"
    elif persona and persona.objective == "freelance":
        copywriter_rule = f"You're a freelancer offering: {persona.skills}."
        cta = "Want me to send over a quick free audit? 📊"
    else:
        val_prop = persona.value_proposition if persona else "We help businesses fix website issues."
        copywriter_rule = f"You're offering B2B services. Value prop: {val_prop}"
        cta = "Want me to send a quick free audit? 📊"

    return f"""You are writing a WhatsApp message to {first_name} from {business_name}.

CRITICAL RULES:
1. Maximum 3 sentences. WhatsApp messages must be SHORT.
2. DO NOT use "Subject:" — this is WhatsApp, not email.
3. Start with "Hi {first_name} 👋" — WhatsApp is casual.
4. Use 1-2 emojis naturally (don't overdo it).
5. Mention ONE specific thing about their business (compliment + problem).
6. End exactly with this CTA: "{cta}"
7. Tone: friendly and casual, like texting a friend who owns a business.
8. {copywriter_rule}

Business findings to reference (pick the most impactful ONE):
{weaknesses_summary}

Write the WhatsApp message."""


# ──────────────────────────────────────────────
#  SMS PROMPTS
# ──────────────────────────────────────────────
def sms_prompt(first_name: str, business_name: str, weaknesses_summary: str, persona=None) -> str:
    """System prompt for an SMS message (160 chars max)."""
    sender_name = persona.name if persona else "LeadForge"

    return f"""You are writing an SMS text message to {first_name} from {business_name}.

CRITICAL RULES:
1. MAXIMUM 160 characters total. This is an SMS — count every character.
2. DO NOT use "Subject:" — this is a text message.
3. Start with "Hi {first_name},"
4. Mention ONE website issue in the shortest way possible.
5. End with a simple CTA like "Reply YES for a free audit" or "Interested? Reply YES"
6. Sign off with "- {sender_name}"
7. NO emojis in SMS (they take extra characters).
8. Every word must earn its place. Be ruthlessly concise.

Business context (distill to the single most important point):
{weaknesses_summary}

Write the SMS. Remember: 160 characters MAXIMUM."""
