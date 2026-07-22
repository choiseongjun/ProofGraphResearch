# 3분 데모 스크립트

## 0:00 - 문제와 실행

대시보드에서 `2026년 한국 AI 에이전트 시장 동향`을 입력한다. 이 시스템은 장시간 리서치 요청을 HTTP 연결에 묶지 않고 Celery worker로 넘긴다.

## 0:30 - 진행 과정

`Agent timeline`에서 Planner, Searcher, Compression, Graph mapper, Writer, Critic이 SSE로 순차 표시되는 것을 보여준다. 각 완료 이벤트에는 실제 소요 시간이 있다.

## 1:20 - 신뢰성

완료 화면의 인용 품질 점수, 출처 목록, Markdown/PDF 내보내기를 보여준다. 실패한 작업은 화면의 `이 작업 재실행` 버튼으로 새 실행 이력을 생성한다.

## 2:00 - 데이터 저장

PostgreSQL에는 보고서·실행 이력·성능 지표가, Neo4j에는 `Research → Source → Entity` 근거 그래프가 남는다는 점을 Neo4j Browser 쿼리로 보여준다.

## 2:30 - 비용 제어

`.env`의 `LLM_PROVIDER=ollama`과 `OLLAMA_MODEL=hoangquan456/qwen3-nothink:4b`를 보여준다. OpenAI API가 아닌 로컬 모델로도 동작하며, 필요할 때만 클라우드 모델로 전환할 수 있다.
