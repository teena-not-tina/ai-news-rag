# Engineering Decisions (ADR)

각 결정은 5요소(배경 / 임팩트 / 대안 비교 / 동작 원리 / 사이드 이펙트) 형식으로 기록.

| # | Title | 상태 | 작성 시점 |
|---|---|---|---|
| [001](001-tech-stack.md) | 기술스택 선택 (Python / LangChain / FAISS / CLI) | ✅ 컨펌됨 (2026-05-22) | Task 01 |
| [002](002-chunking-strategy.md) | 청킹 전략 (500자/50 overlap, 한국어 separator) | ✅ 컨펌됨 (2026-05-22) | Task 04 |
| 003 | 임베딩 Provider | — | Task 05 |
| 004 | 벡터 스토어 선택 | — | Task 06 |
| 005 | 검색 전략 | — | Task 07 |
| 006 | 프롬프트 디자인 | — | Task 08 |
| 007 | 평가 지표 | — | Task 11 |

- MVP 이후 고도화 아이디어 → [v2-backlog.md](v2-backlog.md)
