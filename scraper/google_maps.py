import asyncio
import random
import re
from typing import Dict, List

import yaml
from loguru import logger
from playwright.async_api import Page, async_playwright
from playwright_stealth import Stealth

from config import settings
from scraper.proxy_manager import ProxyManager
from scraper.user_agents import get_random_user_agent

SCROLL_PAUSE_MIN_MS = 1500
SCROLL_PAUSE_MAX_MS = 3500
PAGE_LOAD_WAIT_MIN_MS = 1500
PAGE_LOAD_WAIT_MAX_MS = 3500
MAX_SCROLL_ROUNDS = 20

# Google Maps DOM selectors are volatile, so every field has alternatives.
SELECTORS = {
    "name": [
        "h1.DUwDvf",
        "h1[class*='fontHeadlineLarge']",
        "div[role='main'] h1",
    ],
    "address": [
        "[data-item-id='address']",
        "button[data-item-id='address']",
        "button[aria-label^='Address:']",
    ],
    "phone": [
        "[data-item-id^='phone:tel:']",
        "button[data-item-id^='phone:tel:']",
        "button[aria-label^='Phone:']",
    ],
    "website": [
        "a[data-item-id='authority']",
        "a[aria-label^='Website:']",
        "a[href^='http']:has-text('Website')",
    ],
    "rating": [
        "div.F7nice span[aria-hidden='true']",
        "span[aria-hidden='true'][class*='MW4etd']",
        "span[aria-label*='stars']",
    ],
    "reviews": [
        "div.F7nice span[aria-label*='reviews']",
        "span[aria-label*='reviews']",
        "button[jsaction*='reviewChart'] span",
    ],
}


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    for prefix in ["Address: ", "Phone: ", "Website: "]:
        if text.startswith(prefix):
            text = text[len(prefix):]
    return text


def parse_review_count(value) -> int:
    if isinstance(value, int):
        return value
    if not value:
        return 0
    digits = re.sub(r"[^0-9]", "", str(value))
    return int(digits) if digits else 0


def build_lead(
    business_name: str = "",
    address: str = "",
    phone: str = "",
    website: str = "",
    rating="",
    review_count=0,
) -> Dict:
    reviews = parse_review_count(review_count)
    return {
        "business_name": clean_text(business_name),
        "name": clean_text(business_name),
        "address": clean_text(address),
        "phone": clean_text(phone),
        "website": website or "",
        "rating": rating or "",
        "review_count": reviews,
        "reviews": reviews,
    }


def load_scraper_config() -> Dict:
    try:
        with open("config.yaml", "r") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.warning("config.yaml not found. Using scraper defaults.")
        return {}


def get_scraper_mode() -> str:
    mode = settings.scraper_mode
    if mode not in {"serpapi", "playwright"}:
        logger.warning(f"Unknown SCRAPER_MODE='{mode}'. Falling back to serpapi.")
        return "serpapi"
    return mode


def fetch_serpapi_google_maps_leads(niche: str, location: str, max_leads: int) -> List[Dict]:
    try:
        import serpapi
    except ImportError as exc:
        raise RuntimeError("serpapi package is not installed. Run pip install -r requirements.txt.") from exc

    api_key = settings.serpapi_key
    if not api_key:
        raise RuntimeError("SERPAPI_KEY is missing. Set SERPAPI_KEY in .env or use SCRAPER_MODE=playwright.")

    query = f"{niche} in {location}"
    logger.info(f"Fetching Google Maps leads through SerpAPI for query: {query}")

    params = {
        "engine": "google_maps",
        "q": query,
        "type": "search",
    }

    try:
        client = serpapi.Client(api_key=api_key)
        search_results = client.search(params)
        results = search_results.as_dict() if hasattr(search_results, "as_dict") else dict(search_results)
    except Exception as exc:
        raise RuntimeError(f"SerpAPI request failed: {exc}") from exc

    if results.get("error"):
        raise RuntimeError(f"SerpAPI error: {results['error']}")

    raw_results = results.get("local_results") or results.get("place_results") or []
    if isinstance(raw_results, dict):
        raw_results = [raw_results]

    leads = []
    for item in raw_results[: int(max_leads)]:
        lead = build_lead(
            business_name=item.get("title") or item.get("name") or "",
            address=item.get("address") or "",
            phone=item.get("phone") or "",
            website=item.get("website") or "",
            rating=item.get("rating") or "",
            review_count=item.get("reviews") or item.get("review_count") or 0,
        )
        if lead["business_name"]:
            leads.append(lead)

    logger.info(f"SerpAPI returned {len(leads)} usable leads.")
    return leads


async def random_delay(min_ms: int = PAGE_LOAD_WAIT_MIN_MS, max_ms: int = PAGE_LOAD_WAIT_MAX_MS):
    await asyncio.sleep(random.uniform(min_ms / 1000, max_ms / 1000))


async def first_locator_text(page: Page, selectors: List[str]) -> str:
    for selector in selectors:
        try:
            locator = page.locator(selector)
            if await locator.count() > 0:
                return clean_text(await locator.first.inner_text(timeout=2500))
        except Exception:
            continue
    return ""


async def first_locator_attribute(page: Page, selectors: List[str], attribute: str) -> str:
    for selector in selectors:
        try:
            locator = page.locator(selector)
            if await locator.count() > 0:
                return clean_text(await locator.first.get_attribute(attribute, timeout=2500) or "")
        except Exception:
            continue
    return ""


async def get_business_links(page: Page, max_leads: int) -> List[str]:
    logger.info("Scrolling Google Maps results to discover listings...")
    seen = set()
    links = []

    container = page.locator('div[role="feed"]')

    for _ in range(MAX_SCROLL_ROUNDS):
        anchors = await page.locator(
            'a[href*="/maps/place/"], a.hfpxzc, a[href*="google.com/maps?cid="]'
        ).all()
        for anchor in anchors:
            href = await anchor.get_attribute("href")
            if href and href not in seen:
                seen.add(href)
                links.append(href)

        if len(links) >= max_leads:
            break

        try:
            if await container.count() > 0:
                await container.evaluate("el => el.scrollBy(0, 800)")
            else:
                await page.keyboard.press("PageDown")
        except Exception:
            await page.keyboard.press("End")

        await random_delay(SCROLL_PAUSE_MIN_MS, SCROLL_PAUSE_MAX_MS)

        if await page.get_by_text("You've reached the end of the list").count() > 0:
            break

    logger.info(f"Found {len(links[:max_leads])} Google Maps listing URLs.")
    return links[:max_leads]


async def scrape_listing(page: Page, url: str) -> Dict:
    lead = build_lead()

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await random_delay()

        business_name = await first_locator_text(page, SELECTORS["name"])
        rating = await first_locator_text(page, SELECTORS["rating"])

        reviews_label = await first_locator_attribute(page, SELECTORS["reviews"], "aria-label")
        if not reviews_label:
            reviews_label = await first_locator_text(page, SELECTORS["reviews"])

        address = await first_locator_attribute(page, SELECTORS["address"], "aria-label")
        phone = await first_locator_attribute(page, SELECTORS["phone"], "aria-label")
        website = await first_locator_attribute(page, SELECTORS["website"], "href")

        lead = build_lead(
            business_name=business_name,
            address=address,
            phone=phone,
            website=website,
            rating=rating,
            review_count=reviews_label,
        )

    except Exception as exc:
        logger.warning(f"Error scraping Google Maps listing URL {url}: {exc}")

    return lead


async def extract_google_maps_leads_playwright(niche: str, location: str, max_leads: int) -> List[Dict]:
    leads = []
    query = f"{niche} in {location}"
    maps_url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"

    logger.info(f"Navigating to Google Maps with Playwright fallback for query: {query}")

    config = load_scraper_config()
    proxy_manager = ProxyManager(config)

    async with async_playwright() as p:
        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ]
        browser = await p.chromium.launch(headless=True, args=args)

        pw_proxy = proxy_manager.get_playwright_proxy(domain="google.com")

        context_kwargs = {
            "user_agent": get_random_user_agent(),
            "viewport": {"width": random.randint(1280, 1920), "height": random.randint(800, 1080)},
        }
        if pw_proxy:
            context_kwargs["proxy"] = pw_proxy
            logger.debug("Routing Google Maps through Playwright Context Proxy.")

        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()

        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        await Stealth().apply_stealth_async(page)

        try:
            await page.goto(maps_url, wait_until="domcontentloaded", timeout=60000)
        except Exception as exc:
            logger.warning(f"Google Maps page load timed out; proceeding with available DOM. Error: {exc}")
        await random_delay()

        try:
            accept_btn = page.get_by_role("button", name=re.compile(r"Accept|Agree", re.I))
            if await accept_btn.count() > 0:
                await accept_btn.first.click()
                await random_delay()
        except Exception:
            pass

        links = await get_business_links(page, max_leads)

        for i, link in enumerate(links, 1):
            logger.info(f"[{i}/{len(links)}] Scraping Google Maps listing basic info...")

            await page.mouse.move(random.randint(100, 500), random.randint(100, 500))
            await random_delay(1500, 3500)

            lead = await scrape_listing(page, link)
            if lead["business_name"]:
                leads.append(lead)
            await random_delay(1500, 3500)

        await browser.close()

    return leads


async def extract_google_maps_leads(niche: str, location: str, max_leads: int) -> List[Dict]:
    """
    Extract Google Maps leads using SerpAPI by default, with Playwright retained as
    fallback for local/offline scraping.
    """
    mode = get_scraper_mode()

    if mode == "playwright":
        logger.info("SCRAPER_MODE=playwright. Skipping SerpAPI and using Playwright scraper.")
        return await extract_google_maps_leads_playwright(niche, location, max_leads)

    try:
        return await asyncio.to_thread(fetch_serpapi_google_maps_leads, niche, location, max_leads)
    except Exception as exc:
        logger.warning(f"SerpAPI scraper failed. Falling back to Playwright. Reason: {exc}")
        return await extract_google_maps_leads_playwright(niche, location, max_leads)
