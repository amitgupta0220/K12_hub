with attendance_with_enrollment as (
    select
        academic_year.academic_year as school_year,
        attendance.district_key,
        attendance.school_key,
        enrollment.grade_level,
        attendance.student_key,
        attendance.daily_attendance_key,
        attendance.minutes_attended,
        attendance.possible_minutes,
        attendance.ingested_at
    from {{ ref("fact_daily_attendance") }} as attendance
    inner join {{ ref("fact_enrollment") }} as enrollment
        on enrollment.student_key = attendance.student_key
       and enrollment.school_key = attendance.school_key
       and attendance.instructional_date between enrollment.entry_date
           and coalesce(enrollment.exit_date, attendance.instructional_date)
    inner join {{ ref("dim_academic_year") }} as academic_year
        on academic_year.academic_year_key = enrollment.academic_year_key
)
select
    school_year,
    district_key,
    school_key,
    grade_level,
    count(distinct student_key) as enrolled_student_count,
    count(daily_attendance_key) as possible_attendance_days,
    {{ safe_divide("sum(minutes_attended)", "420") }} as attended_days,
    {{ safe_divide("sum(minutes_attended)", "sum(possible_minutes)") }} as attendance_rate,
    max(ingested_at) as source_data_updated_at,
    extract(epoch from (current_timestamp - max(ingested_at))) / 3600.0
        as data_freshness_hours,
    current_timestamp as mart_refreshed_at
from attendance_with_enrollment
group by school_year, district_key, school_key, grade_level
