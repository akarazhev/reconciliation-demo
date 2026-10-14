{# True when two amounts use the same digits in another order: 129.00 and 192.00. #}
{% macro same_digits(a, b) -%}
(list_sort(string_split(replace(cast(abs({{ a }}) as varchar), '.', ''), ''))
 = list_sort(string_split(replace(cast(abs({{ b }}) as varchar), '.', ''), '')))
{%- endmacro %}
