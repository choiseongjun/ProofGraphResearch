# LocalStack + Kubernetes local deployment

This deployment uses two complementary local layers:

- **k3d** runs the actual Kubernetes Pods.
- **LocalStack Pro** emulates AWS APIs: EKS control-plane API, S3 artifact bucket, SQS, IAM, STS, CloudWatch and Logs.

LocalStack's EKS API emulation is not a replacement for a Kubernetes scheduler. k3d is therefore the execution cluster, while LocalStack provides the AWS integration surface that the same application can target in real EKS.

## Prerequisites

Docker Desktop, `kubectl`, and `k3d` must be installed. Ollama must be running on the host at port 11434.

## Deploy

Do not put the LocalStack token in Git, `.env.example`, or a Kubernetes manifest. Pass it only at runtime:

```powershell
$token = Read-Host "LocalStack auth token" -AsSecureString
.\scripts\deploy-localstack-k8s.ps1 -LocalStackAuthToken $token
```

The script starts LocalStack, creates a `proofgraph` k3d cluster if needed, builds/imports the application image, creates runtime-only Kubernetes secrets, and deploys all workloads.

Open the dashboard at `http://localhost:8000`. Inspect workloads with:

```powershell
kubectl -n proofgraph get pods,svc,pvc
docker logs proofgraph-localstack
```

Completed reports are uploaded to LocalStack S3 as `s3://proofgraph-reports/reports/<task-id>.md`. Verify them with:

```powershell
aws --endpoint-url http://localhost:4566 s3 ls s3://proofgraph-reports/reports/
```

## Cleanup

```powershell
kubectl delete namespace proofgraph
k3d cluster delete proofgraph
docker compose -f .\infra\localstack\docker-compose.localstack.yml down -v
```
