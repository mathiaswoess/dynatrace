#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://api.timecockpit.com"
DEFAULT_USER_UUID = "2edda6e5-39aa-446f-a8e7-fd29303a3449"
ROOT_DIR = Path(__file__).resolve().parents[1]
PAGES_DIR = ROOT_DIR / "pages"
INDEX_PAGE = PAGES_DIR / "Timecockpit.md"
PAGE_NAME_TEMPLATE = "Timecockpit {month}.md"
INDEX_LINK_TEMPLATE = "- [[Timecockpit {month}]]"
TYPE_LABELS = {
    "0ad94cf7-955c-45dc-b49e-20be0f449b75": "Home Office",
    "cd4f750b-85f8-41f8-b193-9c82e23f82eb": "Office",
    "9e160bb3-4f22-47a4-9b1a-701868563a4b": "Travel",
    "43007851-87f0-468d-b9d2-376ede4a8fd2": "Field Service",
    "23fc8769-0624-4fb3-857d-54c4ca71357a": "Training/Conference",
    "d1cfb1e0-9c8d-43f7-bf99-628e9ebeed38": "Doctor",
    "15f76b17-ac62-4908-8e79-89c81519dd01": "Care Leave",
}
ABSENCE_COLLECTION_CANDIDATES = [
    "APP_Absence",
    "APP_AbsenceDay",
    "APP_Holiday",
    "APP_Leave",
    "APP_SickLeave",
    "USR_Absence",
]
ABSENCE_FALLBACK_LABELS = {
    "APP_Absence": "Absence",
    "APP_AbsenceDay": "Absence",
    "APP_Holiday": "Holiday",
    "APP_Leave": "Leave",
    "APP_SickLeave": "Sick Leave",
    "USR_Absence": "Absence",
}
USER_FIELDS = [
    "APP_UserDetailUuid",
    "USR_UserDetailUuid",
    "APP_UserUuid",
    "USR_UserUuid",
]
START_FIELDS = [
    "APP_BeginTime",
    "APP_StartTime",
    "APP_BeginDate",
    "APP_StartDate",
    "APP_Date",
    "APP_Day",
]
END_FIELDS = [
    "APP_EndTime",
    "APP_EndDate",
    "APP_StopDate",
    "APP_ToDate",
    "APP_UntilDate",
]
LABEL_FIELDS = [
    "APP_AbsenceTypeName",
    "USR_AbsenceTypeName",
    "APP_TypeName",
    "USR_TypeName",
    "APP_Name",
    "APP_Title",
    "APP_Caption",
    "APP_Text",
    "APP_Code",
]
DESCRIPTION_FIELDS = [
    "APP_Description",
    "APP_Reason",
    "APP_Remark",
    "APP_Note",
    "APP_Comment",
]


@dataclass(frozen=True)
class Config:
    pat: str
    user_uuid: str


@dataclass(frozen=True)
class MonthRange:
    month: str
    start: date
    end: date


@dataclass(frozen=True)
class AbsenceFields:
    user_field: str
    start_field: str
    end_field: str | None
    label_field: str | None
    description_field: str | None


def load_config() -> Config:
    pat_value = os.getenv("TIMECOCKPIT_PAT", f"{Path.home()}/Documents/tokens/timecockpit-curl.txt")
    pat_path = Path(pat_value).expanduser()
    pat = pat_path.read_text(encoding="utf-8").strip() if pat_path.is_file() else pat_value.strip()
    if not pat:
        raise SystemExit("TIMECOCKPIT_PAT is empty.")
    return Config(
        pat=pat,
        user_uuid=os.getenv("TIMECOCKPIT_USER_UUID", DEFAULT_USER_UUID).strip(),
    )


def request_text(config: Config, path: str, *, query: dict[str, str] | None = None) -> str:
    url = f"{BASE_URL}{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    req = Request(url, headers={"Authorization": f"Bearer {config.pat}"})
    try:
        with urlopen(req) as response:
            return response.read().decode("utf-8")
    except (HTTPError, URLError) as exc:
        raise SystemExit(f"Request failed: {exc}") from exc


def request_json(config: Config, path: str, *, query: dict[str, str] | None = None) -> dict:
    payload = request_text(config, path, query=query)
    return json.loads(payload) if payload else {}


def try_request_json(config: Config, path: str, *, query: dict[str, str] | None = None) -> dict | None:
    url = f"{BASE_URL}{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    req = Request(url, headers={"Authorization": f"Bearer {config.pat}"})
    try:
        with urlopen(req) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as exc:
        return None
    except URLError as exc:
        return None
    return json.loads(payload) if payload else {}


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


def fetch_task_codes(config: Config, task_uuids: list[str]) -> dict[str, str]:
    if not task_uuids:
        return {}

    task_codes: dict[str, str] = {}
    unique_task_uuids = list(dict.fromkeys(task_uuids))
    for index in range(0, len(unique_task_uuids), 20):
        chunk = unique_task_uuids[index:index + 20]
        payload = request_json(
            config,
            "/odata/APP_Task()",
            query={
                "$filter": " or ".join(f"APP_TaskUuid eq guid'{task_uuid}'" for task_uuid in chunk),
                "$select": "APP_TaskUuid,APP_Code",
            },
        )
        task_codes.update(
            {
                (task.get("APP_TaskUuid") or "").strip(): (task.get("APP_Code") or "").strip()
                for task in payload.get("value", [])
                if task.get("APP_TaskUuid")
            }
        )
    return task_codes


def fetch_timesheet_entries(config: Config, month_range: MonthRange) -> list[dict]:
    end_exclusive = month_range.end + timedelta(days=1)
    payload = request_json(
        config,
        "/odata/APP_Timesheet()",
        query={
            "$filter": (
                f"APP_UserDetailUuid eq guid'{config.user_uuid}' and "
                f"APP_BeginTime ge datetime'{month_range.start}T00:00:00' and "
                f"APP_BeginTime lt datetime'{end_exclusive}T00:00:00'"
            ),
            "$orderby": "APP_BeginTime",
            "$select": "APP_TimesheetUuid,APP_BeginTime,APP_EndTime,APP_Description,USR_TimesheetTypeUuid,APP_TaskUuid",
        },
    )
    entries = payload.get("value", [])
    task_codes = fetch_task_codes(
        config,
        [
            task_uuid
            for entry in entries
            if (task_uuid := (entry.get("APP_TaskUuid") or "").strip())
        ],
    )
    for entry in entries:
        task_uuid = (entry.get("APP_TaskUuid") or "").strip()
        if task_uuid:
            entry["APP_TicketCode"] = task_codes.get(task_uuid, "")
    return entries


def discover_absence_collections(config: Config) -> list[str]:
    discovered = list(ABSENCE_COLLECTION_CANDIDATES)
    try:
        metadata = request_text(config, "/odata/$metadata")
    except SystemExit:
        return discovered

    for name in re.findall(r'EntitySet Name="([^"]+)"', metadata):
        if re.search(r"Absence|Leave|Holiday|Vacation|Sick", name, re.IGNORECASE) and name not in discovered:
            discovered.append(name)
    return discovered


def pick_first_key(record: dict, names: list[str]) -> str | None:
    for name in names:
        if name in record:
            return name
    return None


def detect_absence_fields(record: dict) -> AbsenceFields | None:
    user_field = pick_first_key(record, USER_FIELDS)
    start_field = pick_first_key(record, START_FIELDS)
    if not user_field or not start_field:
        return None
    return AbsenceFields(
        user_field=user_field,
        start_field=start_field,
        end_field=pick_first_key(record, END_FIELDS),
        label_field=pick_first_key(record, LABEL_FIELDS),
        description_field=pick_first_key(record, DESCRIPTION_FIELDS),
    )


def fetch_absence_records(config: Config, month_range: MonthRange) -> list[tuple[date, str]]:
    records_by_day: dict[date, set[str]] = {}
    for collection in discover_absence_collections(config):
        sample_payload = try_request_json(config, f"/odata/{collection}()", query={"$top": "1"})
        if not sample_payload:
            continue
        sample_values = sample_payload.get("value", [])
        if not sample_values:
            continue

        fields = detect_absence_fields(sample_values[0])
        if not fields:
            continue

        payload = try_request_json(
            config,
            f"/odata/{collection}()",
            query={
                "$filter": f"{fields.user_field} eq guid'{config.user_uuid}'",
                "$orderby": fields.start_field,
            },
        )
        if not payload:
            continue

        for record in payload.get("value", []):
            start_day = parse_dateish(record.get(fields.start_field))
            end_day = parse_dateish(record.get(fields.end_field)) if fields.end_field else start_day
            if not start_day or not end_day:
                continue
            if end_day < month_range.start or start_day > month_range.end:
                continue

            label = absence_label(record, fields, collection)
            for day in expand_overlap(start_day, end_day, month_range.start, month_range.end):
                records_by_day.setdefault(day, set()).add(label)

    normalized: list[tuple[date, str]] = []
    for day in sorted(records_by_day):
        for label in sorted(records_by_day[day]):
            normalized.append((day, label))
    return normalized


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


def absence_label(record: dict, fields: AbsenceFields, collection: str) -> str:
    label = string_value(record.get(fields.label_field)) if fields.label_field else ""
    description = string_value(record.get(fields.description_field)) if fields.description_field else ""

    if label and description and label != description:
        return f"All day: {label} ({description})"
    if label:
        return f"All day: {label}"
    if description:
        return f"All day: {description}"
    return f"All day: {ABSENCE_FALLBACK_LABELS.get(collection, collection)}"


def string_value(value: object) -> str:
    return str(value).strip() if value is not None else ""


def expand_overlap(start: date, end: date, month_start: date, month_end: date) -> list[date]:
    current = max(start, month_start)
    last = min(end, month_end)
    days: list[date] = []
    while current <= last:
        days.append(current)
        current += timedelta(days=1)
    return days


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
    type_uuid = string_value(entry.get("USR_TimesheetTypeUuid"))
    type_label = TYPE_LABELS.get(type_uuid, type_uuid)
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
    config = load_config()
    month_range = parse_month(args.month)
    timesheet_entries = fetch_timesheet_entries(config, month_range)
    absence_entries = fetch_absence_records(config, month_range)
    display_end = resolve_display_end(month_range, timesheet_entries, absence_entries)
    content = build_page_content(month_range, display_end, timesheet_entries, absence_entries)
    page_path = write_month_page(month_range, content)
    update_index(month_range)
    print(page_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))