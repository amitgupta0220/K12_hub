"""Typed models and loaders for configuration-driven source contracts."""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    ValidationError,
    model_validator,
)
from typing_extensions import Self
from yaml import YAMLError


class ConfigurationFileError(ValueError):
    """Raised when a configuration file cannot be parsed or validated."""


class StrictModel(BaseModel):
    """Base model that rejects undeclared configuration keys."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class DataCategory(str, Enum):
    """Supported provenance categories."""

    SYNTHETIC = "synthetic"
    PUBLIC = "public"


class FileFormat(str, Enum):
    """Supported declarative source formats."""

    CSV = "csv"
    JSON_LINES = "jsonl"
    XLSX = "xlsx"


class DataType(str, Enum):
    """Supported contract field types."""

    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"


class SensitiveClassification(str, Enum):
    """Field-level sensitivity classifications."""

    DIRECT_IDENTIFIER = "direct_identifier"
    QUASI_IDENTIFIER = "quasi_identifier"
    SENSITIVE = "sensitive"
    OPERATIONAL = "operational"
    NON_SENSITIVE = "non_sensitive"


class RuleType(str, Enum):
    """Declarative data-quality rule types."""

    REQUIRED = "required"
    UNIQUE = "unique"
    ACCEPTED_VALUES = "accepted_values"
    DATE_ORDER = "date_order"
    MINIMUM = "minimum"


class Severity(str, Enum):
    """Supported data-quality severities."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class SourceSystem(StrictModel):
    """One simulated or public source system."""

    name: StrictStr
    description: StrictStr
    data_category: DataCategory
    enabled: StrictBool = True
    contracts: list[StrictStr]


class SourceSystemsConfig(StrictModel):
    """Registered source systems."""

    schema_version: StrictStr
    source_systems: list[SourceSystem]

    @model_validator(mode="after")
    def validate_unique_names(self) -> Self:
        names = [source.name for source in self.source_systems]
        if len(names) != len(set(names)):
            raise ValueError("source system names must be unique")
        return self


class ContractField(StrictModel):
    """One expected field in a source contract."""

    name: StrictStr
    data_type: DataType
    accepted_values: list[StrictStr] | None = None
    sensitive_classification: SensitiveClassification

    @model_validator(mode="after")
    def validate_accepted_values(self) -> Self:
        if self.accepted_values is not None and not self.accepted_values:
            raise ValueError("accepted_values must contain at least one value when provided")
        return self


class SourceContract(StrictModel):
    """Validated source-file contract."""

    source_name: StrictStr
    source_system: StrictStr
    description: StrictStr
    file_pattern: StrictStr
    file_format: FileFormat
    expected_fields: list[ContractField]
    required_fields: list[StrictStr]
    natural_key: list[StrictStr]
    expected_grain: StrictStr
    schema_version: StrictStr
    destination_staging_table: StrictStr = Field(pattern=r"^staging\.[a-z][a-z0-9_]*$")

    @model_validator(mode="after")
    def validate_field_references(self) -> Self:
        field_names = [field.name for field in self.expected_fields]
        if len(field_names) != len(set(field_names)):
            raise ValueError("expected field names must be unique")
        if not self.required_fields:
            raise ValueError("required_fields must contain at least one field")
        if not self.natural_key:
            raise ValueError("natural_key must contain at least one field")

        unknown_required = sorted(set(self.required_fields) - set(field_names))
        if unknown_required:
            raise ValueError(f"required_fields contains unknown fields: {unknown_required}")
        unknown_key_fields = sorted(set(self.natural_key) - set(field_names))
        if unknown_key_fields:
            raise ValueError(f"natural_key contains unknown fields: {unknown_key_fields}")
        return self


class DataQualityRule(StrictModel):
    """One declarative data-quality rule."""

    rule_id: StrictStr
    description: StrictStr
    contract: StrictStr
    field: StrictStr | None = None
    rule_type: RuleType
    severity: Severity
    parameters: dict[StrictStr, Any] = Field(default_factory=dict)


class DataQualityRulesConfig(StrictModel):
    """Registered data-quality rules."""

    schema_version: StrictStr
    rules: list[DataQualityRule]

    @model_validator(mode="after")
    def validate_unique_rule_ids(self) -> Self:
        rule_ids = [rule.rule_id for rule in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("data-quality rule IDs must be unique")
        return self


class PrivacyConfig(StrictModel):
    """Privacy controls used by later delivery layers."""

    schema_version: StrictStr
    small_group_threshold: StrictInt = Field(ge=1)
    direct_identifier_fields: list[StrictStr]
    prohibited_dashboard_fields: list[StrictStr]
    allowed_aggregate_dimensions: list[StrictStr]

    @model_validator(mode="after")
    def validate_privacy_lists(self) -> Self:
        direct = set(self.direct_identifier_fields)
        prohibited = set(self.prohibited_dashboard_fields)
        allowed = set(self.allowed_aggregate_dimensions)
        if not direct <= prohibited:
            missing = sorted(direct - prohibited)
            raise ValueError(f"direct identifiers must be prohibited from dashboards: {missing}")
        overlap = sorted(prohibited & allowed)
        if overlap:
            raise ValueError(
                f"dashboard-prohibited fields cannot be aggregate dimensions: {overlap}"
            )
        return self


class MetricDefinition(StrictModel):
    """A metric name and description without calculation logic."""

    name: StrictStr
    description: StrictStr


class MetricsConfig(StrictModel):
    """Registered metric names and descriptions."""

    schema_version: StrictStr
    metrics: list[MetricDefinition]

    @model_validator(mode="after")
    def validate_unique_metric_names(self) -> Self:
        names = [metric.name for metric in self.metrics]
        if len(names) != len(set(names)):
            raise ValueError("metric names must be unique")
        return self


class ConfigurationBundle(StrictModel):
    """All validated project configuration files."""

    source_systems: SourceSystemsConfig
    contracts: dict[StrictStr, SourceContract]
    data_quality_rules: DataQualityRulesConfig
    privacy: PrivacyConfig
    metrics: MetricsConfig

    @model_validator(mode="after")
    def validate_cross_file_references(self) -> Self:
        systems = {source.name: source for source in self.source_systems.source_systems}
        contract_names = set(self.contracts)

        for contract_name, contract in self.contracts.items():
            if contract.source_name != contract_name:
                raise ValueError(
                    f"contract {contract_name!r} must declare source_name {contract_name!r}"
                )
            source_system = systems.get(contract.source_system)
            if source_system is None:
                raise ValueError(
                    f"contract {contract_name!r} references unknown source system "
                    f"{contract.source_system!r}"
                )
            if contract_name not in source_system.contracts:
                raise ValueError(
                    f"source system {source_system.name!r} does not register contract "
                    f"{contract_name!r}"
                )

        registered_contracts = {
            contract_name
            for source_system in systems.values()
            for contract_name in source_system.contracts
        }
        missing_contracts = sorted(registered_contracts - contract_names)
        if missing_contracts:
            raise ValueError(f"source systems reference missing contracts: {missing_contracts}")

        for rule in self.data_quality_rules.rules:
            referenced_contract = self.contracts.get(rule.contract)
            if referenced_contract is None:
                raise ValueError(
                    f"data-quality rule {rule.rule_id!r} references unknown contract "
                    f"{rule.contract!r}"
                )
            if rule.field is not None:
                field_names = {field.name for field in referenced_contract.expected_fields}
                if rule.field not in field_names:
                    raise ValueError(
                        f"data-quality rule {rule.rule_id!r} references unknown field "
                        f"{rule.field!r}"
                    )
        return self


ModelT = TypeVar("ModelT", bound=BaseModel)
CONTRACT_NAMES = ("sis_students", "sis_enrollment", "attendance_events", "assessments")


def load_yaml_model(path: Path, model_type: type[ModelT]) -> ModelT:
    """Load one YAML file and validate it as the requested model."""

    try:
        raw_data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ConfigurationFileError(f"{path}: unable to read configuration: {error}") from error
    except YAMLError as error:
        raise ConfigurationFileError(f"{path}: invalid YAML: {error}") from error

    if not isinstance(raw_data, Mapping):
        raise ConfigurationFileError(f"{path}: top-level YAML value must be a mapping")

    try:
        return model_type.model_validate(raw_data)
    except ValidationError as error:
        raise ConfigurationFileError(
            f"{path}: configuration validation failed:\n{error}"
        ) from error


def load_source_contract(path: Path) -> SourceContract:
    """Load and validate one source contract."""

    return load_yaml_model(path, SourceContract)


def load_configuration(config_dir: Path = Path("config")) -> ConfigurationBundle:
    """Load and cross-validate the complete configuration bundle."""

    contracts = {
        name: load_source_contract(config_dir / "contracts" / f"{name}.yml")
        for name in CONTRACT_NAMES
    }
    try:
        return ConfigurationBundle(
            source_systems=load_yaml_model(
                config_dir / "source_systems.yml",
                SourceSystemsConfig,
            ),
            contracts=contracts,
            data_quality_rules=load_yaml_model(
                config_dir / "data_quality_rules.yml",
                DataQualityRulesConfig,
            ),
            privacy=load_yaml_model(config_dir / "privacy.yml", PrivacyConfig),
            metrics=load_yaml_model(config_dir / "metrics.yml", MetricsConfig),
        )
    except ValidationError as error:
        raise ConfigurationFileError(
            f"{config_dir}: cross-file configuration validation failed:\n{error}"
        ) from error
