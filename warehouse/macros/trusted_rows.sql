{% macro trusted_rows(source_table) %}
    select
        staged.*,
        source_file.source_system,
        pipeline_run.started_at as pipeline_started_at
    from {{ source("staging", source_table) }} as staged
    inner join audit.source_file as source_file
        on source_file.source_file_id = staged.source_file_id
    inner join audit.pipeline_run as pipeline_run
        on pipeline_run.pipeline_run_id = staged.pipeline_run_id
    inner join lateral (
        select quality_run.status
        from audit.data_quality_rule_run as quality_run
        where quality_run.pipeline_run_id = staged.pipeline_run_id
        order by quality_run.started_at desc, quality_run.data_quality_rule_run_id desc
        limit 1
    ) as latest_quality
        on latest_quality.status = 'passed'
    where not exists (
        select 1
        from quarantine.rejected_record as rejected
        inner join metadata.data_quality_rule as quality_rule
            on quality_rule.rule_id = rejected.rule_id
        where rejected.source_file_id = staged.source_file_id
          and rejected.source_row_number = staged.source_row_number
          and quality_rule.blocking
    )
{% endmacro %}
