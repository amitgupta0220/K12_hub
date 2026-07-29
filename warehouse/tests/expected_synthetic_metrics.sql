{% set expected = var("expected_metrics") %}

with attendance_by_student as (
    select
        student_key,
        sum(possible_minutes - minutes_attended)::numeric
            / nullif(sum(possible_minutes), 0) as absence_rate
    from {{ ref("fact_daily_attendance") }}
    group by student_key
),
actual as (
    select
        (select count(*) from {{ ref("dim_student") }})::numeric as student_count,
        (select count(*) from {{ ref("fact_enrollment") }})::numeric as enrollment_count,
        (select count(*) from {{ ref("fact_assessment") }})::numeric
            as assessment_event_count,
        (
            select sum(minutes_attended)::numeric / nullif(sum(possible_minutes), 0)
            from {{ ref("fact_daily_attendance") }}
        ) as attendance_rate,
        (
            select count(*) filter (where absence_rate >= 0.10)::numeric
                / nullif(count(*), 0)
            from attendance_by_student
        ) as chronic_absence_rate,
        (
            select count(*) filter (where is_proficient)::numeric / nullif(count(*), 0)
            from {{ ref("fact_assessment") }}
        ) as assessment_proficiency_rate,
        (
            select count(distinct instructional_date)
            from {{ ref("fact_daily_attendance") }}
        )::numeric as instructional_days,
        (
            select min(academic_year)
            from {{ ref("dim_academic_year") }}
        ) as school_year
),
comparisons as (
    select 'student_count' as metric_name, student_count as actual_value,
           {{ expected["student_count"] }}::numeric as expected_value
    from actual
    union all
    select 'enrollment_count', enrollment_count,
           {{ expected["enrollment_count"] }}::numeric
    from actual
    union all
    select 'assessment_event_count', assessment_event_count,
           {{ expected["assessment_event_count"] }}::numeric
    from actual
    union all
    select 'attendance_rate', attendance_rate,
           {{ expected["attendance_rate"] }}::numeric
    from actual
    union all
    select 'chronic_absence_rate', chronic_absence_rate,
           {{ expected["chronic_absence_rate"] }}::numeric
    from actual
    union all
    select 'assessment_proficiency_rate', assessment_proficiency_rate,
           {{ expected["assessment_proficiency_rate"] }}::numeric
    from actual
    union all
    select 'instructional_days', instructional_days,
           {{ expected["instructional_days"] }}::numeric
    from actual
),
numeric_failures as (
    select metric_name, actual_value::text, expected_value::text
    from comparisons
    where abs(actual_value - expected_value) > 0.000001
),
school_year_failure as (
    select 'school_year' as metric_name, school_year as actual_value,
           '{{ expected["school_year"] | replace("'", "''") }}' as expected_value
    from actual
    where school_year <> '{{ expected["school_year"] | replace("'", "''") }}'
)
select * from numeric_failures
union all
select * from school_year_failure
