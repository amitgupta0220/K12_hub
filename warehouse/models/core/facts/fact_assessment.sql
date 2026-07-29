{{
    config(
        materialized="incremental",
        unique_key="assessment_key",
        incremental_strategy="merge",
        on_schema_change="fail"
    )
}}

with ranked as (
    select
        *,
        row_number() over (
            partition by assessment_event_id
            order by pipeline_started_at desc, source_file_id desc, source_row_number desc
        ) as version_rank
    from {{ ref("trusted_assessment_event") }}
)
select
    {{ tokenized_key("assessment", "assessment_event_id") }} as assessment_key,
    {{ student_key("student_id") }} as student_key,
    {{ stable_key(["district_id"]) }} as district_key,
    {{ stable_key(["school_id"]) }} as school_key,
    {{ stable_key(["academic_year"]) }} as academic_year_key,
    {{ stable_key(["source_system"]) }} as source_system_key,
    to_char(assessment_date, 'YYYYMMDD')::integer as assessment_date_key,
    academic_year,
    assessment_name,
    subject,
    assessment_date,
    scale_score,
    performance_level,
    performance_level in ('meets_standard', 'exceeds_standard') as is_proficient,
    pipeline_run_id,
    source_file_id,
    source_row_number,
    source_system,
    source_schema_version,
    ingested_at,
    pipeline_started_at
from ranked
where version_rank = 1
