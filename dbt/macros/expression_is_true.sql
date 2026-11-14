{# 断言表达式为真，替代 dbt_utils.expression_is_true，零外部包依赖。
   列级测试时 dbt 会传入 column_name，这里显式吸收；
   支持测试 config 中的 where 过滤（经 get_where_subquery 生效）。 #}
{% test expression_is_true(model, expression, column_name=None, condition=None) %}
    select *
    from {{ get_where_subquery(model) }}
    where not ({{ expression }})
    {% if condition %}
        and {{ condition }}
    {% endif %}
{% endtest %}
