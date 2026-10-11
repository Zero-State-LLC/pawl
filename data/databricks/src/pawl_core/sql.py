def render_merge_sql(target_table: str, source_sql: str, key_columns: list, columns: list) -> str:
    on_clause = " AND ".join(f"t.{k} = s.{k}" for k in key_columns)
    update_cols = [c for c in columns if c not in key_columns]
    parts = [f"MERGE INTO {target_table} AS t USING ({source_sql}) AS s ON {on_clause}"]
    if update_cols:
        sets = ", ".join(f"{c} = s.{c}" for c in update_cols)
        parts.append(f"WHEN MATCHED THEN UPDATE SET {sets}")
    insert_cols = ", ".join(columns)
    insert_vals = ", ".join(f"s.{c}" for c in columns)
    parts.append(f"WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals})")
    return " ".join(parts)
