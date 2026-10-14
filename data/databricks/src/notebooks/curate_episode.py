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

RELEASE_TAG = "v0.1"

CURATED_COLS = [
    "record_id",
    "payload",
    "split",
    "label",
    "origin",
    "_validated_at",
    "release_tag",
]


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
    validated = f"{catalog}.{schema}.validated_episode"
    curated = f"{catalog}.{schema}.curated_episode"
    spark.sql(
        f"CREATE TABLE IF NOT EXISTS {curated} ("  # validated identifiers
        "record_id STRING, payload STRING, split STRING, "  # validated identifiers
        "label STRING, origin STRING, _validated_at STRING, "  # validated identifiers
        "release_tag STRING)"  # validated identifiers
    )
    source_sql = (
        "SELECT record_id, payload, split, label, origin, _validated_at, "  # noqa: S608
        f"'{RELEASE_TAG}' AS release_tag "  # validated identifiers
        f"FROM {validated}"  # validated identifiers
    )
    sql = render_merge_sql(curated, source_sql, ["record_id"], CURATED_COLS)
    spark.sql(sql)


if __name__ == "__main__":
    main()
