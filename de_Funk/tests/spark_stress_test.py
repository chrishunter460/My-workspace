#!/usr/bin/env python3
"""
Spark Cluster Stress Test

Generates CPU and memory load across all workers to verify monitoring.

Usage:
    spark-submit --master spark://192.168.1.212:7077 spark_stress_test.py
"""
from pyspark.sql import SparkSession
import time

def stress_test():
    spark = SparkSession.builder \
        .appName("ClusterStressTest") \
        .getOrCreate()

    sc = spark.sparkContext

    print("=" * 60)
    print("  Spark Cluster Stress Test")
    print("=" * 60)
    print(f"  Master: {sc.master}")
    print(f"  App ID: {sc.applicationId}")
    print()

    # Create a large RDD and force computation across workers
    num_partitions = 30  # Spread across workers
    num_elements = 10_000_000

    print(f"Creating RDD with {num_elements:,} elements across {num_partitions} partitions...")

    # CPU-intensive: compute-heavy operations
    rdd = sc.parallelize(range(num_elements), num_partitions)

    # Run multiple iterations to generate sustained load
    for i in range(5):
        print(f"\nIteration {i+1}/5 - Running compute tasks...")
        start = time.time()

        # Force computation with aggregation
        result = rdd.map(lambda x: x * x) \
                    .map(lambda x: x ** 0.5) \
                    .map(lambda x: sum(range(int(x % 100)))) \
                    .reduce(lambda a, b: a + b)

        elapsed = time.time() - start
        print(f"  Completed in {elapsed:.2f}s, result checksum: {result}")

        # Brief pause between iterations
        time.sleep(2)

    print("\n" + "=" * 60)
    print("  Stress test complete!")
    print("  Check the monitoring dashboard for utilization graphs.")
    print("=" * 60)

    spark.stop()

if __name__ == "__main__":
    stress_test()
