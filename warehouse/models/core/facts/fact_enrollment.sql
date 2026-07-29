{{
    config(
        materialized="incremental",
        unique_key="enrollment_key",
        incremental_strategy="merge",
        on_schema_change="fail"
    )
}}

with ranked as (
    select
        *,
        row_number() over (
            partition by enrollment_id
            order by pipeline_started_at desc, source_file_id desc, source_row_number desc
        ) as version_rank
    from {{ ref("trusted_sis_enrollment") }}
)
select
    {{ tokenized_key("enrollment", "enrollment_id") }} as enrollment_key,
    {{ student_key("student_id") }} as student_key,
    {{ stable_key(["district_id"]) }} as district_key,
    {{ stable_key(["school_id"]) }} as school_key,
    {{ stable_key(["academic_year"]) }} as academic_year_key,
    {{ stable_key(["source_system"]) }} as source_system_key,
    to_char(entry_date, 'YYYYMMDD')::integer as entry_date_key,
    case when exit_date is not null then to_char(exit_date, 'YYYYMMDD')::integer end
        as exit_date_key,
    grade_level,
    entry_date,
    exit_date,
    enrollment_status,
    pipeline_run_id,
    source_file_id,
    source_row_number,
    source_system,
    source_schema_version,
    ingested_at,
    pipeline_started_at
from ranked
where version_rank = 1
