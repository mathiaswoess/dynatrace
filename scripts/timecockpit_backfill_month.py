#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
PAGES_DIR = ROOT_DIR / "pages"
INDEX_PAGE = PAGES_DIR / "Timecockpit.md"
PAGE_NAME_TEMPLATE = "Timecockpit {month}.md"
INDEX_LINK_TEMPLATE = "- [[Timecockpit {month}]]"
TIMECOCKPIT_BINARY = "timecockpit"


@dataclass(frozen=True)
class MonthRange:
    month: str
    start: date
    end: date


def parse_month(value: str | None) -> MonthRange:
    today = date.today()
    month_value = value or today.strftime("%Y-%m")
    match = re.fullmatch(r"(\d{4})-(\d{2})", month_value)
    if not match:
        raise SystemExit("Month must use YYYY-MM.")

    year = int(match.group(1))
    month = int(match.group(2))
    start = date(year, month, 1)
    next_month = date(year + (month // 12), (month % 12) + 1, 1)
    end = next_month - timedelta(days=1)
    if start > today:
        raise SystemExit("Cannot fetch a future month.")
    return MonthRange(month=month_value, start=start, end=end)


def fetch_month_payload(month_range: MonthRange) -> dict:
    timecockpit_binary = shutil.which(TIMECOCKPIT_BINARY)
    if not timecockpit_binary:
        raise SystemExit("timecockpit is not available on PATH.")

    result = subprocess.run(
        [timecockpit_binary, "list", "--month", month_range.month, "--json", "--include-absences"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        error_output = result.stderr.strip() or result.stdout.strip() or "timecockpit command failed."
        raise SystemExit(error_output)

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit("timecockpit returned invalid JSON.") from exc


def parse_dateish(value: object) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) >= 10:
        text = text[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def string_value(value: object) -> str:
    return str(value).strip() if value is not None else ""


def build_page_content(
    month_range: MonthRange,
    display_end: date,
    timesheet_entries: list[dict],
    absences: list[tuple[date, str]],
) -> str:
    timesheet_by_day: dict[date, list[str]] = {}
    for entry in timesheet_entries:
        day = parse_dateish(entry.get("APP_BeginTime"))
        if not day:
            continue
        timesheet_by_day.setdefault(day, []).append(format_timesheet_entry(entry))

    absence_by_day: dict[date, list[str]] = {}
    for day, label in absences:
        absence_by_day.setdefault(day, []).append(f"- {label}")

    lines = [f"# Timecockpit {month_range.month}", ""]
    current = month_range.start
    while current <= display_end:
        lines.append(f"## {current.isoformat()}")
        day_lines = []
        day_lines.extend(absence_by_day.get(current, []))
        day_lines.extend(timesheet_by_day.get(current, []))
        if day_lines:
            lines.extend(day_lines)
        else:
            lines.append("- No timecockpit entries found.")
        lines.append("")
        current += timedelta(days=1)

    return "\n".join(lines).rstrip() + "\n"


def resolve_display_end(month_range: MonthRange, timesheet_entries: list[dict], absences: list[tuple[date, str]]) -> date:
    today = date.today()
    current_month = today.strftime("%Y-%m")
    if month_range.month != current_month:
        return month_range.end

    last_data_day = month_range.start
    for entry in timesheet_entries:
        if (entry_day := parse_dateish(entry.get("APP_BeginTime"))) and entry_day > last_data_day:
            last_data_day = entry_day
    for absence_day, _label in absences:
        if absence_day > last_data_day:
            last_data_day = absence_day

    return min(month_range.end, max(today, last_data_day))


def format_timesheet_entry(entry: dict) -> str:
    begin = string_value(entry.get("APP_BeginTime"))[11:16]
    end = string_value(entry.get("APP_EndTime"))[11:16]
    time_range = f"{begin}-{end}" if begin and end else "All day"
    type_label = string_value(entry.get("APP_TypeLabel")) or string_value(entry.get("USR_TimesheetTypeUuid"))
    description = string_value(entry.get("APP_Description"))
    ticket = string_value(entry.get("APP_TicketCode"))

    text = f"- {time_range}"
    if type_label:
        text += f" {type_label}"
    if description:
        text += f": {description}"
    if ticket:
        text += f" ({ticket})"
    return text


def write_month_page(month_range: MonthRange, content: str) -> Path:
    page_path = PAGES_DIR / PAGE_NAME_TEMPLATE.format(month=month_range.month)
    page_path.write_text(content, encoding="utf-8")
    return page_path


def update_index(month_range: MonthRange) -> None:
    link = INDEX_LINK_TEMPLATE.format(month=month_range.month)
    if INDEX_PAGE.exists():
        lines = INDEX_PAGE.read_text(encoding="utf-8").splitlines()
    else:
        lines = ["# Timecockpit", ""]

    existing_links = [line for line in lines if line.startswith("- [[Timecockpit ")]
    if link not in existing_links:
        existing_links.append(link)
    existing_links.sort()

    INDEX_PAGE.write_text(
        "# Timecockpit\n\n" + "\n".join(existing_links) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch a month of timecockpit data into the raw backfill pages.")
    parser.add_argument("month", nargs="?", help="Target month in YYYY-MM format. Defaults to the current month.")
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    month_range = parse_month(args.month)
    payload = fetch_month_payload(month_range)
    timesheet_entries = payload.get("entries", [])
    absence_entries = [
        (parse_dateish(item.get("date")), string_value(item.get("label")))
        for item in payload.get("absences", [])
    ]
    absence_entries = [(day, label) for day, label in absence_entries if day and label]
    display_end = resolve_display_end(month_range, timesheet_entries, absence_entries)
    content = build_page_content(month_range, display_end, timesheet_entries, absence_entries)
    page_path = write_month_page(month_range, content)
    update_index(month_range)
    print(page_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))