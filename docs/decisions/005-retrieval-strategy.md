# ADR 005: Retrieval 전략

- **결정일**: 2026-05-23
- **상태**: 컨펌 완료 (2026-05-23)
- **관련 Task**: Task 07

---

## 최종 결정

| 항목 | 값 |
|---|---|
| 메서드 | `FAISS.similarity_search_with_score` |
| k (top-k) | **default 4** (per-query 파라미터, 호출자가 매번 override 가능) |
| Provider 선택 | 함수 인자 (`search(query, provider, k)`) — 하드코딩 X |
| Store 로딩 | 모듈 레벨 dict 캐시 (`_STORE_CACHE`) — 반복 쿼리 시 디스크 I/O 0 |
| 반환 형식 | `SearchHit` dataclass (`text / title / source / published / score`) |
| 인터페이스 | **`search()` 함수만** (LCEL retriever는 Task 08에서 결정) |
| Score 의미 | L2 distance (작을수록 유사). 코사인 아님 — 비교 시 주의 |
| 메타데이터 필터 | 없음 — MVP는 본문 의미 검색만 |

---

## 5요소

### 배경
- 인덱싱 완료 (Task 06). 이제 "쿼리 → 관련 청크 N개" 단계 필요.
- 결정 변수: **검색 알고리즘 / k값 / score 반환 여부 / provider 분기 / 인터페이스 / 메타데이터 필터링**.
- 잘못 설계 시 답변 노이즈↑, Task 08 프롬프트 디버깅 시간↑, Task 11 평가 신뢰도↓.

### 임팩트
| 결정 | 영향 |
|---|---|
| k=4 | 답변 정확도 ↔ context window 비용·노이즈 트레이드오프. MVP default. |
| score 반환 | Task 11 평가(노이즈 비율) 측정 가능 vs 불가능 |
| Provider 인자화 | OpenAI/Gemini 동시 비교 가능 vs 매번 코드 수정 |
| 함수 인터페이스 | 검수·평가 루프 직관적. LCEL은 Task 08에서 추가 시 비용 거의 0. |
| Store 캐싱 | 반복 쿼리 시 디스크 I/O 0 → 평가 루프 속도 |

### 대안 비교

**검색 방식:**
| 방식 | 장단점 | MVP |
|---|---|---|
| **`similarity_search_with_score` ✅** | top-k + L2 score, 단순, 평가 지표 확보 | ✅ |
| `similarity_search` | score 없음 → 평가 불가 | ❌ |
| `max_marginal_relevance_search` (MMR) | 다양성 보장. 긴 기사의 중복 청크 회피 | 🟡 v2 |
| Hybrid (BM25 + Dense) | 키워드+의미 결합. 모델명/고유명사에 강함 | 🟡 v2 |
| Re-ranking (Cohere/Cross-Encoder) | top-20 뽑고 재순위. 정확도↑ but 추가 API | 🟡 v2 |

**k 값 — 두 변수 (데이터 크기 + 질문 타입):**

| 데이터 크기 | 적절한 k | 비고 |
|---|---|---|
| **52 articles / 169 chunks (우리)** | **3~5** | 평균 3 청크/기사, k=4면 1~3 기사 커버 |
| 500 articles / 1,500 chunks | 5~8 | 후보 풍부, 토픽 다양성↑ |
| 10K+ chunks | top-20 → re-rank top-5 | 2단계 패턴 일반적 (% 기반 동적 k) |

| 질문 타입 | 권장 k | 예시 |
|---|---|---|
| 단일 사실 | 2~3 | "o3 출시일?" |
| 종합/요약 | 4~6 | "AI 칩 시장 동향?" |
| 비교 | 6~10 | "GPT-4 vs Gemini Ultra 차이?" |

→ **k는 search-time per-query 파라미터.** 인덱스에 박힌 게 아니라 호출 시점에 결정. `search(query, k=4)` default 두되 caller가 매번 override 가능.

**인터페이스:**
| 스타일 | 장점 | 우리 채택 |
|---|---|---|
| **함수 `search()` ✅** | 디버깅·테스트·평가 루프 직관적 | Task 07 |
| LCEL Retriever | LLM 체이닝 / 스트리밍 / 배치 / 트레이싱 공짜 | **Task 08에서 결정** |

→ **이유:** Task 07은 retrieval 단일 컴포넌트. LCEL은 컴포넌트 2개 이상 체이닝할 때 진가. 함수가 단일 컴포넌트에선 더 깔끔. Task 08(LLM 합치는 순간)에 `as_retriever()` 한 줄 추가하면 LCEL 진입 비용 0.

### 동작 원리

```python
_STORE_CACHE: dict[str, FAISS] = {}

def search(query: str, provider: str = "openai-small", k: int = 4) -> list[SearchHit]:
    store = _load_store(provider)  # 첫 호출만 디스크 I/O, 이후 캐시
    raw = store.similarity_search_with_score(query, k=k)
    # raw = [(Document, L2_distance), ...]
    return [SearchHit.from_document(doc, score) for doc, score in raw]
```

**핵심 동작:**
1. 쿼리도 **동일 embedder**로 임베딩 (차원·공간 일치 필수)
2. `FAISS.load_local(..., allow_dangerous_deserialization=True)` — pkl이 pickle 기반이라 필수
3. L2 distance 반환 (작을수록 유사). 코사인 유사도 아님.
4. Store는 한 번 load 후 `dict[provider, FAISS]` 캐싱 — 반복 호출 시 디스크 I/O 0

### 사이드 이펙트 ⚠️

| 이슈 | 대응 |
|---|---|
| `allow_dangerous_deserialization=True` 보안 경고 | 자체 빌드 인덱스만 로드 — README/ADR 명시 |
| 모듈 레벨 캐시 = 인덱스 재빌드 후 stale | 프로세스 재시작 필요. CLI 한 회 실행 사이클엔 무관 |
| 쿼리 임베딩은 캐시 X | OK — 동일 쿼리 반복 가능성 낮음. v2-backlog의 query cache 후보 |
| OpenAI 쿼리 임베딩 비용 | 쿼리당 ~$0.00002. 무시 가능 |
| 긴 기사에서 비슷한 청크 4개 다 뽑힐 위험 | MVP 감수. Task 11에서 측정 후 MMR 도입 판단 |
| `published`가 ISO 문자열 — 날짜 필터 불가 | 메타데이터 필터링과 함께 v2-backlog (형식 정리 + DB 재검토 묶음) |
| k=4 임의 선정 | v2-backlog "k값 sweep + 동적 k" 항목 참고 |

---

## 함수 시그니처

```python
@dataclass
class SearchHit:
    text: str
    title: str
    source: str       # 원문 URL
    published: str
    score: float      # L2 distance (작을수록 유사)

def search(
    query: str,
    provider: str = "openai-small",
    k: int = 4,
    embedder: Embeddings | None = None,   # DI: 테스트용 FakeEmbeddings
    store_dir: Path = DEFAULT_STORE_DIR,
) -> list[SearchHit]
```

CLI:
- `python -m src.search "질문"` — openai-small로 검색
- `python -m src.search "질문" --provider gemini --k 6`

---

## v2-backlog 연계

- k값 sweep 실험 / 동적 k(질문 타입 분류) / 퍼센트 기반 k
- Score threshold (분포 측정 후 결정)
- MMR retrieval
- Hybrid (BM25 + Vector)
- Re-ranking (Cross-Encoder)
- 메타데이터 필터링 묶음 (형식 정리 + DB 재검토)
- Query cache
