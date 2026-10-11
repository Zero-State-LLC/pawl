import re

IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def quote_ident(name: str) -> str:
    if len(name) > 2 and name[0] == name[-1] == "`":
        name = name[1:-1]
    if not IDENT_RE.fullmatch(name):
        raise ValueError(f"invalid identifier: {name!r}")
    return f"`{name}`"


def quote_qualified_name(name: str) -> str:
    return ".".join(quote_ident(part) for part in name.split("."))


def render_merge_sql(target_table: str, source_sql: str, key_columns: list, columns: list) -> str:
    target = quote_qualified_name(target_table)
    on_clause = " AND ".join(
        f"t.{quote_ident(k)} = s.{quote_ident(k)}"  # validated identifiers
        for k in key_columns
    )
    update_cols = [c for c in columns if c not in key_columns]
    parts = [
        f"MERGE INTO {target} AS t "  # validated identifiers
        f"USING ({source_sql}) AS s ON {on_clause}"  # validated identifiers
    ]
    if update_cols:
        sets = ", ".join(
            f"{quote_ident(c)} = s.{quote_ident(c)}"  # validated identifiers
            for c in update_cols
        )
        parts.append(
            f"WHEN MATCHED THEN UPDATE SET {sets}"  # validated identifiers
        )
    insert_cols = ", ".join(quote_ident(c) for c in columns)
    insert_vals = ", ".join(
        f"s.{quote_ident(c)}"  # validated identifiers
        for c in columns
    )
    parts.append(
        f"WHEN NOT MATCHED THEN INSERT ({insert_cols}) "  # noqa: S608  # validated identifiers
        f"VALUES ({insert_vals})"  # validated identifiers
    )
    return " ".join(parts)
