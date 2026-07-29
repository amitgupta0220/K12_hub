"""Reusable configuration-driven data-quality rule engine."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import Engine, text

from k12hub.contracts import (
    ConfigurationBundle,
    DataQualityRule,
    RuleType,
    SourceContract,
)
from k12hub.database import transaction
from k12hub.staging import STAGING_BUSINESS_COLUMNS, normalize_column_name


class DataQualityError(RuntimeError):
    """Raised when a quality run cannot be evaluated or persisted."""


@dataclass(frozen=True)
class DatasetRow:
    """One staged row available to rule evaluators."""

    dataset: str
    pipeline_run_id: UUID
    source_file_id: UUID
    source_system: str
    source_row_number: int
    source_schema_version: str
    raw_payload: dict[str, Any]
    values: dict[str, Any]


@dataclass(frozen=True)
class SourceFileProfile:
    """Current and prior counts for one expected source file."""

    source_file_id: UUID
    source_system: str
    original_filename: str
    row_count: int
    previous_row_count: int | None


@dataclass(frozen=True)
class QualityContext:
    """All staged and pipeline metadata used by a quality run."""

    pipeline_run_id: UUID
    rows_by_dataset: dict[str, tuple[DatasetRow, ...]]
    source_files: tuple[SourceFileProfile, ...]
    contracts_by_dataset: dict[str, SourceContract]


@dataclass(frozen=True)
class QualityFailure:
    """One rule failure tied to a source row or pipeline-level row zero."""

    source_file_id: UUID | None
    source_system: str
    source_row_number: int
    raw_payload: dict[str, Any]
    message: str


@dataclass(frozen=True)
class RuleEvaluation:
    """Aggregate and row-level results for one enabled rule."""

    rule: DataQualityRule
    evaluated_row_count: int
    failures: tuple[QualityFailure, ...]

    @property
    def failure_count(self) -> int:
        return len(self.failures)


@dataclass(frozen=True)
class RuleSummary:
    """Persisted aggregate result for terminal and dashboard use."""

    rule_id: str
    severity: str
    blocking: bool
    evaluated: int
    failures: int


@dataclass(frozen=True)
class QualityRunResult:
    """Summary of one persisted quality-rule run."""

    data_quality_rule_run_id: UUID
    pipeline_run_id: UUID
    status: str
    enabled_rules: int
    evaluated_rows: int
    failures: int
    blocking_failures: int
    rule_summaries: tuple[RuleSummary, ...]


class QualityStore(Protocol):
    """Persistence boundary used by the quality service."""

    def load_context(
        self,
        pipeline_run_id: UUID,
        configuration: ConfigurationBundle,
    ) -> QualityContext:
        """Load allowlisted staging rows and pipeline metadata."""

    def persist(
        self,
        context: QualityContext,
        evaluations: Sequence[RuleEvaluation],
    ) -> QualityRunResult:
        """Persist a rule run, aggregates, failures, and quarantine copies."""


def _required_string(parameters: Mapping[str, Any], name: str) -> str:
    value = parameters.get(name)
    if not isinstance(value, str) or not value:
        raise DataQualityError(f"Rule parameter {name!r} must be a non-empty string")
    return value


def _required_strings(parameters: Mapping[str, Any], name: str) -> tuple[str, ...]:
    value = parameters.get(name)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        raise DataQualityError(f"Rule parameter {name!r} must be a non-empty string list")
    return tuple(value)


def _required_number(parameters: Mapping[str, Any], name: str) -> Decimal:
    value = parameters.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise DataQualityError(f"Rule parameter {name!r} must be numeric")
    try:
        return Decimal(str(value))
    except Exception as error:
        raise DataQualityError(f"Rule parameter {name!r} must be numeric") from error


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _failure(row: DatasetRow, message: str) -> QualityFailure:
    return QualityFailure(
        source_file_id=row.source_file_id,
        source_system=row.source_system,
        source_row_number=row.source_row_number,
        raw_payload=row.raw_payload,
        message=message,
    )


class DataQualityRuleEngine:
    """Dispatch enabled YAML rules to reusable evaluator implementations."""

    def __init__(self) -> None:
        self._evaluators: dict[
            RuleType,
            Callable[[DataQualityRule, QualityContext], RuleEvaluation],
        ] = {
            RuleType.REQUIRED: self._required,
            RuleType.UNIQUE: self._unique,
            RuleType.SCHOOL_EXISTS: self._school_exists,
            RuleType.REFERENCE_EXISTS: self._reference_exists,
            RuleType.DATE_ORDER: self._date_order,
            RuleType.ACCEPTED_VALUES: self._accepted_values,
            RuleType.NO_OVERLAP: self._no_overlap,
            RuleType.WITHIN_ENROLLMENT: self._within_enrollment,
            RuleType.POSITIVE_PARAMETER: self._positive_parameter,
            RuleType.MAXIMUM: self._maximum,
            RuleType.RANGE: self._range,
            RuleType.ROW_COUNT_CHANGE: self._row_count_change,
            RuleType.REQUIRED_FILE: self._required_file,
            RuleType.SCHEMA_VERSION: self._schema_version,
        }

    def evaluate(
        self,
        context: QualityContext,
        rules: Sequence[DataQualityRule],
    ) -> tuple[RuleEvaluation, ...]:
        """Evaluate enabled rules in configured order."""

        evaluations: list[RuleEvaluation] = []
        for rule in rules:
            if not rule.enabled:
                continue
            evaluator = self._evaluators.get(rule.rule_type)
            if evaluator is None:  # pragma: no cover - enum and registry evolve together
                raise DataQualityError(f"Unsupported rule type: {rule.rule_type}")
            evaluations.append(evaluator(rule, context))
        return tuple(evaluations)

    @staticmethod
    def _rows(rule: DataQualityRule, context: QualityContext) -> tuple[DatasetRow, ...]:
        rows = context.rows_by_dataset.get(rule.dataset)
        if rows is None:
            raise DataQualityError(
                f"Rule {rule.rule_id} references unloaded dataset {rule.dataset}"
            )
        return rows

    def _required(self, rule: DataQualityRule, context: QualityContext) -> RuleEvaluation:
        field = _required_string(rule.parameters, "field")
        rows = self._rows(rule, context)
        failures = tuple(
            _failure(row, f"{field} is required")
            for row in rows
            if _is_missing(row.values.get(field))
        )
        return RuleEvaluation(rule, len(rows), failures)

    def _unique(self, rule: DataQualityRule, context: QualityContext) -> RuleEvaluation:
        fields = _required_strings(rule.parameters, "fields")
        rows = self._rows(rule, context)
        seen: set[tuple[UUID, tuple[Any, ...]]] = set()
        failures: list[QualityFailure] = []
        for row in rows:
            values = tuple(row.values.get(field) for field in fields)
            if any(_is_missing(value) for value in values):
                continue
            key = (row.source_file_id, values)
            if key in seen:
                failures.append(
                    _failure(row, f"duplicate value for {', '.join(fields)}: {values!r}")
                )
            else:
                seen.add(key)
        return RuleEvaluation(rule, len(rows), tuple(failures))

    def _school_exists(self, rule: DataQualityRule, context: QualityContext) -> RuleEvaluation:
        field = _required_string(rule.parameters, "field")
        pattern = re.compile(_required_string(rule.parameters, "pattern"))
        rows = self._rows(rule, context)
        failures = tuple(
            _failure(row, f"{field} {row.values.get(field)!r} is not a registered school code")
            for row in rows
            if _is_missing(row.values.get(field))
            or pattern.fullmatch(str(row.values.get(field))) is None
        )
        return RuleEvaluation(rule, len(rows), failures)

    def _reference_exists(
        self,
        rule: DataQualityRule,
        context: QualityContext,
    ) -> RuleEvaluation:
        field = _required_string(rule.parameters, "field")
        reference_dataset = _required_string(rule.parameters, "reference_dataset")
        reference_field = _required_string(rule.parameters, "reference_field")
        rows = self._rows(rule, context)
        reference_rows = context.rows_by_dataset.get(reference_dataset, ())
        allowed = {
            row.values.get(reference_field)
            for row in reference_rows
            if not _is_missing(row.values.get(reference_field))
        }
        failures = tuple(
            _failure(
                row, f"{field} {row.values.get(field)!r} does not exist in {reference_dataset}"
            )
            for row in rows
            if row.values.get(field) not in allowed
        )
        return RuleEvaluation(rule, len(rows), failures)

    def _date_order(self, rule: DataQualityRule, context: QualityContext) -> RuleEvaluation:
        start_field = _required_string(rule.parameters, "start_field")
        end_field = _required_string(rule.parameters, "end_field")
        rows = self._rows(rule, context)
        failures = tuple(
            _failure(row, f"{start_field} must not occur after {end_field}")
            for row in rows
            if row.values.get(end_field) is not None
            and row.values.get(start_field) is not None
            and row.values[start_field] > row.values[end_field]
        )
        return RuleEvaluation(rule, len(rows), failures)

    def _accepted_values(
        self,
        rule: DataQualityRule,
        context: QualityContext,
    ) -> RuleEvaluation:
        field = _required_string(rule.parameters, "field")
        accepted = set(_required_strings(rule.parameters, "values"))
        rows = self._rows(rule, context)
        failures = tuple(
            _failure(row, f"{field} {row.values.get(field)!r} is not an accepted value")
            for row in rows
            if str(row.values.get(field)) not in accepted
        )
        return RuleEvaluation(rule, len(rows), failures)

    def _no_overlap(self, rule: DataQualityRule, context: QualityContext) -> RuleEvaluation:
        entity_field = _required_string(rule.parameters, "entity_field")
        start_field = _required_string(rule.parameters, "start_field")
        end_field = _required_string(rule.parameters, "end_field")
        rows = self._rows(rule, context)
        by_entity: dict[Any, list[DatasetRow]] = defaultdict(list)
        for row in rows:
            by_entity[row.values.get(entity_field)].append(row)
        failures: list[QualityFailure] = []
        for entity, entity_rows in by_entity.items():
            previous_end: date | None = None
            for row in sorted(entity_rows, key=lambda item: item.values[start_field]):
                start = row.values[start_field]
                end = row.values.get(end_field) or date.max
                if previous_end is not None and start <= previous_end:
                    failures.append(_failure(row, f"overlapping enrollment period for {entity!r}"))
                if previous_end is None or end > previous_end:
                    previous_end = end
        return RuleEvaluation(rule, len(rows), tuple(failures))

    def _within_enrollment(
        self,
        rule: DataQualityRule,
        context: QualityContext,
    ) -> RuleEvaluation:
        entity_field = _required_string(rule.parameters, "entity_field")
        date_field = _required_string(rule.parameters, "date_field")
        enrollment_dataset = _required_string(rule.parameters, "enrollment_dataset")
        enrollment_entity_field = _required_string(
            rule.parameters,
            "enrollment_entity_field",
        )
        start_field = _required_string(rule.parameters, "start_field")
        end_field = _required_string(rule.parameters, "end_field")
        rows = self._rows(rule, context)
        enrollments: dict[Any, list[tuple[date, date]]] = defaultdict(list)
        for enrollment in context.rows_by_dataset.get(enrollment_dataset, ()):
            enrollments[enrollment.values.get(enrollment_entity_field)].append(
                (
                    enrollment.values[start_field],
                    enrollment.values.get(end_field) or date.max,
                )
            )
        failures = tuple(
            _failure(
                row,
                f"{date_field} is outside an enrollment period for "
                f"{entity_field} {row.values.get(entity_field)!r}",
            )
            for row in rows
            if not any(
                start <= row.values[date_field] <= end
                for start, end in enrollments.get(row.values.get(entity_field), ())
            )
        )
        return RuleEvaluation(rule, len(rows), failures)

    def _positive_parameter(
        self,
        rule: DataQualityRule,
        context: QualityContext,
    ) -> RuleEvaluation:
        parameter_name = _required_string(rule.parameters, "parameter_name")
        value = _required_number(rule.parameters, parameter_name)
        rows = self._rows(rule, context)
        failures = (
            tuple(_failure(row, f"configured {parameter_name} must be positive") for row in rows)
            if value <= 0
            else ()
        )
        return RuleEvaluation(rule, len(rows), failures)

    def _maximum(self, rule: DataQualityRule, context: QualityContext) -> RuleEvaluation:
        field = _required_string(rule.parameters, "field")
        maximum = _required_number(rule.parameters, "maximum")
        rows = self._rows(rule, context)
        failures = tuple(
            _failure(row, f"{field} {row.values.get(field)!r} exceeds maximum {maximum}")
            for row in rows
            if row.values.get(field) is not None and Decimal(str(row.values[field])) > maximum
        )
        return RuleEvaluation(rule, len(rows), failures)

    def _range(self, rule: DataQualityRule, context: QualityContext) -> RuleEvaluation:
        field = _required_string(rule.parameters, "field")
        minimum = _required_number(rule.parameters, "minimum")
        maximum = _required_number(rule.parameters, "maximum")
        rows = self._rows(rule, context)
        failures = tuple(
            _failure(
                row,
                f"{field} {row.values.get(field)!r} is outside [{minimum}, {maximum}]",
            )
            for row in rows
            if row.values.get(field) is None
            or not minimum <= Decimal(str(row.values[field])) <= maximum
        )
        return RuleEvaluation(rule, len(rows), failures)

    def _row_count_change(
        self,
        rule: DataQualityRule,
        context: QualityContext,
    ) -> RuleEvaluation:
        threshold = _required_number(rule.parameters, "percent_threshold")
        failures: list[QualityFailure] = []
        for source_file in context.source_files:
            previous = source_file.previous_row_count
            if previous is None:
                continue
            change = (
                Decimal("0")
                if previous == source_file.row_count
                else Decimal("Infinity")
                if previous == 0
                else (
                    Decimal(abs(source_file.row_count - previous))
                    / Decimal(previous)
                    * Decimal(100)
                )
            )
            if change > threshold:
                failures.append(
                    QualityFailure(
                        source_file_id=source_file.source_file_id,
                        source_system=source_file.source_system,
                        source_row_number=0,
                        raw_payload={
                            "filename": source_file.original_filename,
                            "row_count": source_file.row_count,
                            "previous_row_count": previous,
                        },
                        message=(
                            f"{source_file.original_filename} row count changed by "
                            f"{change}% (threshold {threshold}%)"
                        ),
                    )
                )
        return RuleEvaluation(rule, len(context.source_files), tuple(failures))

    def _required_file(
        self,
        rule: DataQualityRule,
        context: QualityContext,
    ) -> RuleEvaluation:
        required = _required_strings(rule.parameters, "filenames")
        arrived = {source_file.original_filename for source_file in context.source_files}
        failures = tuple(
            QualityFailure(
                source_file_id=None,
                source_system="pipeline",
                source_row_number=0,
                raw_payload={"missing_filename": filename},
                message=f"required source file did not arrive: {filename}",
            )
            for filename in required
            if filename not in arrived
        )
        return RuleEvaluation(rule, len(required), failures)

    def _schema_version(
        self,
        rule: DataQualityRule,
        context: QualityContext,
    ) -> RuleEvaluation:
        detect_unknown = rule.parameters.get("detect_unknown_fields")
        if not isinstance(detect_unknown, bool):
            raise DataQualityError("Rule parameter 'detect_unknown_fields' must be boolean")
        all_rows = tuple(row for rows in context.rows_by_dataset.values() for row in rows)
        failures: list[QualityFailure] = []
        for row in all_rows:
            contract = context.contracts_by_dataset[row.dataset]
            unknown_fields: set[str] = set()
            if detect_unknown:
                expected = {field.name for field in contract.expected_fields}
                unknown_fields = {
                    normalize_column_name(field)
                    for field in row.raw_payload
                    if normalize_column_name(field) not in expected
                }
            if row.source_schema_version != contract.schema_version or unknown_fields:
                details = []
                if row.source_schema_version != contract.schema_version:
                    details.append(
                        f"version {row.source_schema_version!r} "
                        f"expected {contract.schema_version!r}"
                    )
                if unknown_fields:
                    details.append(f"unknown fields {sorted(unknown_fields)}")
                failures.append(_failure(row, "; ".join(details)))
        return RuleEvaluation(rule, len(all_rows), tuple(failures))


def _rule_uuid(rule_code: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"k12hub:data-quality:{rule_code}")


class PostgresQualityStore:
    """PostgreSQL context loader and quality audit writer."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def load_context(
        self,
        pipeline_run_id: UUID,
        configuration: ConfigurationBundle,
    ) -> QualityContext:
        contracts_by_dataset = {
            contract.destination_staging_table: contract
            for contract in configuration.contracts.values()
        }
        rows_by_dataset: dict[str, tuple[DatasetRow, ...]] = {}
        with transaction(engine=self._engine) as connection:
            pipeline_exists = connection.execute(
                text("SELECT 1 FROM audit.pipeline_run WHERE pipeline_run_id = :pipeline_run_id"),
                {"pipeline_run_id": pipeline_run_id},
            ).first()
            if pipeline_exists is None:
                raise DataQualityError(f"Pipeline run does not exist: {pipeline_run_id}")

            for dataset, business_columns in STAGING_BUSINESS_COLUMNS.items():
                table_name = dataset.removeprefix("staging.")
                selected_columns = ", ".join(f"staged.{column}" for column in business_columns)
                result = connection.execute(
                    text(
                        f"""
                        SELECT staged.pipeline_run_id, staged.source_file_id,
                               source_file.source_system, staged.source_row_number,
                               staged.source_schema_version, staged.raw_payload,
                               {selected_columns}
                        FROM staging.{table_name} AS staged
                        JOIN audit.source_file AS source_file
                          ON source_file.source_file_id = staged.source_file_id
                        WHERE staged.pipeline_run_id = :pipeline_run_id
                        ORDER BY staged.source_file_id, staged.source_row_number
                        """
                    ),
                    {"pipeline_run_id": pipeline_run_id},
                ).mappings()
                rows_by_dataset[dataset] = tuple(
                    DatasetRow(
                        dataset=dataset,
                        pipeline_run_id=UUID(str(row["pipeline_run_id"])),
                        source_file_id=UUID(str(row["source_file_id"])),
                        source_system=str(row["source_system"]),
                        source_row_number=int(row["source_row_number"]),
                        source_schema_version=str(row["source_schema_version"]),
                        raw_payload=dict(row["raw_payload"]),
                        values={column: row[column] for column in business_columns},
                    )
                    for row in result
                )

            source_file_rows = connection.execute(
                text(
                    """
                    SELECT current_file.source_file_id,
                           current_file.source_system,
                           current_file.original_filename,
                           COALESCE(current_file.row_count, 0) AS row_count,
                           (
                               SELECT previous_file.row_count
                               FROM audit.source_file AS previous_file
                               JOIN audit.pipeline_run AS previous_run
                                 ON previous_run.pipeline_run_id =
                                    previous_file.pipeline_run_id
                               WHERE previous_run.pipeline_name =
                                     current_run.pipeline_name
                                 AND previous_run.started_at < current_run.started_at
                                 AND previous_file.original_filename =
                                     current_file.original_filename
                                 AND previous_file.source_system =
                                     current_file.source_system
                                 AND previous_file.status = 'loaded'
                                 AND previous_file.row_count IS NOT NULL
                               ORDER BY previous_run.started_at DESC
                               LIMIT 1
                           ) AS previous_row_count
                    FROM audit.source_file AS current_file
                    JOIN audit.pipeline_run AS current_run
                      ON current_run.pipeline_run_id = current_file.pipeline_run_id
                    WHERE current_file.pipeline_run_id = :pipeline_run_id
                      AND current_file.status = 'loaded'
                    ORDER BY current_file.original_filename
                    """
                ),
                {"pipeline_run_id": pipeline_run_id},
            ).mappings()
            source_files = tuple(
                SourceFileProfile(
                    source_file_id=UUID(str(row["source_file_id"])),
                    source_system=str(row["source_system"]),
                    original_filename=str(row["original_filename"]),
                    row_count=int(row["row_count"]),
                    previous_row_count=(
                        int(row["previous_row_count"])
                        if row["previous_row_count"] is not None
                        else None
                    ),
                )
                for row in source_file_rows
            )

        return QualityContext(
            pipeline_run_id=pipeline_run_id,
            rows_by_dataset=rows_by_dataset,
            source_files=source_files,
            contracts_by_dataset=contracts_by_dataset,
        )

    @staticmethod
    def _register_rule(
        connection: Any,
        rule: DataQualityRule,
    ) -> UUID:
        internal_rule_id = _rule_uuid(rule.rule_id)
        stored_id = connection.execute(
            text(
                """
                INSERT INTO metadata.data_quality_rule (
                    rule_id, rule_code, name, description, dataset, rule_type,
                    severity, blocking, remediation_guidance, configuration, is_active
                )
                VALUES (
                    :rule_id, :rule_code, :name, :description, :dataset, :rule_type,
                    :severity, :blocking, :remediation_guidance,
                    CAST(:configuration AS JSONB), :is_active
                )
                ON CONFLICT (rule_code) DO UPDATE
                SET name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    dataset = EXCLUDED.dataset,
                    rule_type = EXCLUDED.rule_type,
                    severity = EXCLUDED.severity,
                    blocking = EXCLUDED.blocking,
                    remediation_guidance = EXCLUDED.remediation_guidance,
                    configuration = EXCLUDED.configuration,
                    is_active = EXCLUDED.is_active,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING rule_id
                """
            ),
            {
                "rule_id": internal_rule_id,
                "rule_code": rule.rule_id,
                "name": rule.name,
                "description": rule.description,
                "dataset": rule.dataset,
                "rule_type": rule.rule_type.value,
                "severity": rule.severity.value,
                "blocking": rule.blocking,
                "remediation_guidance": rule.remediation_guidance,
                "configuration": json.dumps(rule.parameters, sort_keys=True),
                "is_active": rule.enabled,
            },
        ).scalar_one()
        return UUID(str(stored_id))

    def persist(
        self,
        context: QualityContext,
        evaluations: Sequence[RuleEvaluation],
    ) -> QualityRunResult:
        failure_count = sum(evaluation.failure_count for evaluation in evaluations)
        blocking_failure_count = sum(
            evaluation.failure_count for evaluation in evaluations if evaluation.rule.blocking
        )
        evaluated_count = sum(evaluation.evaluated_row_count for evaluation in evaluations)
        status = "failed" if blocking_failure_count else "passed"

        with transaction(engine=self._engine) as connection:
            rule_ids = {
                evaluation.rule.rule_id: self._register_rule(
                    connection,
                    evaluation.rule,
                )
                for evaluation in evaluations
            }
            quality_run_id = UUID(
                str(
                    connection.execute(
                        text(
                            """
                            INSERT INTO audit.data_quality_rule_run (
                                pipeline_run_id, finished_at, status,
                                enabled_rule_count, evaluated_row_count,
                                failure_count, blocking_failure_count
                            )
                            VALUES (
                                :pipeline_run_id, CURRENT_TIMESTAMP, :status,
                                :enabled_rule_count, :evaluated_row_count,
                                :failure_count, :blocking_failure_count
                            )
                            RETURNING data_quality_rule_run_id
                            """
                        ),
                        {
                            "pipeline_run_id": context.pipeline_run_id,
                            "status": status,
                            "enabled_rule_count": len(evaluations),
                            "evaluated_row_count": evaluated_count,
                            "failure_count": failure_count,
                            "blocking_failure_count": blocking_failure_count,
                        },
                    ).scalar_one()
                )
            )

            for evaluation in evaluations:
                rule = evaluation.rule
                internal_rule_id = rule_ids[rule.rule_id]
                connection.execute(
                    text(
                        """
                        INSERT INTO audit.data_quality_rule_result (
                            data_quality_rule_run_id, pipeline_run_id, rule_id,
                            rule_code, dataset, severity, blocking,
                            evaluated_row_count, failure_count, status
                        )
                        VALUES (
                            :quality_run_id, :pipeline_run_id, :rule_id,
                            :rule_code, :dataset, :severity, :blocking,
                            :evaluated_count, :failure_count, :status
                        )
                        """
                    ),
                    {
                        "quality_run_id": quality_run_id,
                        "pipeline_run_id": context.pipeline_run_id,
                        "rule_id": internal_rule_id,
                        "rule_code": rule.rule_id,
                        "dataset": rule.dataset,
                        "severity": rule.severity.value,
                        "blocking": rule.blocking,
                        "evaluated_count": evaluation.evaluated_row_count,
                        "failure_count": evaluation.failure_count,
                        "status": "failed" if evaluation.failures else "passed",
                    },
                )
                for failure in evaluation.failures:
                    payload = json.dumps(failure.raw_payload, sort_keys=True, default=str)
                    connection.execute(
                        text(
                            """
                            INSERT INTO audit.data_quality_failure (
                                data_quality_rule_run_id, pipeline_run_id,
                                source_file_id, source_row_number, rule_id,
                                rule_code, dataset, severity, blocking, message,
                                remediation_guidance, raw_payload
                            )
                            VALUES (
                                :quality_run_id, :pipeline_run_id,
                                :source_file_id, :source_row_number, :rule_id,
                                :rule_code, :dataset, :severity, :blocking, :message,
                                :remediation_guidance, CAST(:raw_payload AS JSONB)
                            )
                            """
                        ),
                        {
                            "quality_run_id": quality_run_id,
                            "pipeline_run_id": context.pipeline_run_id,
                            "source_file_id": failure.source_file_id,
                            "source_row_number": failure.source_row_number,
                            "rule_id": internal_rule_id,
                            "rule_code": rule.rule_id,
                            "dataset": rule.dataset,
                            "severity": rule.severity.value,
                            "blocking": rule.blocking,
                            "message": failure.message,
                            "remediation_guidance": rule.remediation_guidance,
                            "raw_payload": payload,
                        },
                    )
                    if rule.blocking:
                        connection.execute(
                            text(
                                """
                                INSERT INTO quarantine.rejected_record (
                                    pipeline_run_id, source_file_id, source_system,
                                    source_row_number, rule_id, rule_code, severity,
                                    error_message, remediation_guidance, raw_payload
                                )
                                VALUES (
                                    :pipeline_run_id, :source_file_id, :source_system,
                                    :source_row_number, :rule_id, :rule_code, :severity,
                                    :message, :remediation_guidance,
                                    CAST(:raw_payload AS JSONB)
                                )
                                ON CONFLICT (
                                    source_file_id, source_row_number, rule_id
                                ) DO NOTHING
                                """
                            ),
                            {
                                "pipeline_run_id": context.pipeline_run_id,
                                "source_file_id": failure.source_file_id,
                                "source_system": failure.source_system,
                                "source_row_number": failure.source_row_number,
                                "rule_id": internal_rule_id,
                                "rule_code": rule.rule_id,
                                "severity": rule.severity.value,
                                "message": failure.message,
                                "remediation_guidance": rule.remediation_guidance,
                                "raw_payload": payload,
                            },
                        )

        return QualityRunResult(
            data_quality_rule_run_id=quality_run_id,
            pipeline_run_id=context.pipeline_run_id,
            status=status,
            enabled_rules=len(evaluations),
            evaluated_rows=evaluated_count,
            failures=failure_count,
            blocking_failures=blocking_failure_count,
            rule_summaries=tuple(
                RuleSummary(
                    rule_id=evaluation.rule.rule_id,
                    severity=evaluation.rule.severity.value,
                    blocking=evaluation.rule.blocking,
                    evaluated=evaluation.evaluated_row_count,
                    failures=evaluation.failure_count,
                )
                for evaluation in evaluations
            ),
        )


class DataQualityService:
    """Coordinate context loading, rule evaluation, and audit persistence."""

    def __init__(
        self,
        store: QualityStore,
        engine: DataQualityRuleEngine | None = None,
    ) -> None:
        self._store = store
        self._engine = engine or DataQualityRuleEngine()

    def validate(
        self,
        pipeline_run_id: UUID,
        configuration: ConfigurationBundle,
    ) -> QualityRunResult:
        """Run all enabled configured rules for one pipeline run."""

        context = self._store.load_context(pipeline_run_id, configuration)
        evaluations = self._engine.evaluate(
            context,
            configuration.data_quality_rules.rules,
        )
        return self._store.persist(context, evaluations)
