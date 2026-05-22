# ADR 003: 임베딩 Provider

- **결정일**: 2026-05-22
- **상태**: 컨펌됨
- **관련 Task**: Task 05

---

## 최종 결정

3개 임베딩 provider 동시 지원 (Strategy Pattern factory, dict-of-functions 방식).

| Provider key | 모델 | 차원 | 가격 ($/1M) | 추정 Latency | 역할 |
|---|---|---|---|---|---|
| `openai-small` ✅ | text-embedding-3-small | 1536 | $0.02 | ~50-150 ms | MVP 기본 |
| `openai-large` ✅ | text-embedding-3-large | 3072 | $0.13 | ~100-400 ms | 가격 tier 비교 |
| `gemini` ✅ | gemini-embedding-001 | 3072 | $0 (Tier 1) | ~50-200 ms | Provider 비교 |

> **참고**: 초기 계획은 `text-embedding-004` (768d, 무료)였으나 `langchain-google-genai==2.0.4`가 deprecated `google.generativeai` 패키지를 써서 v1beta API에서 미지원. 실제 가용 모델 중 `gemini-embedding-001` 채택 (3072d). v2에서 라이브러리 업그레이드 시 재선택.

> Latency는 공개 정보 기준 추정. 실측은 Task 06 (indexing) + Task 11 (per-query) 에서.

코드 위치: `src/embedder.py` — `get_embedder(provider)` factory + `estimate_cost(tokens, provider)`

---

## 5요소

- **배경**: 임베딩 = 텍스트를 고차원 벡터로 변환. "의미 비슷한 텍스트 = 가까운 벡터" 원리. RAG 검색 가능성의 기초.
- **임팩트**: 임베딩 품질 = 검색 정확도의 1차 결정자. Provider 추상화 = Task 11 평가에서 모델 갈아끼우는 핵심 인프라.
- **대안 비교**: (위 결정 표 + 아래 v2 후보)
- **동작 원리**: 텍스트 → 신경망 → 벡터. LangChain `Embeddings` 추상화로 `embed_documents()`/`embed_query()` 통일. `get_embedder(provider)` 팩토리가 다른 모델 인스턴스 반환.
- **사이드 이펙트** ⚠️:
  - **차원/공간 다른 모델 섞으면 인덱스 호환 X** → provider별 디렉토리 분리 필수
  - Rate limit (OpenAI/Gemini 둘 다 1500 RPM) — 169 청크는 한 번에 처리 가능
  - 입력 길이 한계 (OpenAI 8191 / Gemini 2048 토큰) — 청크 500자 ≈ 750토큰이라 여유

---

## 데이터 통계 (2026-05-22 실측)

- 기사 수: **52**
- 청크 수: **169**
- 총 글자 수: **64,496**
- 추정 토큰 수: **~96,744** (한국어 1글자 ≈ 1.5 토큰)

---

## 💰 비용 추정 (인덱싱 1회)

| Provider | 차원 | 단가 | 비용 (USD) | 비용 (KRW) |
|---|---|---|---|---|
| openai-small | 1536 | $0.02/1M | $0.0019 | ~3원 |
| openai-large | 3072 | $0.13/1M | $0.0126 | ~17원 |
| gemini | 768 | 무료 | $0 | 0원 |
| **3종 합산** | - | - | **$0.0145** | **~20원** |

Task 11 평가에서 재실행해도 한 자리수 원 단위. **무시 가능.**

---

## 인덱스 저장 구조 (Task 06 영역)

```
data/vector_store/
├── openai_small/
│   ├── index.faiss   # 벡터 데이터
│   └── index.pkl     # 메타데이터 (title/source/keywords/...)
├── openai_large/
└── gemini/
```

`FAISS.save_local(path)` / `FAISS.load_local(path, embedder)`로 다룸.

---

## 평가 방법론

임베딩 자체는 결정적 변환(텍스트 → 벡터)이라 "정확도" 개념 X.
실제 품질 비교는 **파이프라인 끝**(retrieval + 답변 생성)에서 일어남.

→ 가설 / 통제 변수 / 측정 지표 / 의사결정 기준 / 한계는 **ADR 007 (Task 11 평가)** 에서 정의.

이 ADR(003)의 책임은 "**왜 이 3개 provider를 선택했나**"까지.

---

## 향후 개선 (v2-backlog 연계)

- **Embedding provider sweep 확장** — BGE-M3 (로컬, $0), Voyage AI, Cohere multilingual 등 추가
- **Hybrid 임베딩** — Dense (현재) + Sparse (BM25) 결합으로 키워드 정확 매칭 보강
- **차원 압축** (Matryoshka) — text-embedding-3-large의 3072d를 1024d/512d로 잘라 저장 공간 절약
