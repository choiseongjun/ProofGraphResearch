# 포트폴리오 제출 체크리스트

## 제출 전

- [ ] `.env`와 실제 API 키가 Git에 포함되지 않았는지 확인
- [ ] `docker compose --profile test run --rm test` 통과
- [ ] `http://localhost:3000`에서 자동 수집·리서치·출처 확인 흐름 시연
- [ ] Docker 컨테이너 상태 확인: `docker compose ps`
- [ ] README의 실행 방법을 새 PC에서 재현 가능하게 확인

## 화면 캡처

- [ ] Workflow 계약 화면
- [ ] 자동 RAG 수집·색인 화면
- [ ] 리서치 실행 완료 보고서
- [ ] 출처·품질 점수·근거 그래프 화면
- [ ] Neo4j Browser 관계 그래프 화면

## 면접 준비

- [ ] Redis와 PostgreSQL의 역할 차이를 30초 안에 설명
- [ ] pgvector와 Neo4j를 함께 쓴 이유 설명
- [ ] RAG와 파인튜닝의 차이 설명
- [ ] 실제 파인튜닝 모델은 없고 학습 파이프라인만 구현됐음을 명확히 설명
- [ ] 자동 수집 결과도 출처 검증이 필요하다는 한계와 개선 방안 설명
