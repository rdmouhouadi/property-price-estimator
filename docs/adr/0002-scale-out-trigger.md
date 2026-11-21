# ADR-0002: Scale-out trigger (when to move from one laptop to a cloud cluster)

- **Status:** proposed (V2)
- **Date:** 2026-11-21

## Context

V1 runs on one laptop: about 20M source rows, processed within 5 GB of RAM in minutes ([ADR-0001](0001-data-processing-stack.md)). A cluster for V1 would contradict that ADR and add cost with no benefit.

## Decision

Move to a cloud cluster **when the data or job duration justifies it**. Not before. Triggers, any of:

- the source data grows beyond what bucketing keeps within one machine's RAM and disk, for example:
  - DVF+ history since 2014,
  - the pre-2021 DPE base (about 10M more records) to study label history,
  - the BDNB (national building database);
- a full rebuild takes longer than the retraining window allows (for example, it can't finish overnight);
- several people or jobs need the same data at the same time.

## Plan

1. **Practise locally first:** Spark on Kubernetes with minikube (already installed).
2. **Cloud target:** AWS EMR Serverless (managed Spark). It aligns with the AWS IaC work.
3. **Port, don't rewrite:**
   - the DVF × DPE join is SQL, so it moves to Spark SQL almost unchanged;
   - Parquet moves from local disk to S3 as is;
   - transformations live in small tested functions, so only that layer changes.
4. **Cost guardrails before the first run:** budget alerts, auto-termination, a small default cluster size.

## Consequences

- V1 stays simple and cheap. The scale-out path is documented and the code is already shaped for it.
- A V2 benchmark (laptop vs cluster on the same job) becomes a write-up in its own right.

## References

- Apache Spark on Kubernetes: https://spark.apache.org/docs/latest/running-on-kubernetes.html
- Amazon EMR Serverless: https://docs.aws.amazon.com/emr/latest/EMR-Serverless-UserGuide/emr-serverless.html
- [ADR-0001](0001-data-processing-stack.md), "no Spark in V1"
