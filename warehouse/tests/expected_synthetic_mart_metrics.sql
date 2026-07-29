{% set expected = var("expected_metrics") %}
{% set tolerance = 0.000001 %}

with actual as (
    select
        (select sum(enrolled_student_count) from {{ ref("mart_enrollment_trends") }})::numeric
            as enrolled_student_count,
        (
            select {{ safe_divide("sum(attended_days)", "sum(possible_attendance_days)") }}
            from {{ ref("mart_attendance_summary") }}
        ) as attendance_rate,
        (
            select {{ safe_divide(
                "sum(chronically_absent_student_count)",
                "sum(enrolled_student_count)"
            ) }}
            from {{ ref("mart_chronic_absenteeism") }}
        ) as chronic_absenteeism_rate,
        (
            select count(distinct attendance.instructional_date)
            from {{ ref("fact_daily_attendance") }} as attendance
        )::numeric as instructional_days
),
comparisons as (
    select
        'enrolled_student_count' as metric_name,
        enrolled_student_count as actual_value,
        {{ expected["student_count"] }}::numeric as expected_value,
        0::numeric as allowed_tolerance
    from actual
    union all
    select
        'attendance_rate',
        attendance_rate,
        {{ expected["attendance_rate"] }}::numeric,
        {{ tolerance }}::numeric
    from actual
    union all
    select
        'chronic_absenteeism_rate',
        chronic_absenteeism_rate,
        {{ expected["chronic_absence_rate"] }}::numeric,
        {{ tolerance }}::numeric
    from actual
    union all
    select
        'instructional_days',
        instructional_days,
        {{ expected["instructional_days"] }}::numeric,
        0::numeric
    from actual
)
select *
from comparisons
where actual_value is null
   or abs(actual_value - expected_value) > allowed_tolerance
