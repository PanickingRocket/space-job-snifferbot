"""
Space Job Tracker
Monitora le career page di aziende space e notifica su Telegram le nuove posizioni.

ATS supportati: greenhouse, lever, smartrecruiters, workday,
                workable, personio, bamboohr, recruitee, pinpoint, generic
"""

import json
import os
import sys
import hashlib
import requests
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup

# ─── Config ───────────────────────────────────────────────────────────────────

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SEEN_JOBS_FILE   = "seen_jobs.json"
COMPANIES_FILE   = "companies.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ─── Telegram ─────────────────────────────────────────────────────────────────

def send_telegram(message: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[WARN] Variabili Telegram non configurate.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"[ERROR] Telegram: {e}")


def send_new_job_notification(company: str, title: str, url: str) -> None:
    msg = (
        f"🚀 <b>Nuova posizione trovata!</b>\n\n"
        f"🏢 <b>Azienda:</b> {company}\n"
        f"💼 <b>Ruolo:</b> {title}\n"
        f"🔗 <a href='{url}'>Apri annuncio</a>\n\n"
        f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )
    send_telegram(msg)


def send_summary(new_jobs: list) -> None:
    if not new_jobs:
        return
    lines = [f"📋 <b>Riepilogo — {len(new_jobs)} nuova/e posizione/i:</b>\n"]
    for j in new_jobs:
        lines.append(f"• {j['company']}: <a href='{j['url']}'>{j['title']}</a>")
    send_telegram("\n".join(lines))


# ─── Persistenza ──────────────────────────────────────────────────────────────

def load_seen_jobs() -> dict:
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_seen_jobs(seen: dict) -> None:
    with open(SEEN_JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, indent=2, ensure_ascii=False)


def load_companies() -> list:
    with open(COMPANIES_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return [e for e in data if e.get("name") and not e.get("_disabled")]


def make_job_id(title: str, url: str) -> str:
    return hashlib.md5(f"{title.strip().lower()}|{url.strip()}".encode()).hexdigest()


# ─── Filtro keywords ──────────────────────────────────────────────────────────

def matches_keywords(title: str, keywords: list) -> bool:
    if not keywords:
        return True
    t = title.lower()
    return any(kw.lower() in t for kw in keywords)


# ─── Scrapers ─────────────────────────────────────────────────────────────────

def scrape_greenhouse(company_id: str, keywords: list) -> list:
    url = f"https://boards-api.greenhouse.io/v1/boards/{company_id}/jobs"
    try:
        r = requests.get(url, timeout=15, headers=HEADERS)
        r.raise_for_status()
        jobs = r.json().get("jobs", [])
        return [
            {"title": j["title"], "url": j["absolute_url"]}
            for j in jobs if matches_keywords(j["title"], keywords)
        ]
    except Exception as e:
        print(f"    [ERROR] Greenhouse ({company_id}): {e}")
        return []


def scrape_lever(company_id: str, keywords: list) -> list:
    url = f"https://api.lever.co/v0/postings/{company_id}?mode=json"
    try:
        r = requests.get(url, timeout=15, headers=HEADERS)
        r.raise_for_status()
        jobs = r.json()
        return [
            {"title": j["text"], "url": j["hostedUrl"]}
            for j in jobs if matches_keywords(j["text"], keywords)
        ]
    except Exception as e:
        print(f"    [ERROR] Lever ({company_id}): {e}")
        return []


def scrape_smartrecruiters(company_id: str, keywords: list) -> list:
    url = f"https://api.smartrecruiters.com/v1/companies/{company_id}/postings?limit=100"
    try:
        r = requests.get(url, timeout=15, headers=HEADERS)
        r.raise_for_status()
        items = r.json().get("content", [])
        results = []
        for j in items:
            title = j.get("name", "")
            jid = j.get("id", "")
            job_url = f"https://jobs.smartrecruiters.com/{company_id}/{jid}"
            if matches_keywords(title, keywords):
                results.append({"title": title, "url": job_url})
        return results
    except Exception as e:
        print(f"    [ERROR] SmartRecruiters ({company_id}): {e}")
        return []


def scrape_workday(base_url: str, keywords: list) -> list:
    try:
        r = requests.get(base_url, timeout=20, headers=HEADERS)
        soup = BeautifulSoup(r.text, "html.parser")
        jobs = []
        for a in soup.find_all("a", {"data-automation-id": "jobTitle"}):
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if href and not href.startswith("http"):
                href = urljoin(base_url, href)
            if title and matches_keywords(title, keywords):
                jobs.append({"title": title, "url": href})
        return jobs
    except Exception as e:
        print(f"    [ERROR] Workday ({base_url}): {e}")
        return []


def scrape_workable(company_id: str, keywords: list) -> list:
    url = f"https://apply.workable.com/api/v3/accounts/{company_id}/jobs"
    try:
        r = requests.post(url, json={"limit": 100, "offset": 0}, timeout=15, headers=HEADERS)
        r.raise_for_status()
        jobs = r.json().get("results", [])
        results = []
        for j in jobs:
            title = j.get("title", "")
            slug = j.get("shortcode", "")
            job_url = f"https://apply.workable.com/{company_id}/j/{slug}/"
            if matches_keywords(title, keywords):
                results.append({"title": title, "url": job_url})
        return results
    except Exception as e:
        print(f"    [ERROR] Workable ({company_id}): {e}")
        return []


def scrape_personio(company_slug: str, keywords: list) -> list:
    url = f"https://{company_slug}.jobs.personio.de/api/v1/positions"
    try:
        r = requests.get(url, timeout=15, headers={**HEADERS, "Accept": "application/json"})
        r.raise_for_status()
        jobs = r.json()
        results = []
        for j in jobs:
            title = j.get("name", "")
            jid = j.get("id", "")
            job_url = f"https://{company_slug}.jobs.personio.de/job/{jid}"
            if matches_keywords(title, keywords):
                results.append({"title": title, "url": job_url})
        return results
    except Exception as e:
        print(f"    [ERROR] Personio ({company_slug}): {e}")
        return []


def scrape_bamboohr(company_slug: str, keywords: list) -> list:
    url = f"https://{company_slug}.bamboohr.com/careers/list"
    try:
        r = requests.get(url, timeout=15, headers={**HEADERS, "Accept": "application/json"})
        r.raise_for_status()
        jobs = r.json().get("result", [])
        results = []
        for j in jobs:
            title = j.get("jobOpeningName", "")
            jid = j.get("id", "")
            job_url = f"https://{company_slug}.bamboohr.com/careers/{jid}"
            if matches_keywords(title, keywords):
                results.append({"title": title, "url": job_url})
        return results
    except Exception as e:
        print(f"    [ERROR] BambooHR ({company_slug}): {e}")
        return []


def scrape_recruitee(company_slug: str, keywords: list) -> list:
    url = f"https://{company_slug}.recruitee.com/api/offers/"
    try:
        r = requests.get(url, timeout=15, headers=HEADERS)
        r.raise_for_status()
        jobs = r.json().get("offers", [])
        results = []
        for j in jobs:
            title = j.get("title", "")
            slug = j.get("slug", "")
            job_url = f"https://{company_slug}.recruitee.com/o/{slug}"
            if matches_keywords(title, keywords):
                results.append({"title": title, "url": job_url})
        return results
    except Exception as e:
        print(f"    [ERROR] Recruitee ({company_slug}): {e}")
        return []


def scrape_pinpoint(company_slug: str, keywords: list) -> list:
    url = f"https://{company_slug}.pinpointhq.com/api/v1/jobs"
    try:
        r = requests.get(url, timeout=15, headers={**HEADERS, "Accept": "application/json"})
        r.raise_for_status()
        jobs = r.json().get("data", [])
        results = []
        for j in jobs:
            attrs = j.get("attributes", {})
            title = attrs.get("title", "")
            job_url = attrs.get("job_ad_url", f"https://{company_slug}.pinpointhq.com")
            if matches_keywords(title, keywords):
                results.append({"title": title, "url": job_url})
        return results
    except Exception as e:
        print(f"    [ERROR] Pinpoint ({company_slug}): {e}")
        return []


def scrape_generic(entry: dict) -> list:
    url       = entry["url"]
    selector  = entry.get("selector", "")
    keywords  = entry.get("keywords", [])
    base_url  = entry.get("base_url", "")
    title_sel = entry.get("title_selector")
    link_sel  = entry.get("link_selector")

    if not selector or selector == "TODO":
        print(f"    [SKIP] Selector non configurato — visita manualmente: {url}")
        return []

    try:
        r = requests.get(url, timeout=20, headers=HEADERS)
        soup = BeautifulSoup(r.text, "html.parser")
        jobs = []
        for el in soup.select(selector):
            title = (el.select_one(title_sel).get_text(strip=True)
                     if title_sel and el.select_one(title_sel)
                     else el.get_text(strip=True))
            if link_sel:
                l_el = el.select_one(link_sel)
                href = l_el.get("href", "") if l_el else ""
            else:
                href = el.get("href", "") if el.name == "a" else ""
            if href and not href.startswith("http") and base_url:
                href = base_url.rstrip("/") + "/" + href.lstrip("/")
            if not href:
                href = url
            if title and matches_keywords(title, keywords):
                jobs.append({"title": title, "url": href})
        return jobs
    except Exception as e:
        print(f"    [ERROR] Generic ({url}): {e}")
        return []


# ─── Dispatcher ───────────────────────────────────────────────────────────────

def fetch_jobs(entry: dict) -> list:
    ats      = entry.get("ats", "generic").lower()
    keywords = entry.get("keywords", [])
    dispatch = {
        "greenhouse":     lambda: scrape_greenhouse(entry["company_id"], keywords),
        "lever":          lambda: scrape_lever(entry["company_id"], keywords),
        "smartrecruiters":lambda: scrape_smartrecruiters(entry["company_id"], keywords),
        "workday":        lambda: scrape_workday(entry["url"], keywords),
        "workable":       lambda: scrape_workable(entry["company_id"], keywords),
        "personio":       lambda: scrape_personio(entry["company_id"], keywords),
        "bamboohr":       lambda: scrape_bamboohr(entry["company_id"], keywords),
        "recruitee":      lambda: scrape_recruitee(entry["company_id"], keywords),
        "pinpoint":       lambda: scrape_pinpoint(entry["company_id"], keywords),
    }
    return dispatch.get(ats, lambda: scrape_generic(entry))()


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Avvio controllo jobs...")
    companies = load_companies()
    seen_jobs = load_seen_jobs()
    all_new   = []

    print(f"Aziende da controllare: {len(companies)}\n")

    for entry in companies:
        name = entry.get("name", "?")
        print(f"  → {name}")
        current_jobs = fetch_jobs(entry)
        print(f"     {len(current_jobs)} posizioni trovate")

        company_seen = seen_jobs.get(name, {})
        for job in current_jobs:
            jid = make_job_id(job["title"], job["url"])
            if jid not in company_seen:
                print(f"     🆕 {job['title']}")
                company_seen[jid] = {"title": job["title"], "url": job["url"],
                                     "found": datetime.now().isoformat()}
                send_new_job_notification(name, job["title"], job["url"])
                all_new.append({"company": name, **job})

        seen_jobs[name] = company_seen

    save_seen_jobs(seen_jobs)
    if all_new:
        send_summary(all_new)

    print(f"\n✅ Completato. {len(all_new)} nuove posizioni trovate in totale.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
