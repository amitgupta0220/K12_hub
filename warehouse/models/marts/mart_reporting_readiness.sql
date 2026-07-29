with assessment_summary as (
    select
        pipeline_run_id,
        count(*) as assessment_event_count,
        {{ safe_divide(
            "count(*) filter (where is_proficient)",
            "count(*)"
        ) }} as assessment_proficiency_rate,
        max(ingested_at) as assessment_data_updated_at
    from {{ ref("fact_assessment") }}
    group by pipeline_run_id
)
select
    pipeline.pipeline_run_id,
    pipeline.pipeline_name,
    pipeline.pipeline_status,
    quality.quality_status,
    pipeline.records_processed,
    pipeline.records_rejected,
    quality.blocking_error_count,
    quality.warning_count,
    quality.data_quality_pass_rate,
    pipeline.pipeline_success_rate,
    pipeline.source_freshness_hours,
    assessment.assessment_event_count,
    assessment.assessment_proficiency_rate,
    case
        when quality.data_quality_pass_rate is null
          or pipeline.source_freshness_hours is null then null
        else round(
            100.0 * (
                0.4 * pipeline.pipeline_success_rate
                + 0.4 * quality.data_quality_pass_rate
                + 0.2 * case
                    when pipeline.source_freshness_hours
                        <= {{ var("source_freshness_sla_hours") }}
                    then 1.0
                    else 0.0
                end
            ),
            2
        )
    end as reporting_readiness_score,
    {{ var("source_freshness_sla_hours") }}::numeric as freshness_sla_hours,
    greatest(
        pipeline.latest_source_loaded_at,
        quality.quality_finished_at,
        assessment.assessment_data_updated_at
    ) as source_data_updated_at,
    current_timestamp as mart_refreshed_at
from {{ ref("mart_pipeline_health") }} as pipeline
left join {{ ref("mart_data_quality_scorecard") }} as quality
    on quality.pipeline_run_id = pipeline.pipeline_run_id
left join assessment_summary as assessment
    on assessment.pipeline_run_id = pipeline.pipeline_run_id
