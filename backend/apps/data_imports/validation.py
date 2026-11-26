import csv
import io
import json
import re
from datetime import datetime, date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from apps.directory.models import (
    AcademicModule,
    Qualification,
    FacultyExpertise,
    FacultyProfile,
    LearnerProfile,
)
from .models import ImportBatch

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000
BATCH_TTL_HOURS = 24

FACULTY_HEADERS = [
    "Faculty_ID", "Full_Name", "Email", "Department", "Qualifications",
    "Modules_Taught", "Expertise_Mappings", "Teaching_Experience_Years",
    "Consultation_Modes", "Languages", "Time_Zone", "Working_Days",
    "Working_Hours_Start", "Working_Hours_End", "Status",
]
LEARNER_HEADERS = [
    "Learner_ID", "Full_Name", "Email", "Qualification", "Current_Module_Code", "Current_Module_Codes",
    "Time_Zone", "Preferred_Consultation_Mode",
    "Preferred_Language", "Status",
]
VALID_STATUSES = {"Active", "Inactive"}
VALID_LEVELS = {"Basic", "Intermediate", "Advanced", "Expert"}


def _split_list(value):
    return [item.strip() for item in (value or "").split(";") if item.strip()]


def _validate_email(value):
    try:
        validate_email(value)
    except ValidationError:
        raise ValueError("Enter a valid email address.")


def _validate_timezone(value):
    if not value:
        raise ValueError("This field is required.")
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError:
        raise ValueError("Use a valid IANA time zone, e.g. Asia/Yangon.")


def _parse_time(value, field):
    if not value:
        raise ValueError("This field is required.")
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError:
        raise ValueError("Use 24-hour HH:MM format, e.g. 09:00.")


def _base_row_error(row_number, field, message):
    return {"row": row_number, "field": field, "message": message}


def _validate_common(row, row_number, id_field):
    errors = []
    for field in (id_field, "Full_Name", "Email", "Status"):
        if not (row.get(field) or "").strip():
            errors.append(_base_row_error(row_number, field, "This field is required."))
    if row.get("Email"):
        try:
            _validate_email(row["Email"].strip())
        except ValueError as exc:
            errors.append(_base_row_error(row_number, "Email", str(exc)))
    if row.get("Status") and row["Status"].strip() not in VALID_STATUSES:
        errors.append(_base_row_error(row_number, "Status", "Use Active or Inactive."))
    return errors


def _validate_faculty(row, row_number):
    errors = _validate_common(row, row_number, "Faculty_ID")
    for field in ("Expertise_Mappings",
                  "Teaching_Experience_Years", "Consultation_Modes", "Languages",
                  "Time_Zone", "Working_Days"):
        if not (row.get(field) or "").strip():
            errors.append(_base_row_error(row_number, field, "This field is required."))

    languages = _split_list(row.get("Languages"))
    if not any(language.casefold() == "english" for language in languages):
        errors.append(_base_row_error(row_number, "Languages", "English must be included for every faculty member."))
    for field in ("Qualifications", "Modules_Taught", "Consultation_Modes", "Working_Days"):
        if row.get(field) and not _split_list(row[field]):
            errors.append(_base_row_error(row_number, field, "Provide at least one semicolon-separated value."))

    try:
        _validate_timezone(row.get("Time_Zone", "").strip())
    except ValueError as exc:
        errors.append(_base_row_error(row_number, "Time_Zone", str(exc)))

    start = end = None
    if row.get("Working_Hours_Start"):
        try:
            start = _parse_time(row["Working_Hours_Start"].strip(), "Working_Hours_Start")
        except ValueError as exc:
            errors.append(_base_row_error(row_number, "Working_Hours_Start", str(exc)))
    if row.get("Working_Hours_End"):
        try:
            end = _parse_time(row["Working_Hours_End"].strip(), "Working_Hours_End")
        except ValueError as exc:
            errors.append(_base_row_error(row_number, "Working_Hours_End", str(exc)))
    if bool(start) != bool(end):
        errors.append(_base_row_error(row_number, "Working_Hours_End", "Provide both times or neither."))
    if start and end and start >= end:
        errors.append(_base_row_error(row_number, "Working_Hours_End", "End time must be later than start time."))

    try:
        years = int(row.get("Teaching_Experience_Years", ""))
        if years < 0 or years > 60:
            raise ValueError
    except ValueError:
        errors.append(_base_row_error(row_number, "Teaching_Experience_Years", "Enter a whole number from 0 to 60."))

    try:
        mappings = json.loads(row.get("Expertise_Mappings", ""))
        if not isinstance(mappings, list):
            raise ValueError("Expertise_Mappings must be a JSON array.")
        seen_codes = set()
        for index, mapping in enumerate(mappings):
            if not isinstance(mapping, dict):
                raise ValueError(f"Mapping {index + 1} must be a JSON object.")
            for key in ("module_code", "expertise_level"):
                if not str(mapping.get(key, "")).strip():
                    raise ValueError(f"Mapping {index + 1}: {key} is required.")
            code = str(mapping["module_code"]).strip()
            if code in seen_codes:
                raise ValueError(f"Duplicate module_code '{code}' in this faculty's mappings.")
            seen_codes.add(code)
            if mapping["expertise_level"] not in VALID_LEVELS:
                raise ValueError(f"Mapping {index + 1}: expertise_level must be Basic, Intermediate, Advanced or Expert.")
            if not isinstance(mapping.get("topics", []), list):
                raise ValueError(f"Mapping {index + 1}: topics must be a JSON array.")
            if not isinstance(mapping.get("qualifications", []), list):
                raise ValueError(f"Mapping {index + 1}: qualifications must be a JSON array.")
            if not isinstance(mapping.get("eligible_for_consultation"), bool):
                raise ValueError(f"Mapping {index + 1}: eligible_for_consultation must be true or false.")
            reviewed = mapping.get("last_reviewed")
            if reviewed:
                try:
                    date.fromisoformat(reviewed)
                except (TypeError, ValueError):
                    raise ValueError(f"Mapping {index + 1}: last_reviewed must use YYYY-MM-DD.")
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        errors.append(_base_row_error(row_number, "Expertise_Mappings", str(exc)))

    return errors


def _validate_learner(row, row_number):
    errors = _validate_common(row, row_number, "Learner_ID")
    for field in ("Qualification", "Current_Module_Code", "Current_Module_Codes", "Time_Zone",
                  "Preferred_Consultation_Mode", "Preferred_Language"):
        if not (row.get(field) or "").strip():
            errors.append(_base_row_error(row_number, field, "This field is required."))
    languages = _split_list(row.get("Preferred_Language"))
    if not any(language.casefold() == "english" for language in languages):
        errors.append(_base_row_error(row_number, "Preferred_Language", "English must be included for every learner."))
    try:
        _validate_timezone(row.get("Time_Zone", "").strip())
    except ValueError as exc:
        errors.append(_base_row_error(row_number, "Time_Zone", str(exc)))
    return errors


