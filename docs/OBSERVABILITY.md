# 관측성: Prometheus + Grafana

## 수집 지표

- API 요청 수, 경로별 p95 응답 시간, HTTP 오류율
- 리서치·대량 수집 작업 상태
- Redis의 `celery`, `ingestion` 큐 적체
- 누적 RAG 청크 수와 Redis 메모리 사용량

## Docker Compose

```powershell
docker compose up -d --build prometheus redis-exporter grafana api
```

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001 (`admin` / `admin` — 로컬 데모 전용)
- API raw metrics: http://localhost:8000/metrics

## Kubernetes

```powershell
kubectl apply -k .\k8s\observability
kubectl -n proofgraph port-forward svc/grafana 3001:3000
```

Grafana는 http://localhost:3001 에서 확인합니다. Kubernetes 개발 환경의 기본 계정도 `admin` / `admin`이며, 실제 배포에서는 Secret 또는 SSO로 반드시 교체해야 합니다.
