--  Imagine you have 50 tables that have an email column. 
-- In SQL, to clean an email, you have to write LOWER(TRIM(email)) 50 times.

{% macro clean_email(email_column) %}
    LOWER(TRIM({{ email_column }}))
{% endmacro %}

