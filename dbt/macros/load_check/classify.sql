{% macro load_is_blank(expr) -%}
    regexp_full_match({{ expr }}, '\s+')
{%- endmacro %}

{% macro load_value_cause(rows, cfg, column, kind, codes) %}
    {#- The first matching cause of spec §5.2 for one column of an entity; an empty setting turns its rule off. -#}
    {%- set parent = load_entity(rows, cfg['parent_entity']) if cfg['parent_entity'] else none -%}
    {%- set modified = ('s.' ~ cfg['modified_column']) if cfg['modified_column']
                       else ('s._parent_modified' if parent and parent['modified_column'] else none) -%}
    case
        {%- if column in load_list(cfg['measures']) and cfg['money_scale_target'] %}
        when t.{{ column }} = trunc(s.{{ column }}, {{ cfg['money_scale_target'] }}) and t.{{ column }} <> s.{{ column }}
            then 'truncated_decimal'
        {%- endif %}
        {%- if kind == 'time' %}
        when datediff('second', s.{{ column }}, t.{{ column }}) % 3600 = 0
         and abs(datediff('second', s.{{ column }}, t.{{ column }})) between 3600 and 14 * 3600
            then 'timezone_shift'
        {%- endif %}
        {%- if kind == 'text' %}
        when {{ load_is_blank('s.' ~ column) }} and t.{{ column }} is null
            then 'whitespace_to_null'
        {%- endif %}
        when t.{{ column }} is null and s.{{ column }}::varchar in (
            select value from {{ codes }}
            where dataset = '{{ var("dataset") }}' and entity = '{{ cfg["entity"] }}' and column_name = '{{ column }}')
            then 'schema_drift'
        {%- if column == cfg['ref_column'] and cfg['ref_number_column'] and cfg['ref_entity'] %}
        {%- set referenced = load_entity(rows, cfg['ref_entity']) %}
        when s.{{ cfg['ref_number_column'] }} = t.{{ cfg['ref_number_column'] }}
         and exists (
            select 1 from {{ load_relation(referenced['entity'], 'target') }} as ref
            where ref.{{ referenced['key'] }} = t.{{ column }}
              and ref.{{ cfg['ref_number_column'] }} = s.{{ cfg['ref_number_column'] }})
            then 'payment_wrong_invoice'
        {%- endif %}
        {%- if cfg['export_column'] and modified %}
        when {{ modified }} > t.{{ cfg['export_column'] }}
            then 'changed_not_exported'
        {%- endif %}
        {%- if column == cfg['code_column'] and cfg['history_relation'] %}
        when exists (
            select 1 from {{ ref(cfg['history_relation']) }} as h
            where h.old_value = t.{{ column }} and h.new_value = s.{{ column }})
            then 'late_item_not_updated'
        {%- endif %}
        else 'value_mismatch'
    end
{% endmacro %}

{% macro load_explanation(cause) -%}
    case {{ cause }}
        when 'batch_boundary_loss' then 'Skipped at a batch boundary: the next batch started after this row''s time.'
        when 'deleted_left_behind' then 'Deleted in the source after the export; still in the target.'
        when 'duplicate_after_rerun' then 'Loaded twice: a re-run of the export wrote it again.'
        when 'missing_in_target' then 'In the source, not in the target.'
        when 'extra_in_target' then 'In the target, not in the source.'
        when 'duplicate_in_target' then 'In the target more than once.'
        when 'truncated_decimal' then 'Amount cut to the target''s decimals.'
        when 'timezone_shift' then 'Time moved by whole hours: local time loaded as UTC.'
        when 'whitespace_to_null' then 'A value of spaces became NULL.'
        when 'schema_drift' then 'Code missing from the migration map; the target has NULL.'
        when 'payment_wrong_invoice' then 'Linked to an older invoice with the same number.'
        when 'changed_not_exported' then 'Changed in the source after it was exported.'
        when 'late_item_not_updated' then 'Item code renamed in the source; the target kept the old code.'
        when 'value_mismatch' then 'Values differ; no other cause found.'
    end
{%- endmacro %}
