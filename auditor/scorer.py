from auditor.pagespeed import pagespeed_summary_for_ai


def calculate_opportunity_score(findings: dict, review_count: int) -> int:
    """
    Calculates a 0-100 opportunity score.
    Higher score means the business has more problems and is a better lead.
    Now includes Google PageSpeed performance data in scoring.
    """
    score = 0

    if not findings:
        return 50  # Base score for unreachable sites

    seo = findings.get("seo", {})
    ux = findings.get("ux", {})
    trust = findings.get("trust", {})
    tech = findings.get("tech", {})
    perf = findings.get("performance", {})

    # Trust / Obvious fixes (+20)
    if not trust.get("has_ssl", True):
        score += 20

    # Mobile UX fixes (+15)
    if not ux.get("has_viewport", True):
        score += 15

    # SEO fixes (+10 each) // Max 20 here
    if not seo.get("has_title", True):
        score += 10
    if not seo.get("has_meta_desc", True):
        score += 10

    # Social Proof (+15)
    if review_count and review_count < 10:
        score += 15

    # Conversion (+10 each)
    if not trust.get("has_contact_form", True):
        score += 10
    if not ux.get("has_cta", True):
        score += 10

    # Pixels (+5)
    if not trust.get("has_tracking_pixel", True):
        score += 5

    # Tech Stack - Easier sells (+5)
    if tech.get("stack") in ["Wix", "Squarespace"]:
        score += 5

    # --- PageSpeed Performance Score ---
    # Mobile score < 50 = "Poor" → strong selling point (+15)
    # Mobile score 50–89 = "Needs Improvement" → good selling point (+8)
    mobile_score = perf.get("mobile_score") if perf else None
    if mobile_score is not None:
        if mobile_score < 50:
            score += 15
        elif mobile_score < 90:
            score += 8

    # Cap at 100
    return min(100, score)


def format_audit_summary_for_ai(findings: dict) -> str:
    """
    Condenses the large dictionary into a tight structure for the LLM.
    Reduces token usage drastically.
    Now includes PageSpeed performance findings for more specific email pitches.
    """
    if not findings:
        return "No accessible website data."

    seo = findings.get("seo", {})
    ux = findings.get("ux", {})
    trust = findings.get("trust", {})
    perf = findings.get("performance", {})

    bullet_points = []

    if not trust.get("has_ssl"):
        bullet_points.append("- SECURITY: No SSL (Missing HTTPS).")
    if not ux.get("has_viewport"):
        bullet_points.append("- UX: Not optimized for mobile (Missing Viewport).")
    if not seo.get("has_title") or not seo.get("has_meta_desc"):
        bullet_points.append("- SEO: Missing foundational metadata (No Title/Description).")
    if not seo.get("has_h1"):
        bullet_points.append("- SEO: Missing primary Header 1 tag.")
    if not trust.get("has_contact_form"):
        bullet_points.append("- CONVERSION: No contact form found.")
    if not trust.get("has_tracking_pixel"):
        bullet_points.append("- ANALYTICS: No Google Analytics or Meta Pixel detected.")

    # Add PageSpeed line if data is available
    perf_line = pagespeed_summary_for_ai(perf)
    if perf_line:
        bullet_points.append(perf_line)

    if not bullet_points:
        return "Website seems surprisingly healthy. Standard modern stack."

    return "\n".join(bullet_points)
