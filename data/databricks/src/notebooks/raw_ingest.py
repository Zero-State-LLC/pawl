import argparse
import sys

from pyspark.sql import SparkSession

from pawl_core.sql import render_merge_sql

def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--source", default="")
    return parser.parse_args(argv)

def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    spark = SparkSession.builder.getOrCreate()
    target = f"{args.catalog}.{args.schema}.raw_episode"
    spark.sql(f"CREATE TABLE IF NOT EXISTS {target} (record_id STRING, payload STRING)")
    if args.source:
        spark.read.json(args.source).createOrReplaceTempView("raw_source")
        source_sql = "SELECT record_id, to_json(struct(*)) AS payload FROM raw_source"
        sql = render_merge_sql(target, source_sql, ["record_id"], ["record_id", "payload"])
        spark.sql(sql)

if __name__ == "__main__":
    main()
