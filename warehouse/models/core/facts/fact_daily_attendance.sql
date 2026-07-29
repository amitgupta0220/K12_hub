{{
    config(
        materialized="incremental",
        unique_key="daily_attendance_key",
        incremental_strategy="merge",
        on_schema_change="fail"
    )
}}

with ranked as (
    select
        *,
        row_number() over (
            partition by student_id, school_id, instructional_date
            order by pipeline_started_at desc, recorded_at desc,
                     source_file_id desc, source_row_number desc
        ) as version_rank
    from {{ ref("trusted_attendance_event") }}
)
select
    {{ tokenized_key(
        "attendance",
        "student_id || '|' || school_id || '|' || instructional_date::text"
    ) }} as daily_attendance_key,
    {{ student_key("student_id") }} as student_key,
    {{ stable_key(["district_id"]) }} as district_key,
    {{ stable_key(["school_id"]) }} as school_key,
    {{ stable_key(["source_system"]) }} as source_system_key,
    to_char(instructional_date, 'YYYYMMDD')::integer as attendance_date_key,
    instructional_date,
    attendance_status,
    minutes_attended,
    420 as possible_minutes,
    reason_code,
    recorded_at,
    pipeline_run_id,
    source_file_id,
    source_row_number,
    source_system,
    source_schema_version,
    ingested_at,
    pipeline_started_at
from ranked
where version_rank = 1
