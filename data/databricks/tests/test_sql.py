from pawl_core.sql import render_merge_sql

def test_merge_sql_contains_idempotent_merge():
    sql = render_merge_sql(
        "main.pawl_dev.validated_episode",
        "SELECT record_id, payload FROM raw_source",
        ["record_id"],
        ["record_id", "payload"],
    )
    assert "MERGE INTO main.pawl_dev.validated_episode AS t" in sql
    assert "ON t.record_id = s.record_id" in sql
    assert "WHEN MATCHED THEN UPDATE SET payload = s.payload" in sql
    assert "WHEN NOT MATCHED THEN INSERT (record_id, payload) VALUES (s.record_id, s.payload)" in sql
