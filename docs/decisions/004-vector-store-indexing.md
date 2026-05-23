# ADR 004: FAISS 인덱싱 + 임베딩 캐시

- **결정일**: 2026-05-22
- **상태**: 컨펌 완료 (2026-05-23)
- **관련 Task**: Task 06

---

## 최종 결정

| 항목 | 값 |
|---|---|
| Vector DB | FAISS (`langchain-community.vectorstores.FAISS`) |
| Index type | IndexFlatL2 (LangChain `FAISS.from_documents` 기본) |
| 임베딩 캐시 | `CacheBackedEmbeddings` + `LocalFileStore` |
| 캐시 위치 | `data/embedding_cache/` (gitignored) |
| 인덱스 위치 | `data/vector_store/{provider}/` (provider별 분리) |
| Namespace | provider 이름 (예: `openai_small`) — 충돌 방지 |

> FAISS **선택 자체**는 ADR 001에 기록. 이 ADR은 **인덱싱 패턴 + 캐싱 전략**에 한정.

---

## 5요소

- **배경**: 임베딩은 비싸고(가격) 느림(latency). 재실행 시 같은 청크는 재계산하지 않게 캐시 필요. + 차원/공간 다른 provider 인덱스는 절대 섞을 수 없어 디렉토리 분리.
- **임팩트**: 개발/평가 iteration 비용↓. 169 청크 × 3 provider 첫 빌드 후, 재실행 거의 즉시 (캐시 적중).
- **대안 비교**:
  | 방식 | 장단점 |
  |---|---|
  | 캐시 X (매번 재임베딩) | 단순 / 느림+비용 |
  | FAISS `save_local` only | 간단 / 청크 1개 변경 시 전체 재임베딩 |
  | **`CacheBackedEmbeddings` ✅** | 청크별 hash 캐시, 변경분만 재호출 / 디스크 사용↑ |
  | 외부 캐시 (Redis 등) | 분산 강력 / MVP 오버킬 |
- **동작 원리**: `embedder` → `CacheBackedEmbeddings.from_bytes_store(...)` wrap. 내부적으로 `(hash(text), namespace)` → bytes 파일 매핑. 텍스트 변경 시 다른 hash → 자동 새 API 호출.
- **사이드 이펙트** ⚠️:
  - 캐시 디스크 누적 (27 MB 측정, MVP 규모 무시 가능)
  - **namespace에 provider 포함 필수** — 같은 청크라도 OpenAI 벡터와 Gemini 벡터는 공유 X
  - embedder 모델 업데이트 시 캐시는 stale. v2: namespace에 모델 버전 hash 포함 권장

---

## 실측 결과 (2026-05-22 빌드)

| Provider | 차원 | 청크 수 | 인덱스 사이즈 |
|---|---|---|---|
| `openai-small` | 1536 | 169 | 1.2 MB |
| `openai-large` | 3072 | 169 | 2.2 MB |
| `gemini` (`gemini-embedding-001`) | 3072 | 169 | 2.2 MB |
| **총 캐시 (`data/embedding_cache/`)** | - | - | **27 MB** |

---

## 디렉토리 구조

```
data/
├── vector_store/              ← gitignored
│   ├── openai_small/
│   │   ├── index.faiss        # 벡터 데이터 (FAISS binary)
│   │   └── index.pkl          # 메타데이터 (title/source/keywords/...)
│   ├── openai_large/
│   └── gemini/
└── embedding_cache/           ← gitignored (대용량)
    └── <namespace>_<hash>     # bytes 파일들
```

---

## 함수 시그니처

```python
build_index(
    articles,
    provider="openai-small",
    embedder=None,              # DI: 테스트 시 FakeEmbeddings 주입
    chunk_size=DEFAULT_CHUNK_SIZE,
    chunk_overlap=DEFAULT_CHUNK_OVERLAP,
    separators=None,
    store_dir=DEFAULT_STORE_DIR,
    cache_dir=DEFAULT_CACHE_DIR,
) -> Path  # 저장 경로 반환
```

CLI:
- `python -m src.indexer build [--provider X]` — 단일 provider
- `python -m src.indexer build-all` — 3개 모두

---

## v2-backlog 연계

- **IndexFlatL2 → HNSW** 마이그레이션 (벡터 수 1만+ 시 검색 속도)
- **외부 캐시** (Redis 등) — 분산/멀티노드 환경
- **버전 hash in namespace** — embedder 모델 업데이트 시 자동 무효화
