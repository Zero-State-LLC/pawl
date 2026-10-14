import argparse
import sys
from pathlib import Path

here = globals().get("__file__") or sys.argv[0]
_notebooks = Path(here).resolve().parent
_src = _notebooks.parent
sys.path.insert(0, str(_src))
sys.path.insert(0, str(_notebooks))

from pawl_core.sql import quote_ident, render_merge_sql  # noqa: E402
from pyspark.sql import SparkSession  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--source", required=True)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    spark = SparkSession.builder.getOrCreate()
    catalog = quote_ident(args.catalog)
    schema = quote_ident(args.schema)
    target = f"{catalog}.{schema}.raw_episode"
    spark.sql(
        f"CREATE TABLE IF NOT EXISTS {target} ("  # validated identifiers
        "record_id STRING, payload STRING, "  # validated identifiers
        "_source_file STRING, _ingested_at TIMESTAMP)"  # validated identifiers
    )
    df = spark.read.text(args.source)
    df = df.select(
        F.get_json_object(F.col("value"), "$.record_id").alias("record_id"),
        F.col("value").alias("payload"),
        F.col("_metadata.file_path").alias("_source_file"),
        F.current_timestamp().alias("_ingested_at"),
    )
    df.createOrReplaceTempView("raw_source")
    source_sql = "SELECT record_id, payload, _source_file, _ingested_at FROM raw_source"
    sql = render_merge_sql(
        target,
        source_sql,
        ["record_id"],
        ["record_id", "payload", "_source_file", "_ingested_at"],
    )
    spark.sql(sql)


if __name__ == "__main__":
    main()
