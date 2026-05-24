# Engineering Decisions (ADR)

각 결정은 5요소(배경 / 임팩트 / 대안 비교 / 동작 원리 / 사이드 이펙트) 형식으로 기록.

| # | Title | 상태 | 작성 시점 |
|---|---|---|---|
| [001](001-tech-stack.md) | 기술스택 선택 (Python / LangChain / FAISS / CLI) | ✅ 컨펌됨 (2026-05-22) | Task 01 |
| [002](002-chunking-strategy.md) | 청킹 전략 (500자/50 overlap, 한국어 separator) | ✅ 컨펌됨 (2026-05-22) | Task 04 |
| [003](003-embedding-provider.md) | 임베딩 Provider (3종: OpenAI small/large + Gemini) | ✅ 컨펌됨 (2026-05-22) | Task 05 |
| [004](004-vector-store-indexing.md) | FAISS 인덱싱 + 임베딩 캐시 | ✅ 컨펌됨 (2026-05-23) | Task 06 |
| [005](005-retrieval-strategy.md) | 검색 전략 (rank-only, k=4, 모듈 캐시) | ✅ 컨펌됨 (2026-05-23) | Task 07 |
| [006](006-prompt-design.md) | 프롬프트 설계 (환각 방지, 번호 인용, temp=0) | ✅ 컨펌됨 (2026-05-24) | Task 08 |
| [007](007-evaluation-metrics.md) | 평가 방법론 + ChatGPT vs Gemini 비교 | ✅ 컨펌됨 (2026-05-25) | Task 11 |

- MVP 이후 고도화 아이디어 → [v2-backlog.md](v2-backlog.md)
