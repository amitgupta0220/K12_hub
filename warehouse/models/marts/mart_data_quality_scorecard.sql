with ranked_quality_runs as (
    select
        quality_run.*,
        row_number() over (
            partition by quality_run.pipeline_run_id
            order by quality_run.started_at desc, quality_run.data_quality_rule_run_id desc
        ) as quality_rank
    from audit.data_quality_rule_run as quality_run
),
latest_quality_runs as (
    select *
    from ranked_quality_runs
    where quality_rank = 1
),
rule_summary as (
    select
        result.data_quality_rule_run_id,
        count(*) filter (where result.status = 'passed') as passed_rule_count,
        sum(result.failure_count) filter (where result.severity = 'warning') as warning_count
    from audit.data_quality_rule_result as result
    group by result.data_quality_rule_run_id
)
select
    pipeline.pipeline_run_id,
    quality.data_quality_rule_run_id,
    pipeline.pipeline_name,
    pipeline.status as pipeline_status,
    quality.status as quality_status,
    quality.blocking_failure_count as blocking_error_count,
    coalesce(summary.warning_count, 0) as warning_count,
    {{ safe_divide("summary.passed_rule_count", "quality.enabled_rule_count") }}
        as data_quality_pass_rate,
    quality.enabled_rule_count,
    quality.failure_count,
    quality.started_at as quality_started_at,
    quality.finished_at as quality_finished_at,
    extract(epoch from (current_timestamp - quality.finished_at)) / 3600.0
        as data_freshness_hours,
    current_timestamp as mart_refreshed_at
from latest_quality_runs as quality
inner join audit.pipeline_run as pipeline
    on pipeline.pipeline_run_id = quality.pipeline_run_id
left join rule_summary as summary
    on summary.data_quality_rule_run_id = quality.data_quality_rule_run_id
