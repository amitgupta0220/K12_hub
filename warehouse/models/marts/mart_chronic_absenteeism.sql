with student_attendance as (
    select
        academic_year.academic_year as school_year,
        attendance.district_key,
        attendance.school_key,
        enrollment.grade_level,
        attendance.student_key,
        {{ safe_divide(
            "sum(attendance.possible_minutes - attendance.minutes_attended)",
            "sum(attendance.possible_minutes)"
        ) }} as absence_rate,
        max(attendance.ingested_at) as source_data_updated_at
    from {{ ref("fact_daily_attendance") }} as attendance
    inner join {{ ref("fact_enrollment") }} as enrollment
        on enrollment.student_key = attendance.student_key
       and enrollment.school_key = attendance.school_key
       and attendance.instructional_date between enrollment.entry_date
           and coalesce(enrollment.exit_date, attendance.instructional_date)
    inner join {{ ref("dim_academic_year") }} as academic_year
        on academic_year.academic_year_key = enrollment.academic_year_key
    group by
        academic_year.academic_year,
        attendance.district_key,
        attendance.school_key,
        enrollment.grade_level,
        attendance.student_key
)
select
    school_year,
    district_key,
    school_key,
    grade_level,
    count(*) filter (where absence_rate is not null) as enrolled_student_count,
    count(*) filter (
        where absence_rate >= {{ var("chronic_absence_threshold") }}
    ) as chronically_absent_student_count,
    {{ safe_divide(
        "count(*) filter (where absence_rate >= "
            ~ var("chronic_absence_threshold") ~ ")",
        "count(*) filter (where absence_rate is not null)"
    ) }} as chronic_absenteeism_rate,
    {{ var("chronic_absence_threshold") }}::numeric as chronic_absence_threshold,
    max(source_data_updated_at) as source_data_updated_at,
    extract(epoch from (current_timestamp - max(source_data_updated_at))) / 3600.0
        as data_freshness_hours,
    current_timestamp as mart_refreshed_at
from student_attendance
group by school_year, district_key, school_key, grade_level
