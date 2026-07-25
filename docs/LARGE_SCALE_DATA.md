# 대용량 수집·색인 설계

## 현재 구현

| 계층 | 처리 방식 |
|---|---|
| 수집 요청 | API가 `ingestion_job`을 생성하고 즉시 `202 Accepted`를 반환합니다. |
| 작업 분리 | 일반 리서치 Worker와 분리된 `ingestion` Celery Queue를 사용합니다. |
| 병렬 처리 | 전용 ingestion worker는 기본 동시성 4로 실행됩니다. |
| 백프레셔 | 임베딩은 `EMBEDDING_BATCH_SIZE`(기본 32) 단위로 처리합니다. |
| 원문 데이터 레이크 | LocalStack S3의 `proofgraph-raw` 버킷에 원문과 매니페스트를 보관합니다. |
| 메타데이터·검색 | PostgreSQL에는 청크, 출처, `artifact_uri`만 저장하고 pgvector HNSW 인덱스로 검색합니다. |
| 추적성 | RAG 검색 결과의 `metadata.artifact_uri`로 S3 원문 객체를 역추적할 수 있습니다. |

## LocalStack S3 활성화

1. LocalStack을 실행합니다. 토큰은 파일에 저장하지 않고 PowerShell 세션에서만 전달합니다.

```powershell
.\scripts\start-localstack.ps1
```

2. `.env`에 아래 값을 추가합니다.

```dotenv
RAW_DOCUMENT_STORAGE_ENABLED=true
AWS_ENDPOINT_URL=http://host.docker.internal:4566
```

3. API와 Worker를 다시 올립니다.

```powershell
docker compose up -d --build api worker ingestion-worker
```

이후 UI의 **자동 RAG 수집**과 **대량 수집 작업**은 원문을 S3에 보관한 뒤 벡터 색인을 수행합니다. 객체 저장소 장애가 있어도 색인 작업 자체는 중단하지 않으며, 해당 문서의 `artifact_uri`만 비어 있게 됩니다.

## 전용 벡터 검색: Qdrant

로컬 Compose는 Qdrant를 기본 기동하며 `.env.qdrant`의 비밀 없는 설정으로 검색 트래픽을 분리합니다. PostgreSQL pgvector는 감사·백업·마이그레이션을 위한 보조 인덱스로 유지됩니다.

```powershell
docker compose up -d qdrant
```

```dotenv
VECTOR_BACKEND=qdrant
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION=proofgraph_knowledge
```

API와 Worker를 재시작한 뒤 새로 수집한 청크부터 Qdrant에 색인됩니다. PostgreSQL은 청크·버전·작업 상태의 감사 원장으로 계속 유지됩니다. Kubernetes 매니페스트는 Qdrant StatefulSet을 기본 포함합니다.

기존 pgvector 청크는 재수집할 필요 없이 아래 API로 Qdrant에 백필합니다.

```powershell
Invoke-RestMethod http://localhost:8000/v1/knowledge/vector-sync -Method Post
```

## KEDA 자동 확장

`k8s/keda`에는 Redis Celery 큐 길이를 기준으로 Worker를 확장하는 `ScaledObject`가 있습니다.

```powershell
# 클러스터에 KEDA Operator가 설치된 뒤 적용
kubectl apply -k .\k8s\keda
```

| 대상 | 최소~최대 | 확장 기준 |
|---|---:|---|
| `ingestion-worker` | 0~8 | `ingestion` 큐에 작업 1개 이상, 5개 단위로 확장 |
| `worker` | 1~5 | 기본 `celery` 큐에 작업 1개 이상, 3개 단위로 확장 |

## 수집 거버넌스

- `robots.txt`를 확인하고 금지된 경로는 수집하지 않습니다.
- 같은 도메인에는 기본 1초 간격을 둡니다.
- URL fragment와 `utm_*` 등 추적 파라미터를 제거해 중복 URL을 막습니다.
- URL별 콘텐츠 SHA-256, ETag, Last-Modified, 수집 시각, 버전을 PostgreSQL에 저장합니다.
- 내용이 바뀌지 않은 URL은 재임베딩하지 않고, 바뀐 문서는 다음 버전으로 색인합니다.
