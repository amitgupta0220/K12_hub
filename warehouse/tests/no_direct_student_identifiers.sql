select table_name, column_name
from information_schema.columns
where table_schema = 'core'
  and table_name in (
      'dim_student',
      'fact_enrollment',
      'fact_daily_attendance',
      'fact_assessment'
  )
  and column_name in (
      'student_id',
      'local_student_number',
      'first_name',
      'last_name',
      'enrollment_id',
      'assessment_event_id'
  )
