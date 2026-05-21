"""
Run this after any campaign to auto-generate email drafts for leads that are missing them.
Usage: venv\Scripts\python fix_campaign.py --campaign-id 3
"""
import os
import sys
import sqlite3
import argparse
from dotenv import load_dotenv

load_dotenv()

def generate_draft(business_name: str, groq_api_key: str) -> str:
    try:
        from groq import Groq
        client = Groq(api_key=groq_api_key)
        first_name = business_name.split()[0].replace(",", "").replace(".", "") if business_name else "there"
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": f"""You are a professional copywriter sending a cold email.
CRITICAL RULES:
1. First line must be exactly: Subject: [Your Subject Here]
2. Second line is greeting to {first_name}
3. Max 4 sentences
4. End with: Would it be worth a quick 10-minute chat?
5. Pitch web improvement services - mention SEO, mobile optimization, or trust signals"""
                },
                {
                    "role": "user",
                    "content": f"Write a cold email to {first_name} about improving their business website."
                }
            ],
            temperature=0.7,
            max_tokens=300
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"  Groq error for {business_name}: {e}")
        return ""


def fix_campaign(campaign_id: int):
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        print("ERROR: GROQ_API_KEY not found in .env")
        sys.exit(1)

    conn = sqlite3.connect('leadforge.db')
    cur = conn.cursor()

    # Get all leads with email but no draft
    cur.execute("""
        SELECT id, business_name, email 
        FROM leads 
        WHERE campaign_id=? AND email IS NOT NULL AND email != '' 
        AND (email_draft IS NULL OR email_draft = '')
    """, (campaign_id,))
    rows = cur.fetchall()

    if not rows:
        print(f"All leads in campaign {campaign_id} already have drafts or no emails found.")
        conn.close()
        return

    print(f"Found {len(rows)} leads needing email drafts. Generating...")

    for row in rows:
        lead_id, business_name, email = row
        print(f"  Generating for: {business_name} ({email})")
        draft = generate_draft(business_name, groq_api_key)
        if draft:
            cur.execute("""
                UPDATE leads 
                SET email_draft=?, status='audited' 
                WHERE id=?
            """, (draft, lead_id))
            print(f"  Done!")
        else:
            # Fallback generic draft
            first_name = business_name.split()[0].replace(",", "").replace(".", "")
            fallback = f"""Subject: Quick question about your website

Hi {first_name},

I was looking at your website and noticed a few quick wins that could bring in more leads without any ad spend.

Would it be worth a quick 10-minute chat?

Best,
Faizan"""
            cur.execute("""
                UPDATE leads 
                SET email_draft=?, status='audited' 
                WHERE id=?
            """, (fallback, lead_id))
            print(f"  Used fallback draft.")

    conn.commit()
    conn.close()
    print(f"\nDone! {len(rows)} leads updated. Go click 'Start Email Sequence' now.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-id", type=int, required=True)
    args = parser.parse_args()
    fix_campaign(args.campaign_id)
