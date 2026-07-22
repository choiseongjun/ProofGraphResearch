# Deep Research Agent 실행 가이드

## 1. 사전 준비

- Docker Desktop 실행
- OpenAI API Key
- 선택 사항: Tavily API Key (웹 검색 품질 향상)

## 2. 환경변수 파일 만들기

프로젝트 최상위 폴더에서 아래 명령을 실행합니다.

```powershell
Copy-Item .env.example .env
```

생성된 `.env` 파일을 열어 값을 설정합니다.

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini
TAVILY_API_KEY=tvly-...
REDIS_URL=redis://redis:6379/0
DATABASE_URL=postgresql+psycopg://research:research@postgres:5432/research
MAX_REVISIONS=2
APP_API_KEY=
```

`TAVILY_API_KEY`가 없어도 DuckDuckGo 검색 폴백을 시도합니다. `OPENAI_API_KEY`가 없으면 워크플로우 연결 확인용 폴백 보고서만 생성됩니다.

## 3. 서비스 시작

```powershell
docker compose up --build
```

정상적으로 시작되면 아래 서비스가 실행됩니다.

| 서비스 | 역할 | 주소 |
|---|---|---|
| `api` | FastAPI 요청 처리 | `http://localhost:8000` |
| `worker` | Celery 리서치 작업 실행 | 내부 서비스 |
| `redis` | Celery 비동기 작업 큐 | `localhost:6379` |
| `postgres` | 작업 상태·보고서·내부 지식 문서 영속 저장 | `localhost:5432` |

API 문서는 `http://localhost:8000/docs`에서 확인할 수 있습니다.

대시보드는 `http://localhost:8000`에서 열 수 있습니다. `APP_API_KEY`를 설정한 경우 API 요청에 `X-API-Key` 헤더를 함께 전달해야 합니다.

## 4. 리서치 작업 요청

별도 PowerShell 창에서 실행합니다.

```powershell
$body = @{
  topic = "2026년 한국 AI 에이전트 시장 동향"
  audience = "신사업 임원"
  depth = "deep"
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/research" `
  -ContentType "application/json" `
  -Body $body
```

응답 예시입니다.

```json
{
  "task_id": "2cbe3b6c-...",
  "status": "queued",
  "created_at": "2026-07-22T..."
}
```

## 5. 진행 상태와 결과 조회

위 응답의 `task_id`를 넣어 폴링합니다.

```powershell
$taskId = "2cbe3b6c-..."
Invoke-RestMethod -Uri "http://localhost:8000/research/$taskId"
```

상태는 `queued → running → completed` 순서로 변경됩니다. `completed`일 때 응답의 `report` 필드에 Markdown 보고서가 담깁니다.

## 6. 종료

서비스 로그가 표시된 창에서 `Ctrl+C`를 누르거나 다음을 실행합니다.

```powershell
docker compose down
```

## 7. 자동 테스트

실행 중인 서비스와 별개로 다음 명령 하나로 테스트를 실행합니다.

```powershell
.\scripts\test.ps1
```

또는 Docker 명령을 직접 실행합니다.

```powershell
docker compose --profile test run --rm test
```

테스트는 인용 품질 지표, PDF 생성, GraphDB 폴백 관계 생성, 대시보드/API 요청 계약을 검증합니다. GitHub에 push 또는 pull request를 만들면 `.github/workflows/test.yml`이 같은 테스트를 자동으로 실행합니다.

## 문제 해결

- **Docker daemon 오류**: Docker Desktop이 실행 중인지 확인합니다.
- **작업이 `queued`에 머묾**: `docker compose logs worker`로 Celery worker 오류를 확인합니다.
- **API가 응답하지 않음**: `docker compose logs api`와 `http://localhost:8000/health`를 확인합니다.
- **검색 결과가 부실함**: `.env`에 `TAVILY_API_KEY`를 설정한 뒤 `docker compose up --build`로 재시작합니다.
