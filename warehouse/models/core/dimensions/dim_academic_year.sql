with academic_years as (
    select academic_year from {{ ref("trusted_sis_enrollment") }}
    union
    select academic_year from {{ ref("trusted_assessment_event") }}
)
select
    {{ stable_key(["academic_year"]) }} as academic_year_key,
    academic_year,
    substring(academic_year from 1 for 4)::integer as start_year,
    substring(academic_year from 6 for 4)::integer as end_year,
    make_date(substring(academic_year from 1 for 4)::integer, 7, 1) as start_date,
    make_date(substring(academic_year from 6 for 4)::integer, 6, 30) as end_date
from academic_years
