select
    academic_year.academic_year as school_year,
    enrollment.district_key,
    enrollment.school_key,
    enrollment.grade_level,
    count(distinct enrollment.student_key) as enrolled_student_count,
    min(enrollment.entry_date) as first_entry_date,
    max(enrollment.exit_date) as latest_exit_date,
    max(enrollment.ingested_at) as source_data_updated_at,
    extract(epoch from (current_timestamp - max(enrollment.ingested_at))) / 3600.0
        as data_freshness_hours,
    current_timestamp as mart_refreshed_at
from {{ ref("fact_enrollment") }} as enrollment
inner join {{ ref("dim_academic_year") }} as academic_year
    on academic_year.academic_year_key = enrollment.academic_year_key
group by
    academic_year.academic_year,
    enrollment.district_key,
    enrollment.school_key,
    enrollment.grade_level
