with school_versions as (
    select district_id, school_id, pipeline_run_id, source_file_id, source_row_number,
           source_system, pipeline_started_at
    from {{ ref("trusted_sis_student") }}
    union all
    select district_id, school_id, pipeline_run_id, source_file_id, source_row_number,
           source_system, pipeline_started_at
    from {{ ref("trusted_sis_enrollment") }}
    union all
    select district_id, school_id, pipeline_run_id, source_file_id, source_row_number,
           source_system, pipeline_started_at
    from {{ ref("trusted_attendance_event") }}
    union all
    select district_id, school_id, pipeline_run_id, source_file_id, source_row_number,
           source_system, pipeline_started_at
    from {{ ref("trusted_assessment_event") }}
),
ranked as (
    select
        *,
        row_number() over (
            partition by school_id
            order by pipeline_started_at desc, source_file_id desc, source_row_number desc
        ) as version_rank
    from school_versions
)
select
    {{ stable_key(["school_id"]) }} as school_key,
    {{ stable_key(["district_id"]) }} as district_key,
    school_id as source_school_id,
    pipeline_run_id,
    source_file_id,
    source_row_number,
    source_system,
    pipeline_started_at
from ranked
where version_rank = 1
