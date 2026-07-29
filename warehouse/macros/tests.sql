{% test unique_combination_of_columns(model, combination_of_columns) %}
    select
        {%- for column in combination_of_columns %}
        {{ column }}{% if not loop.last %},{% endif %}
        {%- endfor %},
        count(*) as duplicate_count
    from {{ model }}
    group by
        {%- for column in combination_of_columns %}
        {{ column }}{% if not loop.last %},{% endif %}
        {%- endfor %}
    having count(*) > 1
{% endtest %}

{% test value_between(model, column_name, minimum, maximum) %}
    select *
    from {{ model }}
    where {{ column_name }} is not null
      and (
          {{ column_name }} < {{ minimum }}
          or {{ column_name }} > {{ maximum }}
      )
{% endtest %}
