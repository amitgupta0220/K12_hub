with ranked as (
    select
        *,
        row_number() over (
            partition by student_id
            order by pipeline_started_at desc, source_file_id desc, source_row_number desc
        ) as version_rank
    from {{ ref("trusted_sis_student") }}
)
select
    {{ student_key("student_id") }} as student_key,
    {{ stable_key(["district_id"]) }} as district_key,
    {{ stable_key(["school_id"]) }} as school_key,
    extract(year from birth_date)::integer as birth_year,
    gender,
    grade_level,
    active as is_active,
    pipeline_run_id,
    source_file_id,
    source_row_number,
    source_system,
    source_schema_version,
    ingested_at,
    pipeline_started_at
from ranked
where version_rank = 1
