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
  - **라우팅 (자동 분기, 핵심)**: 사용자가 파일마다 수동 선택 X. `parse_file`이 frontmatter의 `source` URL에서 **도메인 추출 → PARSERS[domain]로 자동 라우팅**:
    ```python
    def parse_file(path):
        source = read_frontmatter(path)["source"]
        domain = extract_domain(source)        # 예: "aitimes.com"
        parser = PARSERS.get(domain, parse_generic)  # 미등록 도메인은 fallback
        return parser(path)
    ```
  - **섞인 코퍼스 처리**: data/에 여러 플랫폼 뉴스가 섞여 있어도 각 파일이 도메인 기준 자동 라우팅 → 올바른 정제. **이게 Strategy Pattern의 핵심 가치** (이종 소스 한 폴더에서 처리). MVP 후 다른 플랫폼 뉴스 섞어서 테스트 예정.
  - **미등록 도메인 fallback**: `parse_generic` (frontmatter만 추출, 본문은 이미지/공백 정리 정도의 보수적 처리) 또는 명시적 에러 — 도입 시 결정.
  - **MVP에서 미적용 이유**: YAGNI 원칙 (You Aren't Gonna Need It). 포털 1개일 땐 추상화 = 비용만, 가치 0. 2번째 포털 추가 시점에 리팩토링.

## Task 07 (Retrieval) 추가 (2026-05-23)
- **k값 sweep 실험** — k={3,4,6} × 10 질문셋으로 정확도/노이즈/비용 비교. MVP default=4는 임의 선정.
- **동적 k (질문 타입 분류)** — 단일 사실(k=2~3) / 종합(k=4~6) / 비교(k=6~10) 자동 분기. LLM/규칙 기반 분류기 도입.
- **퍼센트 기반 k** — 데이터셋 1만+ 청크 시 절대값 대신 `k = ceil(N * %)`. 데이터셋 성장에 적응적.
- **Score threshold (provider별 분리)** — 단일 값 불가능 실증됨. provider별 분포 + margin 기반(top-1 vs top-2 갭) 신뢰도 동적 평가.
- **메타데이터 필터링 묶음** — `published` → datetime, `keywords` → list 형식 정리 + FAISS → Chroma/Pinecone 등 필터 강한 DB 재검토.
- **Query cache** — 동일 쿼리 반복 시 임베딩 재호출 방지.

## 외부 리뷰 반영 — Retrieval/Eval 우선순위 재정렬 (2026-05-23)

**ROI 순으로 재정렬** (기존 Hybrid→MMR→Re-rank → 신규 MMR→QueryRewrite→Hybrid묶음→Re-rank):

### 1순위: Context Deduplication / MMR (relevance-diversity tradeoff)
- 단순 dedup 아님 — relevance와 다양성의 trade-off 최적화. **context breadth 확보 + 토큰 가성비**.
- 실측: 모든 provider에서 top-k 중복 청크 빈번 (E1/E4/E5 결과).
- 구현 비용 가장 낮음 (`max_marginal_relevance_search` 호출 한 줄).

### 2순위: Query Rewriting (LLM 기반)
- **위치: backend retrieval gateway 계층** (frontend ❌) — observability / caching / AB test / prompt versioning / analytics 모두 backend 관리 용이.
- 한국어 RAG 함정 완화: `오픈에이아이`→`OpenAI`, `어제`→`2026-05-22`, 부정 표현 의도 추출.
- 패턴: Multi-Query (LLM이 3가지 표현 분기) / HyDE (가상 답변 임베딩) 검토.

### 3순위: Hybrid (BM25 + Vector) 묶음
- **단일 항목 아니라 묶음 도입**:
  - BM25 sparse retrieval 채널
  - **Kiwi 한국어 형태소 분석기** (sparse tokenizer)
  - **Synonym normalization** (외래어/영문 표기 변형)
  - **Query expansion** (관련어 자동 확장)
- 네 가지가 같이 가야 효과. Kiwi 단독만으론 부족.

### 4순위: Re-ranking
- 현재 169 청크엔 오버엔지니어링 명시.
- Hybrid 후보군이 커지고 인덱스 수천+ 시점에 Cross-Encoder/Cohere 도입.

## 외부 리뷰 반영 — Evaluation Infra 신규 항목 (2026-05-23)

### Golden Dataset (정식 v2)
- Task 11에서 v1 seed(10문항 + schema) 구축. v2에서:
  - 50 → 200 문항 확장
  - 라벨 스키마 강화 (`failure_labels`로 어떤 개선이 어떤 failure를 줄였는지 측정)
  - embedding/chunking/hybrid 변경 시 자동 회귀 측정 기준
- **이게 없으면 v2 진입 시 "좋아졌는지" 측정 불가능**.

### Retrieval logging infrastructure
- v1은 file 기반 jsonl (Task 09에서 골격). v2에서:
  - DB 영속 저장 (postgres/sqlite)
  - 쿼리 분석 dashboard
  - "user correction signal" 자동 감지 (재질문/즉시 이탈/같은 질문 반복)

### 운영 metrics dashboard
- Task 11에서 v1 측정 (거부율 + citation coverage). v2에서:
  - **Top-k entropy** (같은 기사 4개 vs 서로 다른 기사 4개 분포) — MMR 효과 검증 지표
  - Latency/cost trend
  - LangSmith 트레이싱 연동
- 현재는 corpus 작아 entropy 의미 적음. MMR 도입 후 본격 측정.

### Automated eval platform
- 현재는 수동 채점. v2:
  - Ragas (Faithfulness / Answer Relevance / Context Precision/Recall)
  - LLM-as-judge 자동화
  - CI 회귀 테스트 통합

### Agentic RAG / Tool-use RAG (2026-05-24)
- 현재 `search()`는 독립 함수 (LLM/CLI와 의존성 분리됨) → function-calling tool로 노출 가능한 구조.
- v2 구상: 일반 챗봇이 질문을 받고, "이건 AI 뉴스 검색이 필요하다"를 function calling으로 판단 → `search()`를 tool로 호출 → 청크 받아 답변.
- 끼우는 비용: tool 스키마 정의 + 핸들러 glue만. **`search()` 자체는 0줄 수정** (의존성 분리의 보상).
- 멀티턴 대화 + user correction signal(위 항목)과 함께 가면 시너지.
