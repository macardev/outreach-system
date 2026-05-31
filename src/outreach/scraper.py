from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from typing import Any

import requests
from bs4 import BeautifulSoup

from src.outreach import sheets_manager
from src.outreach.config import settings

logger = logging.getLogger(__name__)


def search_businesses(
    city: str, business_type: str, radius_km: int | None = None
) -> list[dict[str, Any]]:
    radius = radius_km or settings.MAPS_RADIUS_KM
    api_key = settings.GOOGLE_MAPS_API_KEY
    if not api_key:
        logger.error("GOOGLE_MAPS_API_KEY is not set")
        return []

    businesses = []
    seen_place_ids = set()

    query = f"{business_type} {city}"
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params: dict[str, Any] = {
        "query": query,
        "key": api_key,
        "radius": radius * 1000,
    }

    try:
        while len(businesses) < settings.MAPS_SEARCH_LIMIT:
            resp = _call_google_api(url, params)
            if not resp:
                break

            results = resp.get("results", [])
            for place in results:
                place_id = place.get("place_id")
                if place_id and place_id not in seen_place_ids:
                    seen_place_ids.add(place_id)
                    business = _extract_business(place, city, business_type)
                    businesses.append(business)

            next_token = resp.get("next_page_token")
            if not next_token:
                break
            params = {"pagetoken": next_token, "key": api_key}

    except Exception as e:
        logger.error(
            "Error searching businesses in %s (%s): %s", city, business_type, e
        )

    logger.info(
        "Found %s businesses for %s in %s", len(businesses), business_type, city
    )
    return businesses


def check_website_quality(website_url: str | None) -> str:
    if not website_url:
        return "none"

    try:
        resp = requests.get(
            website_url,
            timeout=10,
            allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        )

        if "X-Wix-Published-Version" in resp.headers:
            return "wix"

        soup = BeautifulSoup(resp.text, "html.parser")
        generator_tag = soup.find("meta", attrs={"name": "generator"})
        if generator_tag:
            content = generator_tag.get("content", "").lower()
            if "blogger" in content:
                return "blogger"
            if "wordpress" in content:
                return "wordpress_basic"

        quality = _check_pagespeed_score(website_url)
        return quality

    except requests.RequestException:
        logger.warning("Could not fetch website %s", website_url)
        return "poor"
    except Exception as e:
        logger.warning("Error checking website %s: %s", website_url, e)
        return "poor"


def find_contact_email(
    business_name: str, website: str | None, phone: str | None,
    place_id: str | None = None, city: str | None = None,
) -> str | None:
    prefixes = ["info", "iletisim", "contact", "hello", "randevu", "bilgi", "destek"]

    if website:
        email = _scrape_website_for_email(website, business_name)
        if email:
            return email

    if website:
        for page_path in [
            "/iletisim",
            "/contact",
            "/hakkimizda",
            "/about",
            "/iletişim",
        ]:
            try:
                url = f"{website.rstrip('/')}{page_path}"
                resp = requests.get(
                    url, timeout=10, headers={"User-Agent": "Mozilla/5.0"}
                )
                if resp.status_code == 200:
                    found = _extract_emails_from_text(resp.text)
                    if found:
                        return found[0]
            except requests.RequestException:
                continue

    common_emails = _try_domain_emails(website, prefixes) if website else []
    if common_emails:
        return common_emails[0]

    email = find_email_from_maps_place(place_id)
    if email:
        return email

    email = find_email_advanced_search(business_name, phone, city)
    if email:
        return email

    try:
        search_query = f"{business_name} email iletişim"
        search_url = (
            f"https://www.google.com/search?q={requests.utils.quote(search_query)}"
        )
        resp = requests.get(
            search_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"}
        )
        if resp.status_code == 200:
            emails = _extract_emails_from_text(resp.text)
            if emails:
                return emails[0]
    except requests.RequestException:
        pass

    return None


def find_email_from_maps_place(place_id: str) -> str | None:
    if not place_id:
        return None
    try:
        url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(url, timeout=15, headers=headers)
        if resp.status_code != 200:
            return None

        emails = _extract_emails_from_text(resp.text)
        if emails:
            return emails[0]

        soup = BeautifulSoup(resp.text, "html.parser")
        mailto_links = soup.select('a[href^="mailto:"]')
        for link in mailto_links:
            email = link.get("href", "").replace("mailto:", "").strip()
            if email and "@" in email:
                return email
    except requests.RequestException:
        logger.warning("Could not fetch Maps place page for %s", place_id)
    except Exception as e:
        logger.warning("Error scraping Maps place %s: %s", place_id, e)
    return None


def find_email_advanced_search(business_name: str, phone: str | None, city: str | None) -> str | None:
    try:
        if phone:
            query = f'"{business_name}" "{phone}" email OR mail OR iletisim'
        else:
            query = f'"{business_name}" {city or ""} email OR mail OR iletisim'

        search_url = f"https://www.google.com/search?q={requests.utils.quote(query)}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(search_url, timeout=15, headers=headers)
        if resp.status_code != 200:
            return None

        emails = _extract_emails_from_text(resp.text)
        if emails:
            return emails[0]

        soup = BeautifulSoup(resp.text, "html.parser")
        links = []
        for a in soup.select("a[href^='/url?q=']"):
            href = a.get("href", "")
            match = re.search(r'/url\?q=([^&]+)', href)
            if match:
                url = match.group(1)
                if url.startswith("http") and "google" not in url.split("/")[2]:
                    links.append(url)

        for url in links[:5]:
            try:
                page_resp = requests.get(url, timeout=10, headers=headers)
                if page_resp.status_code == 200:
                    page_emails = _extract_emails_from_text(page_resp.text)
                    if page_emails:
                        return page_emails[0]
            except requests.RequestException:
                continue
    except requests.RequestException:
        pass
    except Exception as e:
        logger.warning("Error in advanced search for %s: %s", business_name, e)
    return None


def calculate_priority_score(business: dict[str, Any]) -> int:
    score = 0
    website_quality = business.get("website_quality", "none")

    if website_quality == "none":
        score += settings.SCORE_NO_WEBSITE
    elif website_quality in ("wix", "blogger", "poor", "wordpress_basic"):
        score += settings.SCORE_POOR_WEBSITE

    rating = business.get("rating", 0)
    if rating and rating >= 4.0:
        score += settings.SCORE_HIGH_RATING

    review_count = business.get("review_count", 0)
    if review_count >= 50:
        score += settings.SCORE_VERY_MANY_REVIEWS
    elif review_count >= 20:
        score += settings.SCORE_MANY_REVIEWS

    if business.get("email"):
        score += settings.SCORE_HAS_EMAIL

    return min(100, score)


def filter_and_rank(businesses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        contacted_ids = set(sheets_manager.get_all_contacted_place_ids())
    except Exception:
        logger.warning(
            "Could not fetch contacted list from Sheets, proceeding without dedup"
        )
        contacted_ids = set()

    filtered = []
    for b in businesses:
        pid = b.get("place_id")
        if pid and pid in contacted_ids:
            continue
        if b.get("priority_score", 0) < settings.MIN_PRIORITY_SCORE:
            continue
        filtered.append(b)

    filtered.sort(key=lambda x: x.get("priority_score", 0), reverse=True)
    return filtered


def _call_google_api(url: str, params: dict[str, Any]) -> dict[str, Any] | None:
    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()
            if data.get("status") == "OK":
                return data
            if data.get("status") == "OVER_QUERY_LIMIT":
                wait = 60 * (attempt + 1)
                logger.warning("Google Maps API quota exceeded. Waiting %ss...", wait)
                time.sleep(wait)
                continue
            if data.get("status") == "ZERO_RESULTS":
                return None
            logger.warning(
                "Google Maps API error: %s - %s",
                data.get("status"),
                data.get("error_message"),
            )
            return None
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))
                continue
            logger.error("Google Maps API request failed: %s", e)
            return None
    return None


def _get_place_details(place_id: str) -> dict[str, Any]:
    api_key = settings.GOOGLE_MAPS_API_KEY
    if not api_key:
        return {}
    try:
        url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {
            "place_id": place_id,
            "key": api_key,
            "fields": "website,formatted_phone_number,international_phone_number,name",
        }
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        if data.get("status") == "OK":
            return data.get("result", {})
    except requests.RequestException:
        logger.warning("Place Details API request failed for %s", place_id)
    except Exception as e:
        logger.warning("Error fetching place details for %s: %s", place_id, e)
    return {}


def _extract_business(
    place: dict[str, Any], city: str, business_type: str
) -> dict[str, Any]:
    place_id = place.get("place_id", "")
    details = _get_place_details(place_id)

    name = place.get("name", "")
    website = details.get("website") or place.get("website")
    phone = (
        details.get("formatted_phone_number")
        or details.get("international_phone_number")
        or place.get("formatted_phone_number")
        or place.get("international_phone_number")
    )

    business = {
        "place_id": place_id,
        "name": name,
        "type": business_type,
        "city": city,
        "address": place.get("formatted_address", ""),
        "phone": phone or "",
        "email": None,
        "website": website,
        "website_quality": "none",
        "maps_url": f"https://maps.google.com/?q=place_id:{place_id}",
        "rating": place.get("rating", 0),
        "review_count": place.get("user_ratings_total", 0),
        "priority_score": 0,
        "found_at": datetime.now().isoformat(),
    }

    if website:
        business["website_quality"] = check_website_quality(website)

    email = find_contact_email(name, website, phone, place_id, city)
    business["email"] = email
    business["priority_score"] = calculate_priority_score(business)

    return business


def _scrape_website_for_email(website: str, business_name: str) -> str | None:
    try:
        resp = requests.get(website, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        emails = _extract_emails_from_text(resp.text)
        if emails:
            return emails[0]
    except requests.RequestException:
        pass
    return None


def _extract_emails_from_text(text: str) -> list[str]:
    pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    emails = re.findall(pattern, text)
    seen = set()
    result = []
    for e in emails:
        e_lower = e.lower()
        if (
            e_lower not in seen
            and not e_lower.endswith(".png")
            and not e_lower.endswith(".jpg")
        ):
            seen.add(e_lower)
            result.append(e_lower)
    return result


def _try_domain_emails(website: str, prefixes: list[str]) -> list[str]:
    from urllib.parse import urlparse

    parsed = urlparse(website)
    domain = parsed.netloc or parsed.path
    domain = domain.replace("www.", "")
    results = []
    for prefix in prefixes:
        email = f"{prefix}@{domain}"
        results.append(email)
    return results


def _check_pagespeed_score(url: str) -> str:
    api_key = settings.GOOGLE_MAPS_API_KEY
    if not api_key:
        return "average"
    try:
        ps_url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
        params = {"url": url, "key": api_key, "strategy": "MOBILE"}
        resp = requests.get(ps_url, params=params, timeout=15)
        data = resp.json()
        score = (
            data.get("lighthouseResult", {})
            .get("categories", {})
            .get("performance", {})
            .get("score", 0)
        )
        score = int(score * 100) if isinstance(score, float) else 0
        if score < 50:
            return "poor"
        if score < 70:
            return "average"
        return "good"
    except Exception:
        return "average"
