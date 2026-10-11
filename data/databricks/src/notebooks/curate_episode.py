import argparse
import sys

from pyspark.sql import SparkSession

from pawl_core.sql import render_merge_sql

def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    return parser.parse_args(argv)

def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    spark = SparkSession.builder.getOrCreate()
    validated = f"{args.catalog}.{args.schema}.validated_episode"
    target = f"{args.catalog}.{args.schema}.curated_episode"
    spark.sql(f"CREATE TABLE IF NOT EXISTS {target} (record_id STRING, payload STRING)")
    source_sql = f"SELECT record_id, payload FROM {validated}"
    sql = render_merge_sql(target, source_sql, ["record_id"], ["record_id", "payload"])
    spark.sql(sql)

if __name__ == "__main__":
    main()
