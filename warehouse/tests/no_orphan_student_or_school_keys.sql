with orphan_keys as (
    select 'fact_enrollment.student_key' as failure
    from {{ ref("fact_enrollment") }} as fact
    left join {{ ref("dim_student") }} as dimension using (student_key)
    where dimension.student_key is null

    union all

    select 'fact_enrollment.school_key'
    from {{ ref("fact_enrollment") }} as fact
    left join {{ ref("dim_school") }} as dimension using (school_key)
    where dimension.school_key is null

    union all

    select 'fact_daily_attendance.student_key'
    from {{ ref("fact_daily_attendance") }} as fact
    left join {{ ref("dim_student") }} as dimension using (student_key)
    where dimension.student_key is null

    union all

    select 'fact_daily_attendance.school_key'
    from {{ ref("fact_daily_attendance") }} as fact
    left join {{ ref("dim_school") }} as dimension using (school_key)
    where dimension.school_key is null

    union all

    select 'fact_assessment.student_key'
    from {{ ref("fact_assessment") }} as fact
    left join {{ ref("dim_student") }} as dimension using (student_key)
    where dimension.student_key is null

    union all

    select 'fact_assessment.school_key'
    from {{ ref("fact_assessment") }} as fact
    left join {{ ref("dim_school") }} as dimension using (school_key)
    where dimension.school_key is null
)
select *
from orphan_keys
