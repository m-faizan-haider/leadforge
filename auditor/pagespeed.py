"""
auditor/pagespeed.py

Fetches real Core Web Vitals and performance scores from
Google PageSpeed Insights API (free, no billing required).

Returns a dict that is merged into the lead's audit_findings
under the key "performance".
"""

import os
import requests
from loguru import logger


PAGESPEED_API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def fetch_pagespeed(url: str) -> dict:
    """
    Calls the Google PageSpeed Insights API for both mobile and desktop.

    Returns:
        {
            "mobile_score":   int (0–100),
            "desktop_score":  int (0–100),
            "lcp":            str  e.g. "4.2 s"
            "fid":            str  e.g. "180 ms"
            "cls":            str  e.g. "0.25"
            "speed_index":    str  e.g. "5.1 s"
            "tti":            str  e.g. "7.3 s"   (Time to Interactive)
            "error":          str | None
        }
    """
    result = {
        "mobile_score": None,
        "desktop_score": None,
        "lcp": None,
        "fid": None,
        "cls": None,
        "speed_index": None,
        "tti": None,
        "error": None,
    }

    api_key = os.getenv("PAGESPEED_API_KEY", "")  # optional — works without key at lower rate limit

    def _call(strategy: str) -> dict:
        params = {"url": url, "strategy": strategy, "category": "performance"}
        if api_key:
            params["key"] = api_key
        try:
            resp = requests.get(PAGESPEED_API_URL, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            logger.warning(f"PageSpeed API timed out for {url} ({strategy})")
            return {}
        except requests.exceptions.HTTPError as e:
            logger.warning(f"PageSpeed API HTTP error for {url} ({strategy}): {e}")
            return {}
        except Exception as e:
            logger.warning(f"PageSpeed API unexpected error for {url} ({strategy}): {e}")
            return {}

    # --- Mobile ---
    mobile_data = _call("mobile")
    if mobile_data:
        result["mobile_score"] = _extract_score(mobile_data)
        metrics = _extract_metrics(mobile_data)
        result.update(metrics)

    # --- Desktop ---
    desktop_data = _call("desktop")
    if desktop_data:
        result["desktop_score"] = _extract_score(desktop_data)

    if result["mobile_score"] is None and result["desktop_score"] is None:
        result["error"] = "PageSpeed API returned no usable data."

    logger.info(
        f"PageSpeed → {url} | Mobile: {result['mobile_score']} | Desktop: {result['desktop_score']}"
    )
    return result


def _extract_score(data: dict) -> int | None:
    """Pull the 0–100 Lighthouse performance score."""
    try:
        score = (
            data["lighthouseResult"]["categories"]["performance"]["score"]
        )
        return int(round(score * 100))
    except (KeyError, TypeError):
        return None


def _extract_metrics(data: dict) -> dict:
    """Extract Core Web Vitals from the Lighthouse audit results."""
    metrics = {}
    try:
        audits = data["lighthouseResult"]["audits"]

        def _display(key: str) -> str | None:
            audit = audits.get(key, {})
            return audit.get("displayValue")

        metrics["lcp"] = _display("largest-contentful-paint")
        metrics["fid"] = _display("max-potential-fid") or _display("interactive")
        metrics["cls"] = _display("cumulative-layout-shift")
        metrics["speed_index"] = _display("speed-index")
        metrics["tti"] = _display("interactive")
    except (KeyError, TypeError):
        pass
    return metrics


def pagespeed_summary_for_ai(perf: dict) -> str:
    """
    Formats PageSpeed data into a short, punchy string for the AI email prompt.
    Example: "PERFORMANCE: Mobile speed score 23/100. LCP: 6.2 s. CLS: 0.31."
    """
    if not perf or perf.get("error"):
        return ""

    parts = []
    mobile = perf.get("mobile_score")
    desktop = perf.get("desktop_score")

    if mobile is not None:
        grade = _score_grade(mobile)
        parts.append(f"Mobile speed score {mobile}/100 ({grade})")
    if desktop is not None:
        parts.append(f"Desktop {desktop}/100")
    if perf.get("lcp"):
        parts.append(f"LCP {perf['lcp']}")
    if perf.get("cls"):
        parts.append(f"CLS {perf['cls']}")
    if perf.get("speed_index"):
        parts.append(f"Speed Index {perf['speed_index']}")

    return "- PERFORMANCE: " + ". ".join(parts) + "." if parts else ""


def _score_grade(score: int) -> str:
    if score >= 90:
        return "Good"
    if score >= 50:
        return "Needs Improvement"
    return "Poor"
