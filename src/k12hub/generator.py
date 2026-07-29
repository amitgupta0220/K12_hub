"""Deterministic synthetic K-12 dataset generation."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import random
import re
import zipfile
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from openpyxl import Workbook

INSTRUCTIONAL_MINUTES = 420
INSTRUCTIONAL_DAY_COUNT = 180
ERROR_TYPES = (
    "duplicate_student",
    "missing_student_identifier",
    "unknown_school_code",
    "invalid_grade",
    "overlapping_enrollment",
    "attendance_for_unknown_student",
    "duplicate_daily_attendance",
    "attendance_outside_enrollment_period",
    "invalid_attendance_status",
    "attended_minutes_greater_than_possible",
    "invalid_assessment_score",
    "schema_drift_field",
)
GRADES = ("K", "01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12")
ATTENDANCE_STATUSES = ("present", "absent_excused", "absent_unexcused", "tardy")
PROFICIENT_LEVELS = {"meets_standard", "exceeds_standard"}

STUDENT_FIELDS = (
    "student_id",
    "local_student_number",
    "first_name",
    "last_name",
    "birth_date",
    "gender",
    "grade_level",
    "district_id",
    "school_id",
    "active",
)
ENROLLMENT_FIELDS = (
    "enrollment_id",
    "student_id",
    "district_id",
    "school_id",
    "academic_year",
    "grade_level",
    "entry_date",
    "exit_date",
    "enrollment_status",
)
ATTENDANCE_FIELDS = (
    "student_id",
    "district_id",
    "school_id",
    "instructional_date",
    "attendance_status",
    "minutes_attended",
    "reason_code",
    "recorded_at",
)
ASSESSMENT_FIELDS = (
    "assessment_event_id",
    "student_id",
    "district_id",
    "school_id",
    "academic_year",
    "assessment_name",
    "subject",
    "assessment_date",
    "scale_score",
    "performance_level",
)


@dataclass(frozen=True)
class GeneratorOptions:
    """Inputs that fully determine one generated dataset."""

    seed: int = 2026
    students: int = 1500
    school_year: str = "2025-2026"
    error_rate: float = 0.0
    enabled_error_types: tuple[str, ...] = ()
    output_directory: Path = Path("data/generated")

    def __post_init__(self) -> None:
        if self.students < 1:
            raise ValueError("students must be at least 1")
        if not 0.0 <= self.error_rate <= 1.0:
            raise ValueError("error_rate must be between 0 and 1")
        start_year, separator, end_year = self.school_year.partition("-")
        if (
            separator != "-"
            or not start_year.isdigit()
            or not end_year.isdigit()
            or len(start_year) != 4
            or len(end_year) != 4
            or int(end_year) != int(start_year) + 1
        ):
            raise ValueError("school_year must use consecutive YYYY-YYYY years")
        unknown_errors = sorted(set(self.enabled_error_types) - set(ERROR_TYPES))
        if unknown_errors:
            raise ValueError(f"unknown error types: {unknown_errors}")
        if len(self.enabled_error_types) != len(set(self.enabled_error_types)):
            raise ValueError("enabled error types must be unique")

    @property
    def run_id(self) -> str:
        """Return a deterministic identifier based only on content-affecting inputs."""

        arguments = {
            "enabled_error_types": sorted(self.enabled_error_types),
            "error_rate": self.error_rate,
            "school_year": self.school_year,
            "seed": self.seed,
            "students": self.students,
        }
        digest = hashlib.sha256(
            json.dumps(arguments, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return f"run-{digest[:16]}"


@dataclass(frozen=True)
class School:
    """One fictitious school in the synthetic region."""

    school_id: str
    district_id: str
    name: str
    school_type: str
    grade_range: str

    def to_dict(self) -> dict[str, str]:
        return {
            "district_id": self.district_id,
            "grade_range": self.grade_range,
            "name": self.name,
            "school_id": self.school_id,
            "school_type": self.school_type,
        }


@dataclass
class StudentRecord:
    """Synthetic SIS student row."""

    student_id: str
    local_student_number: str
    first_name: str
    last_name: str
    birth_date: str
    gender: str
    grade_level: str
    district_id: str
    school_id: str
    active: bool
    extra_fields: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "student_id": self.student_id,
            "local_student_number": self.local_student_number,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "birth_date": self.birth_date,
            "gender": self.gender,
            "grade_level": self.grade_level,
            "district_id": self.district_id,
            "school_id": self.school_id,
            "active": self.active,
        }
        result.update(self.extra_fields)
        return result


@dataclass
class EnrollmentRecord:
    """Synthetic SIS enrollment row."""

    enrollment_id: str
    student_id: str
    district_id: str
    school_id: str
    academic_year: str
    grade_level: str
    entry_date: str
    exit_date: str
    enrollment_status: str

    def to_dict(self) -> dict[str, object]:
        return {
            "enrollment_id": self.enrollment_id,
            "student_id": self.student_id,
            "district_id": self.district_id,
            "school_id": self.school_id,
            "academic_year": self.academic_year,
            "grade_level": self.grade_level,
            "entry_date": self.entry_date,
            "exit_date": self.exit_date,
            "enrollment_status": self.enrollment_status,
        }


@dataclass
class AttendanceRecord:
    """Synthetic daily attendance row."""

    student_id: str
    district_id: str
    school_id: str
    instructional_date: str
    attendance_status: str
    minutes_attended: int
    reason_code: str
    recorded_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "student_id": self.student_id,
            "district_id": self.district_id,
            "school_id": self.school_id,
            "instructional_date": self.instructional_date,
            "attendance_status": self.attendance_status,
            "minutes_attended": self.minutes_attended,
            "reason_code": self.reason_code,
            "recorded_at": self.recorded_at,
        }


@dataclass
class AssessmentRecord:
    """Synthetic assessment event row."""

    assessment_event_id: str
    student_id: str
    district_id: str
    school_id: str
    academic_year: str
    assessment_name: str
    subject: str
    assessment_date: str
    scale_score: float
    performance_level: str

    def to_dict(self) -> dict[str, object]:
        return {
            "assessment_event_id": self.assessment_event_id,
            "student_id": self.student_id,
            "district_id": self.district_id,
            "school_id": self.school_id,
            "academic_year": self.academic_year,
            "assessment_name": self.assessment_name,
            "subject": self.subject,
            "assessment_date": self.assessment_date,
            "scale_score": self.scale_score,
            "performance_level": self.performance_level,
        }


@dataclass
class GeneratedRecords:
    """In-memory synthetic records before file serialization."""

    students: list[StudentRecord]
    enrollments: list[EnrollmentRecord]
    attendance: list[AttendanceRecord]
    assessments: list[AssessmentRecord]


@dataclass(frozen=True)
class GenerationResult:
    """Generated dataset location and deterministic metadata."""

    run_id: str
    output_path: Path
    manifest: dict[str, Any]
    expected_metrics: dict[str, Any]


def _regional_structure() -> tuple[list[dict[str, str]], list[School]]:
    districts = [
        {
            "district_id": f"SYN-D{index:02d}",
            "intermediate_district_id": "SYN-ISD-001",
            "name": f"Synthetic Local District {index}",
        }
        for index in range(1, 4)
    ]
    schools: list[School] = []
    for district_number in range(1, 4):
        district_id = f"SYN-D{district_number:02d}"
        schools.extend(
            [
                School(
                    f"{district_id}-E01",
                    district_id,
                    f"Synthetic Elementary {district_number}A",
                    "elementary",
                    "K-05",
                ),
                School(
                    f"{district_id}-E02",
                    district_id,
                    f"Synthetic Elementary {district_number}B",
                    "elementary",
                    "K-05",
                ),
                School(
                    f"{district_id}-M01",
                    district_id,
                    f"Synthetic Middle {district_number}",
                    "middle",
                    "06-08",
                ),
                School(
                    f"{district_id}-H01",
                    district_id,
                    f"Synthetic High {district_number}",
                    "high",
                    "09-12",
                ),
            ]
        )
    return districts, schools


def _last_monday_in_august(year: int) -> date:
    candidate = date(year, 8, 31)
    return candidate - timedelta(days=candidate.weekday())


def _nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (occurrence - 1))


def instructional_days(school_year: str) -> list[date]:
    """Return exactly 180 deterministic instructional days."""

    start_year = int(school_year[:4])
    end_year = start_year + 1
    current = _last_monday_in_august(start_year)
    thanksgiving = _nth_weekday(start_year, 11, 3, 4)
    spring_break_start = _nth_weekday(end_year, 4, 0, 1)
    excluded = {
        _nth_weekday(start_year, 9, 0, 1),
        thanksgiving,
        thanksgiving + timedelta(days=1),
        _nth_weekday(end_year, 1, 0, 3),
    }
    excluded.update(
        date(end_year if month == 1 else start_year, month, day)
        for month, days in ((12, range(22, 32)), (1, range(1, 3)))
        for day in days
    )
    excluded.update(spring_break_start + timedelta(days=offset) for offset in range(5))

    days: list[date] = []
    while len(days) < INSTRUCTIONAL_DAY_COUNT:
        if current.weekday() < 5 and current not in excluded:
            days.append(current)
        current += timedelta(days=1)
    return days


def _school_for_grade(
    schools: list[School],
    district_id: str,
    grade_level: str,
    student_index: int,
) -> School:
    district_schools = [school for school in schools if school.district_id == district_id]
    if grade_level in {"K", "01", "02", "03", "04", "05"}:
        elementary = [school for school in district_schools if school.school_type == "elementary"]
        return elementary[student_index % len(elementary)]
    if grade_level in {"06", "07", "08"}:
        return next(school for school in district_schools if school.school_type == "middle")
    return next(school for school in district_schools if school.school_type == "high")


def _synthetic_student_id(seed: int, student_index: int) -> str:
    digest = hashlib.sha256(f"k12hub-synthetic:{seed}:{student_index}".encode()).hexdigest()
    return f"SYN-{digest[:12].upper()}"


def _birth_date(rng: random.Random, start_year: int, grade_level: str) -> str:
    grade_number = 0 if grade_level == "K" else int(grade_level)
    approximate_age = 5 + grade_number
    birth_year = start_year - approximate_age
    start = date(birth_year, 1, 1)
    return (start + timedelta(days=rng.randrange(365))).isoformat()


def _generate_baseline(
    options: GeneratorOptions,
) -> tuple[GeneratedRecords, list[date], list[School]]:
    rng = random.Random(options.seed)
    days = instructional_days(options.school_year)
    districts, schools = _regional_structure()
    district_ids = [district["district_id"] for district in districts]
    students: list[StudentRecord] = []
    enrollments: list[EnrollmentRecord] = []
    attendance: list[AttendanceRecord] = []
    assessments: list[AssessmentRecord] = []
    genders = ("female", "male", "nonbinary", "not_reported")

    for index in range(1, options.students + 1):
        student_id = _synthetic_student_id(options.seed, index)
        district_id = district_ids[rng.randrange(len(district_ids))]
        grade_level = rng.choice(GRADES)
        school = _school_for_grade(schools, district_id, grade_level, index)

        entry_index = 0
        exit_index = len(days) - 1
        enrollment_draw = rng.random()
        if enrollment_draw < 0.04:
            entry_index = rng.randint(10, 40)
        elif enrollment_draw < 0.08:
            exit_index = rng.randint(125, len(days) - 2)
        entry_date = days[entry_index]
        exit_date = days[exit_index]
        active = exit_index == len(days) - 1

        students.append(
            StudentRecord(
                student_id=student_id,
                local_student_number=f"SYNLOCAL-{options.seed:06d}-{index:06d}",
                first_name=f"Synthetic{index:06d}",
                last_name=f"Learner{options.seed:06d}",
                birth_date=_birth_date(rng, int(options.school_year[:4]), grade_level),
                gender=rng.choices(genders, weights=(47, 47, 3, 3), k=1)[0],
                grade_level=grade_level,
                district_id=district_id,
                school_id=school.school_id,
                active=active,
            )
        )
        enrollments.append(
            EnrollmentRecord(
                enrollment_id=f"SYN-ENR-{options.seed:06d}-{index:06d}",
                student_id=student_id,
                district_id=district_id,
                school_id=school.school_id,
                academic_year=options.school_year,
                grade_level=grade_level,
                entry_date=entry_date.isoformat(),
                exit_date="" if active else exit_date.isoformat(),
                enrollment_status="active" if active else "exited",
            )
        )

        absence_probability = min(0.22, max(0.01, rng.betavariate(2.0, 30.0)))
        enrolled_days = days[entry_index : exit_index + 1]
        for instructional_date in enrolled_days:
            attendance_draw = rng.random()
            if attendance_draw < absence_probability:
                excused = rng.random() < 0.62
                status = "absent_excused" if excused else "absent_unexcused"
                minutes = 0
                reason = rng.choice(("illness", "appointment", "transportation", "family"))
            elif attendance_draw < absence_probability + 0.035:
                status = "tardy"
                minutes = rng.randint(350, 410)
                reason = rng.choice(("transportation", "appointment", "unknown"))
            else:
                status = "present"
                minutes = INSTRUCTIONAL_MINUTES
                reason = "not_applicable"
            recorded = datetime.combine(instructional_date, time(16, index % 60), tzinfo=None)
            attendance.append(
                AttendanceRecord(
                    student_id=student_id,
                    district_id=district_id,
                    school_id=school.school_id,
                    instructional_date=instructional_date.isoformat(),
                    attendance_status=status,
                    minutes_attended=minutes,
                    reason_code=reason,
                    recorded_at=f"{recorded.isoformat()}Z",
                )
            )

        assessment_day = enrolled_days[
            max(0, min(len(enrolled_days) - 1, len(enrolled_days) * 3 // 4))
        ]
        for subject_index, subject in enumerate(("mathematics", "reading"), start=1):
            score = round(min(100.0, max(0.0, rng.gauss(71.0, 14.0))), 1)
            if score < 50:
                level = "below_standard"
            elif score < 65:
                level = "approaching_standard"
            elif score < 85:
                level = "meets_standard"
            else:
                level = "exceeds_standard"
            assessments.append(
                AssessmentRecord(
                    assessment_event_id=(f"SYN-ASM-{options.seed:06d}-{index:06d}-{subject_index}"),
                    student_id=student_id,
                    district_id=district_id,
                    school_id=school.school_id,
                    academic_year=options.school_year,
                    assessment_name="Synthetic Regional Benchmark",
                    subject=subject,
                    assessment_date=assessment_day.isoformat(),
                    scale_score=score,
                    performance_level=level,
                )
            )

    return GeneratedRecords(students, enrollments, attendance, assessments), days, schools


def calculate_expected_metrics(
    records: GeneratedRecords,
    instructional_day_count: int,
    school_year: str,
) -> dict[str, Any]:
    """Calculate deterministic clean aggregates for later pipeline tests."""

    attended_minutes = sum(record.minutes_attended for record in records.attendance)
    possible_minutes = len(records.attendance) * INSTRUCTIONAL_MINUTES
    attendance_rate = attended_minutes / possible_minutes if possible_minutes else 0.0

    by_student: dict[str, list[AttendanceRecord]] = {}
    for record in records.attendance:
        by_student.setdefault(record.student_id, []).append(record)
    chronically_absent = sum(
        1
        for student_records in by_student.values()
        if (
            sum(INSTRUCTIONAL_MINUTES - record.minutes_attended for record in student_records)
            / (len(student_records) * INSTRUCTIONAL_MINUTES)
        )
        >= 0.10
    )
    chronic_absence_rate = chronically_absent / len(by_student) if by_student else 0.0

    proficient = sum(
        1 for record in records.assessments if record.performance_level in PROFICIENT_LEVELS
    )
    proficiency_rate = proficient / len(records.assessments) if records.assessments else 0.0

    return {
        "instructional_days": instructional_day_count,
        "metrics": {
            "assessment_event_count": len(records.assessments),
            "assessment_proficiency_rate": round(proficiency_rate, 6),
            "attendance_rate": round(attendance_rate, 6),
            "chronic_absence_rate": round(chronic_absence_rate, 6),
            "enrollment_count": len(records.enrollments),
            "student_count": len(records.students),
        },
        "school_year": school_year,
        "synthetic_data": True,
    }


def _error_count(options: GeneratorOptions) -> int:
    if options.error_rate == 0 or not options.enabled_error_types:
        return 0
    return max(1, round(options.students * options.error_rate))


def _inject_errors(
    records: GeneratedRecords,
    options: GeneratorOptions,
    days: list[date],
) -> dict[str, int]:
    rng = random.Random(options.seed ^ 0xBAD5EED)
    count = _error_count(options)
    injected: dict[str, int] = {error_type: 0 for error_type in options.enabled_error_types}
    if count == 0:
        return injected

    for error_type in options.enabled_error_types:
        if error_type == "duplicate_student":
            for index in rng.sample(range(options.students), min(count, options.students)):
                records.students.append(replace(records.students[index], extra_fields={}))
                injected[error_type] += 1
        elif error_type == "missing_student_identifier":
            for index in rng.sample(range(options.students), min(count, options.students)):
                records.students.append(
                    replace(
                        records.students[index],
                        student_id="",
                        local_student_number=(
                            f"{records.students[index].local_student_number}-MISSING-ID"
                        ),
                        extra_fields={},
                    )
                )
                injected[error_type] += 1
        elif error_type == "unknown_school_code":
            for index in rng.sample(
                range(len(records.enrollments)), min(count, len(records.enrollments))
            ):
                records.enrollments[index].school_id = "SYN-UNKNOWN-SCHOOL"
                injected[error_type] += 1
        elif error_type == "invalid_grade":
            for index in rng.sample(range(options.students), min(count, options.students)):
                records.students[index].grade_level = "99"
                injected[error_type] += 1
        elif error_type == "overlapping_enrollment":
            for index in rng.sample(
                range(len(records.enrollments)), min(count, len(records.enrollments))
            ):
                original = records.enrollments[index]
                records.enrollments.append(
                    replace(
                        original,
                        enrollment_id=f"{original.enrollment_id}-OVERLAP",
                        entry_date=(
                            date.fromisoformat(original.entry_date) + timedelta(days=7)
                        ).isoformat(),
                    )
                )
                injected[error_type] += 1
        elif error_type == "attendance_for_unknown_student":
            for index in rng.sample(
                range(len(records.attendance)), min(count, len(records.attendance))
            ):
                records.attendance.append(
                    replace(
                        records.attendance[index],
                        student_id=f"SYN-UNKNOWN-{index:06d}",
                    )
                )
                injected[error_type] += 1
        elif error_type == "duplicate_daily_attendance":
            for index in rng.sample(
                range(len(records.attendance)), min(count, len(records.attendance))
            ):
                records.attendance.append(replace(records.attendance[index]))
                injected[error_type] += 1
        elif error_type == "attendance_outside_enrollment_period":
            for index in rng.sample(range(options.students), min(count, options.students)):
                student = records.students[index]
                records.attendance.append(
                    AttendanceRecord(
                        student_id=student.student_id,
                        district_id=student.district_id,
                        school_id=student.school_id,
                        instructional_date=(days[0] - timedelta(days=1)).isoformat(),
                        attendance_status="present",
                        minutes_attended=INSTRUCTIONAL_MINUTES,
                        reason_code="not_applicable",
                        recorded_at=f"{days[0] - timedelta(days=1)}T16:00:00Z",
                    )
                )
                injected[error_type] += 1
        elif error_type == "invalid_attendance_status":
            for index in rng.sample(
                range(len(records.attendance)), min(count, len(records.attendance))
            ):
                records.attendance[index].attendance_status = "invalid_status"
                injected[error_type] += 1
        elif error_type == "attended_minutes_greater_than_possible":
            for index in rng.sample(
                range(len(records.attendance)), min(count, len(records.attendance))
            ):
                records.attendance[index].minutes_attended = INSTRUCTIONAL_MINUTES + 120
                injected[error_type] += 1
        elif error_type == "invalid_assessment_score":
            for index in rng.sample(
                range(len(records.assessments)), min(count, len(records.assessments))
            ):
                records.assessments[index].scale_score = 999.0
                injected[error_type] += 1
        elif error_type == "schema_drift_field":
            for index in rng.sample(range(options.students), min(count, options.students)):
                records.students[index].extra_fields["unexpected_schema_drift"] = "injected"
                injected[error_type] += 1
    return injected


def _write_csv(
    path: Path,
    fieldnames: tuple[str, ...],
    rows: list[dict[str, object]],
) -> None:
    additional_fields = sorted({key for row in rows for key in row} - set(fieldnames))
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=[*fieldnames, *additional_fields],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_json_lines(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as output:
        for row in rows:
            output.write(json.dumps(row, sort_keys=True, separators=(",", ":")))
            output.write("\n")


def _normalized_xlsx_bytes(rows: list[dict[str, object]]) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    if worksheet is None:
        raise RuntimeError("A new workbook did not create an active worksheet")
    worksheet.title = "assessments"
    worksheet.append(list(ASSESSMENT_FIELDS))
    for row in rows:
        worksheet.append([row[field_name] for field_name in ASSESSMENT_FIELDS])
    workbook.properties.creator = "K12 Data Reliability Hub synthetic generator"
    workbook.properties.created = datetime(2000, 1, 1)
    workbook.properties.modified = datetime(2000, 1, 1)

    source = io.BytesIO()
    workbook.save(source)
    output = io.BytesIO()
    with zipfile.ZipFile(source, "r") as source_zip:  # noqa: SIM117 - Python 3.9
        with zipfile.ZipFile(
            output,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as output_zip:
            for name in sorted(source_zip.namelist()):
                info = zipfile.ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o600 << 16
                content = source_zip.read(name)
                if name == "docProps/core.xml":
                    content = re.sub(
                        rb"(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)",
                        rb"\g<1>2000-01-01T00:00:00Z\g<2>",
                        content,
                    )
                output_zip.writestr(info, content)
    return output.getvalue()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        f"{json.dumps(payload, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for block in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def generate_data(options: GeneratorOptions) -> GenerationResult:
    """Generate one deterministic synthetic dataset and its manifest."""

    baseline, days, schools = _generate_baseline(options)
    baseline_counts = {
        "assessments.xlsx": len(baseline.assessments),
        "attendance_events.jsonl": len(baseline.attendance),
        "enrollments.csv": len(baseline.enrollments),
        "students.csv": len(baseline.students),
    }
    expected_metrics = calculate_expected_metrics(
        baseline,
        instructional_day_count=len(days),
        school_year=options.school_year,
    )
    injected_errors = _inject_errors(baseline, options, days)

    output_path = options.output_directory / options.run_id
    output_path.mkdir(parents=True, exist_ok=True)
    paths = {
        "students.csv": output_path / "students.csv",
        "enrollments.csv": output_path / "enrollments.csv",
        "attendance_events.jsonl": output_path / "attendance_events.jsonl",
        "assessments.xlsx": output_path / "assessments.xlsx",
        "expected_metrics.json": output_path / "expected_metrics.json",
    }
    _write_csv(paths["students.csv"], STUDENT_FIELDS, [row.to_dict() for row in baseline.students])
    _write_csv(
        paths["enrollments.csv"],
        ENROLLMENT_FIELDS,
        [row.to_dict() for row in baseline.enrollments],
    )
    _write_json_lines(
        paths["attendance_events.jsonl"],
        [row.to_dict() for row in baseline.attendance],
    )
    paths["assessments.xlsx"].write_bytes(
        _normalized_xlsx_bytes([row.to_dict() for row in baseline.assessments])
    )
    _write_json(paths["expected_metrics.json"], expected_metrics)

    districts, _ = _regional_structure()
    record_counts = {
        "assessments.xlsx": len(baseline.assessments),
        "attendance_events.jsonl": len(baseline.attendance),
        "enrollments.csv": len(baseline.enrollments),
        "students.csv": len(baseline.students),
    }
    manifest: dict[str, Any] = {
        "arguments": {
            "enabled_error_types": sorted(options.enabled_error_types),
            "error_rate": options.error_rate,
            "school_year": options.school_year,
            "seed": options.seed,
            "students": options.students,
        },
        "baseline_record_counts": baseline_counts,
        "checksums": {name: _sha256(path) for name, path in sorted(paths.items())},
        "injected_errors": injected_errors,
        "instructional_day_count": len(days),
        "record_counts": record_counts,
        "regional_structure": {
            "intermediate_district": {
                "intermediate_district_id": "SYN-ISD-001",
                "name": "Synthetic Intermediate District",
            },
            "local_districts": districts,
            "schools": [school.to_dict() for school in schools],
        },
        "run_id": options.run_id,
        "synthetic_data": True,
    }
    _write_json(output_path / "generation_manifest.json", manifest)
    return GenerationResult(options.run_id, output_path, manifest, expected_metrics)
