with date_bounds as (
    select min(event_date) as minimum_date, max(event_date) as maximum_date
    from (
        select instructional_date as event_date from {{ ref("trusted_attendance_event") }}
        union all
        select assessment_date from {{ ref("trusted_assessment_event") }}
        union all
        select entry_date from {{ ref("trusted_sis_enrollment") }}
        union all
        select exit_date from {{ ref("trusted_sis_enrollment") }} where exit_date is not null
    ) as dates
),
date_spine as (
    select generate_series(minimum_date, maximum_date, interval '1 day')::date as calendar_date
    from date_bounds
)
select
    to_char(calendar_date, 'YYYYMMDD')::integer as date_key,
    calendar_date,
    extract(year from calendar_date)::integer as calendar_year,
    extract(quarter from calendar_date)::integer as calendar_quarter,
    extract(month from calendar_date)::integer as calendar_month,
    trim(to_char(calendar_date, 'Month')) as month_name,
    extract(day from calendar_date)::integer as day_of_month,
    extract(isodow from calendar_date)::integer as iso_day_of_week,
    trim(to_char(calendar_date, 'Day')) as day_name,
    extract(isodow from calendar_date) in (6, 7) as is_weekend
from date_spine
