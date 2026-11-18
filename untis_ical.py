#!/usr/bin/env python3
"""WebUntis public student timetable -> subscribable iCalendar (Python stdlib only).

Uses undocumented public WebUntis endpoints; availability varies by school.
No credentials are collected and no private endpoints are accessed.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SERVER = os.getenv("UNTIS_SERVER", "igs-hannover-linden.webuntis.com")
SCHOOL = os.getenv("UNTIS_SCHOOL", "igs-hannover-linden")
STUDENT_ID = int(os.getenv("UNTIS_STUDENT_ID", "8279"))
DAYS_PAST = int(os.getenv("UNTIS_DAYS_PAST", "7"))
DAYS_FUTURE = int(os.getenv("UNTIS_DAYS_FUTURE", "63"))
OUTPUT = Path(os.getenv("UNTIS_OUTPUT", "public/stundenplan.ics"))
TZ = ZoneInfo("Europe/Berlin")
BASE = f"https://{SERVER}/WebUntis"
USER_AGENT = "Untis-Apple-Kalender/1.0 (public timetable; low frequency)"


@dataclass(frozen=True)
class Period:
    start: datetime
    end: datetime
    subject: str
    room: str = ""
    teachers: str = ""
    notes: str = ""
    cancelled: bool = False
    changed: bool = False
    ident: str = ""


class UntisError(Exception):
    pass


def fetch_json(url: str, params: dict, *, headers: dict | None = None) -> dict:
    url += "?" + urllib.parse.urlencode(params)
    cookies = "_" + base64.b64encode(SCHOOL.encode()).decode()
    request_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "anonymous-school": SCHOOL,
        "Cookie": f"schoolname={cookies}",
    }
    if headers:
        request_headers.update(headers)
    req = urllib.request.Request(url, headers=request_headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read(5_000_000)
    except urllib.error.HTTPError as exc:
        raise UntisError(f"HTTP {exc.code} an {url.split('?')[0]}") from exc
    except urllib.error.URLError as exc:
        raise UntisError(f"Verbindungsfehler: {exc.reason}") from exc
    try:
        return json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise UntisError("Server lieferte keine JSON-Stundenplandaten") from exc


def dparse(value) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, int) or (isinstance(value, str) and value.isdigit() and len(value) == 8):
        return datetime.strptime(str(value), "%Y%m%d").date()
    return date.fromisoformat(str(value)[:10])


def tparse(value) -> dtime:
    if isinstance(value, dtime):
        return value
    if isinstance(value, (int, float)):
        n = int(value)
        return dtime(n // 100, n % 100)
    value = str(value)
    if value.isdigit():
        return tparse(int(value))
    return dtime.fromisoformat(value)


def dtparse(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=TZ)
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=TZ)


def names_from_positions(entry: dict, kind: str) -> str:
    matches: list[str] = []
    for i in range(1, 8):
        for obj in entry.get(f"position{i}") or []:
            current = obj.get("current") or {}
            if current.get("type") != kind:
                continue
            val = current.get("shortName") or current.get("longName") or current.get("displayName")
            if val and val not in matches:
                matches.append(str(val))
    return ", ".join(matches)


def parse_rest(data: dict) -> list[Period]:
    """Parse public view/v1/timetable/entries, including substitutions/cancellations."""
    if not isinstance(data, dict) or "days" not in data:
        raise UntisError("REST-Antwort ohne 'days' – möglicherweise keine öffentliche Freigabe")
    output = []
    for day in data["days"]:
        for entry in day.get("gridEntries", []):
            duration = entry.get("duration") or {}
            if not duration.get("start") or not duration.get("end"):
                continue
            start = dtparse(duration["start"])
            end = dtparse(duration["end"])
            if end <= start:
                continue
            status = str(entry.get("status", "")).upper()
            cancelled = status in {"CANCEL", "CANCELLED", "CANCELED"}
            changed = bool(status and status not in {"REGULAR", "NORMAL", "STANDARD"})
            subject = names_from_positions(entry, "SUBJECT") or "Unterricht"
            room = names_from_positions(entry, "ROOM")
            teachers = names_from_positions(entry, "TEACHER")
            notes = []
            if entry.get("lessonInfo"):
                notes.append(str(entry["lessonInfo"]))
            if entry.get("substitutionText"):
                notes.append(str(entry["substitutionText"]))
            for item in entry.get("texts", []):
                if isinstance(item, dict) and item.get("text"):
                    value = str(item["text"])
                    if value not in notes:
                        notes.append(value)
            ids = entry.get("ids") or []
            event_id = str(ids[0]) if ids else ""
            output.append(Period(start, end, subject, room, teachers,
                                 " | ".join(notes), cancelled, changed, event_id))
    return output


def parse_legacy(data: dict) -> list[Period]:
    """Parse api/public/timetable/weekly/data (legacy fallback)."""
    core = (data.get("data") or {}).get("result") or {}
    if "error" in (data.get("data") or {}):
        raise UntisError(f"Untis-Fehler: {(data['data']['error'])!s}")
    content = core.get("data") or {}
    if "elementPeriods" not in content:
        raise UntisError("Legacy-Antwort ohne 'elementPeriods'")
    catalogue = {
        (int(e.get("type", 0)), int(e.get("id", 0))):
        e.get("name") or e.get("displayname") or e.get("longName") or ""
        for e in content.get("elements", []) if isinstance(e, dict)
    }
    result = []
    for elements in content["elementPeriods"].values():
        for entry in elements:
            start_day = dparse(entry["date"])
            start = datetime.combine(start_day, tparse(entry["startTime"]), TZ)
            end = datetime.combine(start_day, tparse(entry["endTime"]), TZ)
            if end <= start:
                continue
            def collect(kind: int) -> str:
                values = []
                for elem in entry.get("elements", []):
                    if int(elem.get("type", 0)) != kind or elem.get("missing"):
                        continue
                    name = catalogue.get((kind, int(elem.get("id", 0))), "")
                    if name and name not in values:
                        values.append(name)
                return ", ".join(values)
            status = str(entry.get("cellState", "")).upper()
            code = str(entry.get("code", "")).upper()
            cancelled = status in {"CANCEL", "CANCELLED", "CANCELED"} or code == "CANCELLED"
            changed = status not in {"", "STANDARD"}
            result.append(Period(
                start, end, collect(3) or "Unterricht", collect(4), collect(2),
                " | ".join(str(entry.get(k)) for k in ("periodText", "substText", "lessonText") if entry.get(k)),
                cancelled, changed, str(entry.get("id") or "")
            ))
    return result


def week_starts(begin: date, end: date):
    monday = begin - timedelta(days=begin.weekday())
    while monday <= end:
        yield monday
        monday += timedelta(days=7)


def fetch_week(monday: date) -> tuple[list[Period], str]:
    rest = BASE + "/api/rest/view/v1/timetable/entries"
    query = {
        "start": monday.isoformat(),
        "end": (monday + timedelta(days=6)).isoformat(),
        "format": "2",
        "resourceType": "STUDENT",
        "resources": str(STUDENT_ID),
        "timetableType": "STANDARD",
        "layout": "START_TIME",
    }
    problems = []
    for fmt in ("2", None):
        params = dict(query)
        if fmt is None:
            params.pop("format")
        try:
            parsed = parse_rest(fetch_json(rest, params))
            return parsed, "REST"
        except (UntisError, ValueError, TypeError, KeyError) as exc:
            problems.append(f"REST: {exc}")
    legacy = BASE + "/api/public/timetable/weekly/data"
    try:
        data = fetch_json(legacy, {
            "elementType": 5,
            "elementId": STUDENT_ID,
            "date": monday.isoformat(),
            "formatId": 1,
        })
        return parse_legacy(data), "Legacy"
    except (UntisError, ValueError, TypeError, KeyError) as exc:
        problems.append(f"Legacy: {exc}")
    raise UntisError("; ".join(problems))


def esc(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("\r\n", "\n").replace("\n", "\\n").replace("\r", "\\n").replace(",", "\\,").replace(";", "\\;")


def fold(line: str) -> list[str]:
    """Fold RFC 5545 lines at 75 OCTETS (not characters)."""
    chunks = []
    current = ""
    size = 0
    for char in line:
        byte_len = len(char.encode("utf-8"))
        if size + byte_len > 75:
            chunks.append(current)
            current = " "
            size = 1
        current += char
        size += byte_len
    if current:
        chunks.append(current)
    return chunks


def utc_format(local_dt: datetime) -> str:
    return local_dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def make_ics(periods: list[Period], *, clock: datetime | None = None) -> str:
    stamp = (clock or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Untis Apple Kalender IGS Linden//DE",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:IGS Linden – Stundenplan",
        "X-WR-TIMEZONE:Europe/Berlin", "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
        "X-PUBLISHED-TTL:PT6H",
    ]
    seen = set()
    for item in sorted(periods, key=lambda p: (p.start, p.subject, p.ident)):
        # A stable UID for period updates; retain identity when subject/room changes.
        raw_id = f"{STUDENT_ID}:{item.start.date().isoformat()}:{item.start.strftime('%H%M')}:{item.ident or item.subject}"
        uid = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:32] + "@untis-igs-linden"
        if uid in seen:
            continue
        seen.add(uid)
        title = ("Entfällt: " if item.cancelled else "") + item.subject
        if item.changed and not item.cancelled:
            title += " (Änderung)"
        description = []
        if item.teachers:
            description.append("Lehrkraft: " + item.teachers)
        if item.room:
            description.append("Raum: " + item.room)
        if item.notes:
            description.append(item.notes)
        description.append("Quelle: WebUntis / IGS Linden")
        fields = [
            "BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{stamp}",
            f"DTSTART:{utc_format(item.start)}", f"DTEND:{utc_format(item.end)}",
            f"SUMMARY:{esc(title)}", "STATUS:CONFIRMED",
            f"TRANSP:{'TRANSPARENT' if item.cancelled else 'OPAQUE'}",
            f"DESCRIPTION:{esc(chr(10).join(description))}",
        ]
        if item.room:
            fields.append(f"LOCATION:{esc(item.room)}")
        fields.append("END:VEVENT")
        lines.extend(fields)
    lines.append("END:VCALENDAR")
    folded = []
    for line in lines:
        folded.extend(fold(line))
    return "\r\n".join(folded) + "\r\n"


def main() -> int:
    if not SERVER.endswith(".webuntis.com") or "/" in SERVER:
        print("Ungültiger WebUntis-Server", file=sys.stderr)
        return 1
    today = datetime.now(TZ).date()
    start = today - timedelta(days=DAYS_PAST)
    end = today + timedelta(days=DAYS_FUTURE)
    all_periods: list[Period] = []
    failed: list[str] = []
    successes = 0
    for i, monday in enumerate(week_starts(start, end)):
        if i:
            time.sleep(0.35)  # rate limit
        try:
            week_periods, source = fetch_week(monday)
            all_periods.extend(week_periods)
            successes += 1
            print(f"{monday}: {len(week_periods)} Stunden ({source})", flush=True)
        except UntisError as exc:
            failed.append(f"{monday}: {exc}")
            print(f"WARNUNG {failed[-1]}", file=sys.stderr, flush=True)
    # Do not publish a misleading empty or partially synchronized calendar.
    if failed or not successes or not all_periods:
        print("ABBRUCH: Keine Veröffentlichung bei Fehlern oder leerem Plan.", file=sys.stderr)
        print("Prüfe die öffentliche WebUntis-Freigabe / STUDENT-ID / Protokoll.", file=sys.stderr)
        return 2
    data = [p for p in all_periods if start <= p.start.date() <= end]
    ics = make_ics(data)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".tmp")
    tmp.write_bytes(ics.encode("utf-8"))
    tmp.replace(OUTPUT)
    print(f"Fertig: {OUTPUT} / {len(data)} Stunden (Zeitraum {start} bis {end})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
