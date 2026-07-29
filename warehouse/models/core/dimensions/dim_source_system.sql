with trusted_source_systems as (
    select source_system from {{ ref("trusted_sis_student") }}
    union
    select source_system from {{ ref("trusted_sis_enrollment") }}
    union
    select source_system from {{ ref("trusted_attendance_event") }}
    union
    select source_system from {{ ref("trusted_assessment_event") }}
)
select
    {{ stable_key(["trusted.source_system"]) }} as source_system_key,
    trusted.source_system as source_system_code,
    metadata.name as source_system_name,
    metadata.description,
    metadata.data_category,
    metadata.is_active
from trusted_source_systems as trusted
inner join metadata.source_system as metadata
    on metadata.source_system_code = trusted.source_system
