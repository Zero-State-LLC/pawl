import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

here = globals().get("__file__") or sys.argv[0]
_notebooks = Path(here).resolve().parent
_src = _notebooks.parent
sys.path.insert(0, str(_src))
sys.path.insert(0, str(_notebooks))

from pawl_core.dq import dq_check  # noqa: E402
from pawl_core.split import split_for_record  # noqa: E402
from pawl_core.sql import quote_ident, render_merge_sql  # noqa: E402
from pyspark.sql import SparkSession  # noqa: E402
from pyspark.sql.types import (  # noqa: E402
    StringType,
    StructField,
    StructType,
)

MAX_ROWS = 10000

VALIDATED_SCHEMA = StructType(
    [
        StructField("record_id", StringType(), True),
        StructField("payload", StringType(), True),
        StructField("split", StringType(), True),
        StructField("label", StringType(), True),
        StructField("origin", StringType(), True),
        StructField("_validated_at", StringType(), True),
    ]
)

QUARANTINE_SCHEMA = StructType(
    [
        StructField("record_id", StringType(), True),
        StructField("reasons", StringType(), True),
        StructField("payload", StringType(), True),
        StructField("_quarantined_at", StringType(), True),
    ]
)

VALIDATED_COLS = ["record_id", "payload", "split", "label", "origin", "_validated_at"]
QUARANTINE_COLS = ["record_id", "reasons", "payload", "_quarantined_at"]


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    spark = SparkSession.builder.getOrCreate()
    catalog = quote_ident(args.catalog)
    schema = quote_ident(args.schema)
    raw = f"{catalog}.{schema}.raw_episode"
    validated = f"{catalog}.{schema}.validated_episode"
    quarantine = f"{catalog}.{schema}.quarantine_episode"

    spark.sql(
        f"CREATE TABLE IF NOT EXISTS {validated} ("  # validated identifiers
        "record_id STRING, payload STRING, split STRING, "  # validated identifiers
        "label STRING, origin STRING, _validated_at STRING)"  # validated identifiers
    )
    spark.sql(
        f"CREATE TABLE IF NOT EXISTS {quarantine} ("  # validated identifiers
        "record_id STRING, reasons STRING, payload STRING, "  # validated identifiers
        "_quarantined_at STRING)"  # validated identifiers
    )

    rows = spark.sql(
        f"SELECT record_id, payload FROM {raw} LIMIT {MAX_ROWS + 1}"  # noqa: S608
    ).collect()
    assert len(rows) <= MAX_ROWS, f"raw_episode exceeds {MAX_ROWS} rows"

    now = datetime.now(UTC).isoformat()
    valid_rows = []
    quarantine_rows = []
    for row in rows:
        rid = row["record_id"]
        payload = row["payload"]
        record = None
        try:
            parsed = json.loads(payload)
            if isinstance(parsed, dict):
                record = parsed
        except (TypeError, ValueError):
            record = None
        if record is None:
            quarantine_rows.append((rid, json.dumps(["DQ_BAD_JSON"]), payload, now))
            continue
        codes = dq_check(record)
        if codes:
            quarantine_rows.append((rid, json.dumps(codes), payload, now))
            continue
        split = split_for_record(record)
        valid_rows.append((rid, payload, split, record.get("label"), record.get("origin"), now))

    if valid_rows:
        df = spark.createDataFrame(valid_rows, schema=VALIDATED_SCHEMA)
        df.createOrReplaceTempView("validated_source")
        source_sql = (
            "SELECT record_id, payload, split, label, origin, _validated_at FROM validated_source"
        )
        sql = render_merge_sql(validated, source_sql, ["record_id"], VALIDATED_COLS)
        spark.sql(sql)

    if quarantine_rows:
        df = spark.createDataFrame(quarantine_rows, schema=QUARANTINE_SCHEMA)
        df.createOrReplaceTempView("quarantine_source")
        source_sql = "SELECT record_id, reasons, payload, _quarantined_at FROM quarantine_source"
        sql = render_merge_sql(quarantine, source_sql, ["record_id"], QUARANTINE_COLS)
        spark.sql(sql)


if __name__ == "__main__":
    main()
