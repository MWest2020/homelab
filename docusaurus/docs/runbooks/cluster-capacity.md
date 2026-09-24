---
title: Cluster capacity and probes
sidebar_position: 4
---

# Cluster capacity and probes

Measured 2026-09-24 (`kubectl get nodes`): three control-plane nodes
(`cp-01..03`, 4 CPU / 8 GiB, tainted `NoSchedule`) and three workers
(`node-01..03`, 4 CPU / 16 GiB). Workloads only land on the workers: about
12 cores and 48 GiB for the whole cluster, no GPU. Re-measure before sizing;
this page is a snapshot, the nodes are the truth.

## Scale out, not up

A CPU-bound inference service (OpenAnonymiser, Ollama) gains more from one
replica per worker with required anti-affinity than from a larger limit on one
pod. Roll such a Deployment with `maxSurge: 0, maxUnavailable: 1` when
replicas equal the number of workers — a surge pod is unschedulable.

## Probes on single-worker inference services

A single-worker inference service blocks its own `/health` during a forward
pass. With the Kubernetes default probe timeout of **1 s**, OpenAnonymiser
dropped out of the Service endpoints mid-run and the next call failed with
`No route to host` — about 80 documents were stranded before this was found.
Give such services a generous readiness timeout (10 s, failure threshold 6)
and liveness (10 s, threshold 12), or a TCP probe.

## The agent host is not a compute node

The host the Claude sessions run on is small (4 GiB RAM, 2 vCPU, no GPU).
Starting a torch/GLiNER model there once froze it and needed a reboot. Verify
such code statically and with unit tests there; run the inference smoke on a
worker.
