# 성능 측정 가이드

## 측정 목적

AI 워크플로는 단순 응답 시간보다 단계별 병목과 근거 품질을 함께 측정해야 합니다.

## 기록할 지표

| 지표 | 확인 위치 | 의미 |
|---|---|---|
| 전체 실행 시간 | `metrics.duration_ms` | 사용자 체감 완료 시간 |
| 단계별 시간 | `metrics.agent_durations_ms` | Planner, Searcher, Retriever, Writer 병목 |
| 인용 품질 점수 | `/v1/research/{task_id}/evaluation` | 출처 번호와 수집 출처의 정합성 |
| 수집 출처 수 | `/v1/research/{task_id}/sources` | 근거 범위 |
| RAG 색인 청크 수 | 이벤트의 `rag_index` 단계 | 지식 축적량 |

## 권장 시나리오

1. RAG가 비어 있는 상태에서 같은 주제로 실행합니다.
2. 자동 RAG 수집을 실행합니다.
3. 동일하거나 유사한 주제로 다시 실행합니다.
4. Retriever 단계 시간, 출처 수, 인용 품질을 비교합니다.

실험 결과는 모델·검색 API·네트워크·로컬 PC 사양에 따라 달라지므로, README에는 단일 숫자보다 측정 조건과 비교 방법을 함께 기록합니다.
