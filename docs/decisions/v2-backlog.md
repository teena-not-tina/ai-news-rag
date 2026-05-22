# v2 백로그 (MVP 이후 고도화 아이디어)

MVP 진행 중 떠오른 추가 아이디어를 여기에 모은다. MVP는 그대로 진행하고, 완성·평가 후 우선순위 매겨 v2에 반영.

## 초기 등록 (2026-05-22)

- **Semantic Chunking** — 의미 변화 감지 자동 분할. 청킹 정밀도 향상.
- **Parent-Child Retriever** — 작은 청크로 검색, 부모 청크로 LLM 컨텍스트 확장.
- **Streamlit UI** — CLI 대체, 채팅 인터페이스.
- **답변 스트리밍** — 토큰 단위 출력으로 UX 향상.
- **다중 턴 대화** — 세션/히스토리 관리.
- **Ragas 자동 평가** — Faithfulness / Answer Relevance 등 LLM-as-judge 지표 자동화.
- **메타데이터 필터링** — 날짜 범위, 태그 필터. 필요 시 FAISS → Chroma 마이그레이션.
- **LLM 전처리 표준화** — 청킹 전 LLM으로 데이터 정제 (비용 vs 정밀도 트레이드오프).
- **API Key Registry 문서** (`docs/security/api-keys.md`) — 키 메타데이터(이름/만료/scope/회전이력) 문서화. 90일 회전 알림 + 포트폴리오 보안 어필용.
- **하이브리드 검색 (BM25 + Vector)** — 키워드(`#태그`) 정확 매칭 + 의미 검색 결합. 정밀도 향상. 키워드는 이미 NewsArticle.keywords에 추출되어 있음 → 인덱싱 단계에서 활용 가능.
- **GraphRAG** — 키워드/엔티티를 노드로, 기사를 관계 엣지로. 다단계 추론 가능 ("엔비디아와 중국의 관계는?"). 데이터셋 확장 시 ROI 상승.
- **관련기사 cross-reference** — 본문 "관련기사" 섹션에서 URL 추출 → 내부 데이터셋 인덱스(idxno)와 매칭해 그래프 엣지 생성. 현재 데이터셋 내부 엣지율 13% (16/126) → 데이터셋 확장 시 활용도↑.
- **멀티모달 RAG** — 이미지/차트 분석 (CLIP 임베딩 등). 현재는 이미지 마크다운 제거.

## 진행 중 추가
- **Chunk size sweep 실험** (Task 11 평가 확장) — chunk_size {300, 500, 800}으로 인덱스 3개 만들고 동일 질문셋으로 정확도/노이즈/latency 비교. 어떤 사이즈가 우리 데이터에 최적인지 데이터 기반 결정. MVP 일정상 v2로 미룸.
- **Full config externalization** — `config.yaml` 또는 env vars로 chunk_size / top_k / 모델명 / 경로 등 모든 튜닝 파라미터 외부화. 현재는 함수 default + caller override로 충분. 운영 환경 분리 / CI에서 다양한 설정 테스트 필요해질 때 도입.
- **`langchain-google-genai` 업그레이드** — 현재 `2.0.4`는 deprecated될 `google.generativeai` 패키지 사용 (FutureWarning + 최신 모델 `text-embedding-004` 미지원). v2.1+ 또는 새 `google.genai` 패키지로 migrate 후 `text-embedding-004` 적용. 현재 MVP는 fallback인 `models/embedding-001` 사용 중.
- **Embedding registry 외부화** — 현재 `EMBEDDING_MODELS` dict가 코드에 박혀있음. 플러그인 시스템으로 외부 provider 동적 추가 가능하게 (예: 새 provider 등록 시 코드 수정 없이 config로). MVP 규모엔 불필요.
- **다중 뉴스 포털 파서 (Strategy Pattern)** — 현재 파서는 AItimes 옵시디언 클립 포맷 전용 (byline/관련기사/키워드/저작권자 패턴). 연합뉴스/중앙일보/조선일보 등 다른 포털 지원 시 **Strategy Pattern** 도입:
  - **개념**: 공통 인터페이스(`parse(path) -> NewsArticle`)를 정의, 포털별 구현 분리. 호출자는 인터페이스만 의존. = 추상화 + 인터페이스 + 의존성 분리 + 객체지향이 합쳐진 패턴.
  - **Python 구현 옵션** (가장 가벼움 → 무거움):
    1. `dict of functions` — `PARSERS = {"aitimes.com": parse_aitimes, ...}` + dispatcher. **MVP 확장에 가장 적합.**
    2. `Protocol` — 타입 힌트 ✓, 인터페이스 명시
    3. `ABC` (Abstract Base Class) — 미구현 시 강제 에러. 외부 기여자 받을 때.
  - **파일 구조 제안**: `src/parsers/aitimes.py`, `src/parsers/yna.py`, `src/parsers/__init__.py` (dispatcher).
  - **MVP에서 미적용 이유**: YAGNI 원칙 (You Aren't Gonna Need It). 포털 1개일 땐 추상화 = 비용만, 가치 0. 2번째 포털 추가 시점에 리팩토링.
