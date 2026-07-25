#!/bin/sh
set -eu

awslocal s3api create-bucket --bucket proofgraph-reports --region ap-northeast-2 --create-bucket-configuration LocationConstraint=ap-northeast-2 2>/dev/null || true
awslocal s3api create-bucket --bucket proofgraph-raw --region ap-northeast-2 --create-bucket-configuration LocationConstraint=ap-northeast-2 2>/dev/null || true
awslocal sqs create-queue --queue-name proofgraph-research-events >/dev/null
