with source_summary as (
    select
        source_file.pipeline_run_id,
        count(*) as source_file_count,
        max(source_file.loaded_at) filter (where source_file.status = 'loaded')
            as latest_source_loaded_at
    from audit.source_file as source_file
    group by source_file.pipeline_run_id
)
select
    pipeline.pipeline_run_id,
    pipeline.pipeline_name,
    pipeline.status as pipeline_status,
    case
        when coalesce(source.source_file_count, 0) = 0 then null
        else pipeline.records_loaded
    end as records_processed,
    case
        when coalesce(source.source_file_count, 0) = 0 then null
        else pipeline.records_rejected
    end as records_rejected,
    case when pipeline.status = 'completed' then 1.0 else 0.0 end
        as pipeline_success_rate,
    source.source_file_count,
    source.latest_source_loaded_at,
    extract(epoch from (current_timestamp - source.latest_source_loaded_at)) / 3600.0
        as source_freshness_hours,
    pipeline.started_at as pipeline_started_at,
    pipeline.finished_at as pipeline_finished_at,
    current_timestamp as mart_refreshed_at
from audit.pipeline_run as pipeline
left join source_summary as source
    on source.pipeline_run_id = pipeline.pipeline_run_id
