{% macro stable_key(expressions) -%}
    md5(
        concat_ws(
            '||'
            {%- for expression in expressions -%}
            , coalesce(cast({{ expression }} as text), '')
            {%- endfor -%}
        )
    )
{%- endmacro %}

{% macro tokenized_key(namespace, expression) -%}
    md5(
        '{{ env_var("K12HUB_HASH_SALT") | replace("'", "''") }}'
        || '|{{ namespace | replace("'", "''") }}|'
        || cast({{ expression }} as text)
    )
{%- endmacro %}

{% macro student_key(expression) -%}
    {{ tokenized_key("student", expression) }}
{%- endmacro %}
