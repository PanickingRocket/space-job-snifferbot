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


def load_companies() -> tuple[list, list, list]:
    """Ritorna (companies, global_keywords, global_exclude_keywords)."""
    with open(COMPANIES_FILE, encoding="utf-8") as f:
        data = json.load(f)

    global_keywords = []
    global_exclude  = []
    companies = []
    for entry in data:
        if "_global_keywords" in entry:
            global_keywords = entry["_global_keywords"]
        if "_global_exclude_keywords" in entry:
            global_exclude = entry["_global_exclude_keywords"]
        if entry.get("name") and not entry.get("_disabled"):
            companies.append(entry)
    return companies, global_keywords, global_exclude


def make_job_id(title: str, url: str) -> str:
    return hashlib.md5(f"{title.strip().lower()}|{url.strip()}".encode()).hexdigest()


# ─── Filtro keywords ──────────────────────────────────────────────────────────

def matches_keywords(title: str, keywords: list, exclude: list = []) -> bool:
    """
    Ritorna True se il titolo contiene almeno una keyword E non contiene
    nessuna delle parole da escludere.
    keywords vuota = nessun filtro inclusivo (tutte le posizioni passano).
    exclude vuota = nessun filtro esclusivo.
    """
    t = title.lower()
    # Prima controlla le esclusioni — se matcha una, scarta subito
    if any(ex.lower() in t for ex in exclude):
        return False
    # Poi applica il filtro inclusivo
    if not keywords:
        return True
    return any(kw.lower() in t for kw in keywords)


def get_effective_keywords(entry: dict, global_keywords: list, global_exclude: list) -> tuple:
    """
    Ritorna (keywords_effettive, exclude_effettive) per questa azienda.
    Le keywords per-azienda si AGGIUNGONO alle globali.
    Le exclude per-azienda si AGGIUNGONO alle globali.
    Con 'override_global_keywords': true si usano solo quelle per-azienda.
    """
    company_kws  = entry.get("keywords", [])
    company_excl = entry.get("exclude_keywords", [])

    if entry.get("override_global_keywords"):
        return company_kws, company_excl

    # Unione keywords senza duplicati
    merged_kws = list(global_keywords)
    for kw in company_kws:
        if kw not in merged_kws:
            merged_kws.append(kw)

    # Unione exclude senza duplicati
    merged_excl = list(global_exclude)
    for ex in company_excl:
        if ex not in merged_excl:
            merged_excl.append(ex)

    return merged_kws, merged_excl


# ─── Scrapers ─────────────────────────────────────────────────────────────────

def scrape_greenhouse(company_id: str, keywords: list, exclude: list) -> list:
    url = f"https://boards-api.greenhouse.io/v1/boards/{company_id}/jobs"
    try:
        r = requests.get(url, timeout=15, headers=HEADERS)
        r.raise_for_status()
        jobs = r.json().get("jobs", [])
        return [
            {"title": j["title"], "url": j["absolute_url"]}
            for j in jobs if matches_keywords(j["title"], keywords, exclude)
        ]
    except Exception as e:
        print(f"    [ERROR] Greenhouse ({company_id}): {e}")
        return []


def scrape_lever(company_id: str, keywords: list, exclude: list) -> list:
    url = f"https://api.lever.co/v0/postings/{company_id}?mode=json"
    try:
        r = requests.get(url, timeout=15, headers=HEADERS)
        r.raise_for_status()
        jobs = r.json()
        return [
            {"title": j["text"], "url": j["hostedUrl"]}
            for j in jobs if matches_keywords(j["text"], keywords, exclude)
        ]
    except Exception as e:
        print(f"    [ERROR] Lever ({company_id}): {e}")
        return []


def scrape_smartrecruiters(company_id: str, keywords: list, exclude: list) -> list:
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
            if matches_keywords(title, keywords, exclude):
                results.append({"title": title, "url": job_url})
        return results
    except Exception as e:
        print(f"    [ERROR] SmartRecruiters ({company_id}): {e}")
        return []


def scrape_workday(base_url: str, keywords: list, exclude: list) -> list:
    try:
        r = requests.get(base_url, timeout=20, headers=HEADERS)
        soup = BeautifulSoup(r.text, "html.parser")
        jobs = []
        for a in soup.find_all("a", {"data-automation-id": "jobTitle"}):
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if href and not href.startswith("http"):
                href = urljoin(base_url, href)
            if title and matches_keywords(title, keywords, exclude):
                jobs.append({"title": title, "url": href})
        return jobs
    except Exception as e:
        print(f"    [ERROR] Workday ({base_url}): {e}")
        return []


def scrape_workable(company_id: str, keywords: list, exclude: list) -> list:
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
            if matches_keywords(title, keywords, exclude):
                results.append({"title": title, "url": job_url})
        return results
    except Exception as e:
        print(f"    [ERROR] Workable ({company_id}): {e}")
        return []


def scrape_personio(company_slug: str, keywords: list, exclude: list) -> list:
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
            if matches_keywords(title, keywords, exclude):
                results.append({"title": title, "url": job_url})
        return results
    except Exception as e:
        print(f"    [ERROR] Personio ({company_slug}): {e}")
        return []


def scrape_bamboohr(company_slug: str, keywords: list, exclude: list) -> list:
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
            if matches_keywords(title, keywords, exclude):
                results.append({"title": title, "url": job_url})
        return results
    except Exception as e:
        print(f"    [ERROR] BambooHR ({company_slug}): {e}")
        return []


def scrape_recruitee(company_slug: str, keywords: list, exclude: list) -> list:
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
            if matches_keywords(title, keywords, exclude):
                results.append({"title": title, "url": job_url})
        return results
    except Exception as e:
        print(f"    [ERROR] Recruitee ({company_slug}): {e}")
        return []


def scrape_pinpoint(company_slug: str, keywords: list, exclude: list) -> list:
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
            if matches_keywords(title, keywords, exclude):
                results.append({"title": title, "url": job_url})
        return results
    except Exception as e:
        print(f"    [ERROR] Pinpoint ({company_slug}): {e}")
        return []


def scrape_factorial(company_slug: str, tld: str, keywords: list, exclude: list) -> list:
    """Factorial HR — usato da D-Orbit (factorial.it), Opus Aerospace (factorial.fr), ecc."""
    base = f"https://{company_slug}.{tld}"
    try:
        r = requests.get(base, timeout=20, headers=HEADERS)
        soup = BeautifulSoup(r.text, "html.parser")
        jobs = []
        # I link alle posizioni hanno sempre /job_posting/ nel path
        for a in soup.find_all("a", href=lambda h: h and "/job_posting/" in h):
            title = a.get_text(strip=True)
            href = a["href"]
            if not href.startswith("http"):
                href = base + href
            # Escludi il link "Open application" generico
            if title and title.lower() != "apply now" and matches_keywords(title, keywords, exclude):
                jobs.append({"title": title, "url": href})
        return jobs
    except Exception as e:
        print(f"    [ERROR] Factorial ({company_slug}.{tld}): {e}")
        return []


def scrape_generic(entry: dict, keywords: list, exclude: list) -> list:
    url       = entry["url"]
    selector  = entry.get("selector", "")
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
            if title and matches_keywords(title, keywords, exclude):
                jobs.append({"title": title, "url": href})
        return jobs
    except Exception as e:
        print(f"    [ERROR] Generic ({url}): {e}")
        return []


# ─── Dispatcher ───────────────────────────────────────────────────────────────

def fetch_jobs(entry: dict, keywords: list, exclude: list) -> list:
    ats = entry.get("ats", "generic").lower()
    dispatch = {
        "greenhouse":      lambda: scrape_greenhouse(entry["company_id"], keywords, exclude),
        "lever":           lambda: scrape_lever(entry["company_id"], keywords, exclude),
        "smartrecruiters": lambda: scrape_smartrecruiters(entry["company_id"], keywords, exclude),
        "workday":         lambda: scrape_workday(entry["url"], keywords, exclude),
        "workable":        lambda: scrape_workable(entry["company_id"], keywords, exclude),
        "personio":        lambda: scrape_personio(entry["company_id"], keywords, exclude),
        "bamboohr":        lambda: scrape_bamboohr(entry["company_id"], keywords, exclude),
        "recruitee":       lambda: scrape_recruitee(entry["company_id"], keywords, exclude),
        "pinpoint":        lambda: scrape_pinpoint(entry["company_id"], keywords, exclude),
        "factorial":       lambda: scrape_factorial(entry["company_slug"], entry.get("tld", "factorialhr.com"), keywords, exclude),
    }
    return dispatch.get(ats, lambda: scrape_generic(entry, keywords, exclude))()


# ─── Deduplication intelligente ───────────────────────────────────────────────
#
# LOGICA:
#   seen_jobs[company] = { job_id: { title, url, first_seen, last_seen } }
#
#   Ad ogni run:
#   1. Recupera i job ATTUALMENTE online per questa azienda
#   2. Calcola i job_id correnti
#   3. Notifica solo i job che NON erano in seen_jobs
#   4. RIMUOVE da seen_jobs i job che non sono più online
#      → se un job viene rimosso e ripostato in futuro, verrà notificato di nuovo ✓
#   5. Aggiorna last_seen per i job ancora online

def update_seen_and_find_new(
    company_seen: dict, current_jobs: list
) -> tuple[dict, list]:
    """
    Ritorna (company_seen aggiornato, lista di job nuovi).
    """
    current_ids = {}
    for job in current_jobs:
        jid = make_job_id(job["title"], job["url"])
        current_ids[jid] = job

    new_jobs = []
    now = datetime.now().isoformat()

    # Trova i nuovi
    for jid, job in current_ids.items():
        if jid not in company_seen:
            new_jobs.append(job)
            company_seen[jid] = {
                "title":      job["title"],
                "url":        job["url"],
                "first_seen": now,
                "last_seen":  now,
            }
        else:
            # Aggiorna last_seen per i job già noti ancora online
            company_seen[jid]["last_seen"] = now

    # Rimuovi i job che non sono più online
    # (così se ricompaiono in futuro verranno notificati come nuovi)
    stale_ids = [jid for jid in company_seen if jid not in current_ids]
    for jid in stale_ids:
        removed = company_seen.pop(jid)
        print(f"    ↩ Rimossa posizione non più online: {removed['title']}")

    return company_seen, new_jobs


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Avvio controllo jobs...")

    companies, global_keywords, global_exclude = load_companies()
    seen_jobs = load_seen_jobs()
    all_new   = []

    print(f"Aziende da controllare: {len(companies)}")
    print(f"Keywords globali attive: {len(global_keywords)}")
    print(f"Exclude globali attive:  {len(global_exclude)}\n")

    for entry in companies:
        name             = entry.get("name", "?")
        keywords, exclude = get_effective_keywords(entry, global_keywords, global_exclude)
        print(f"  → {name}")

        current_jobs = fetch_jobs(entry, keywords, exclude)
        print(f"     {len(current_jobs)} posizioni trovate (dopo filtro keywords)")

        company_seen = seen_jobs.get(name, {})
        company_seen, new_jobs = update_seen_and_find_new(company_seen, current_jobs)

        for job in new_jobs:
            print(f"     🆕 {job['title']}")
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
