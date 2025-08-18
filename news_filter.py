"""
news_filter.py
- Fetch high-impact (red) economic events from ForexFactory
- Convert times to UTC based on provided timezone (e.g., Europe/Paris)
- Provide query: is trading blocked for a given symbol now?
Note: ForexFactory markup can change. This parser is best-effort.
"""

from __future__ import annotations
import os, time, pytz, requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from datetime import datetime, timedelta

FF_URL = "https://www.forexfactory.com/calendar?week=this"
TIMEZONE = os.getenv("TIMEZONE", "Europe/Paris")
BLOCK_BEFORE = int(os.getenv("NEWS_BLOCK_BEFORE_MINUTES", "60"))
BLOCK_AFTER  = int(os.getenv("NEWS_BLOCK_AFTER_MINUTES", "60"))
FETCH_INTERVAL_MIN = int(os.getenv("NEWS_FETCH_INTERVAL_MINUTES", "10"))

_cache = {"ts": 0, "events": []}

SYMBOL_CCY_MAP = {
    "XAUUSD": ["USD"],
    "EURUSD": ["EUR", "USD"],
    "GBPUSD": ["GBP", "USD"],
    "BTCUSD": ["USD"],
}

def _fetch_html():
    headers = {"User-Agent": "Mozilla/5.0 (TradingBot; +https://example.local)"}
    r = requests.get(FF_URL, headers=headers, timeout=15)
    r.raise_for_status()
    return r.text

def _parse_events(html: str):
    soup = BeautifulSoup(html, "lxml")
    events = []
    for row in soup.select("tr.calendar__row"):
        impact_el = row.select_one('[data-impact], .calendar__impact')
        if not impact_el:
            continue
        impact_text = (impact_el.get("data-impact") or impact_el.get_text() or "").strip().lower()
        if "high" not in impact_text and "folder-red" not in impact_text and "impact--high" not in impact_el.get("class", []):
            continue

        ccy_el = row.select_one(".calendar__currency, td.currency, [data-symbol]")
        currency = (ccy_el.get_text() if ccy_el else "").strip().upper()
        if not currency:
            icon = row.select_one(".calendar__flag > img")
            if icon and icon.get("title"):
                currency = icon["title"].split()[-1].upper()

        title_el = row.select_one(".calendar__event-title, .calendar__event")
        title = (title_el.get_text() if title_el else "").strip()

        date_group = row.find_previous("tr", class_="calendar__row--day")
        date_text = (date_group.get_text() if date_group else "").strip()
        time_el = row.select_one(".calendar__time")
        time_text = (time_el.get_text() if time_el else "").strip()

        local_tz = pytz.timezone(TIMEZONE)
        now_local = datetime.now(local_tz)
        base_str = f"{date_text} {time_text}".strip() if date_text else time_text
        try:
            when_local = dateparser.parse(base_str, default=now_local.replace(hour=0, minute=0, second=0, microsecond=0))
        except Exception:
            when_local = now_local

        if when_local.tzinfo is None:
            when_local = local_tz.localize(when_local)
        when_utc = when_local.astimezone(pytz.UTC)

        events.append({
            "currency": currency or "N/A",
            "impact": "High",
            "title": title or "High Impact Event",
            "time_utc": when_utc,
            "time_local": when_local,
        })
    return events

def refresh_events(force: bool=False):
    global _cache
    now = time.time()
    if not force and (now - _cache["ts"] < FETCH_INTERVAL_MIN*60) and _cache["events"]:
        return _cache["events"]
    try:
        html = _fetch_html()
        events = _parse_events(html)
        _cache = {"ts": now, "events": events}
        return events
    except Exception:
        return _cache["events"]

def relevant_currencies(symbol: str):
    return SYMBOL_CCY_MAP.get(symbol.upper(), ["USD"])

def is_blocked_now(symbol: str, now_utc: datetime|None=None):
    evs = refresh_events()
    now_utc = now_utc or datetime.utcnow().replace(tzinfo=pytz.UTC)
    ccys = set(relevant_currencies(symbol))

    for ev in evs:
        if ev["currency"] not in ccys:
            continue
        start = ev["time_utc"] - timedelta(minutes=BLOCK_BEFORE)
        end   = ev["time_utc"] + timedelta(minutes=BLOCK_AFTER)
        if start <= now_utc <= end:
            return True, f"NO_TRADE: {ev['title']} ({ev['currency']}) window"
    return False, "OK"

def next_blocking_event(symbol: str, now_utc: datetime|None=None):
    evs = refresh_events()
    now_utc = now_utc or datetime.utcnow().replace(tzinfo=pytz.UTC)
    ccys = set(relevant_currencies(symbol))
    soonest = None
    for ev in evs:
        if ev["currency"] not in ccys:
            continue
        if ev["time_utc"] >= now_utc:
            if soonest is None or ev["time_utc"] < soonest["time_utc"]:
                soonest = ev
    return soonest
