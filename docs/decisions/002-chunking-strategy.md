# ADR 002: 청킹 전략

- **결정일**: 2026-05-22
- **상태**: 컨펌됨
- **관련 Task**: Task 04

---

## 최종 결정

| 파라미터 | Default 값 | 비고 |
|---|---|---|
| 라이브러리 | `RecursiveCharacterTextSplitter` (LangChain) | |
| chunk_size | **500** | 글자수(character) 기준 |
| chunk_overlap | **50 (10%)** | 경계 정보 유실 방지 |
| separators | `["\n\n", "\n", "다. ", ". ", " ", ""]` | 한국어 종결(`다. `) 추가 |
| 청킹 대상 | `article.body` (메타데이터 제외) | metadata는 Document.metadata에 별도 보존 |

> ⚙️ **이 값들은 default이며 caller가 override 가능** — `chunk_articles(articles, chunk_size=..., chunk_overlap=..., separators=...)`.
> AItimes 뉴스(평균 ~1200자 본문) 기준 분석된 값. 다른 데이터셋이면 자신의 길이 분포에 맞게 조정.

---

## 5요소

- **배경**: 문서를 작은 조각으로 잘라 임베딩. 너무 크면 검색 정밀도↓, 너무 작으면 LLM 컨텍스트↓. 청킹 = 검색 단위 결정.
- **임팩트**: chunk_size/overlap/separator 3개가 RAG 품질의 1차 결정 변수. 평가에서 정확도로 즉시 드러남.
- **대안 비교**:
  | 방식 | 장단점 |
  |---|---|
  | **RecursiveCharacterTextSplitter ✅** | LangChain 표준, 의미 경계 존중 / 진짜 의미 변화는 못 봄 |
  | Token-based (tiktoken) | LLM 토큰 정확 매칭 / 한국어 토큰화 불안정 |
  | Semantic Chunking | 의미 변화 자동 감지 / 임베딩 호출 비용↑ → **v2** |
  | Fixed-size | 가장 단순 / 단어/문장 끊김 |
- **동작 원리**: separator 우선순위(`\n\n` → `\n` → `다. ` → `. ` → ` ` → `""`)대로 자르고 chunk_size 초과 시 다음 단계 폴백. 오버랩으로 경계 정보 보존.
- **사이드 이펙트** ⚠️: 한국어 문장 종결(`다. `)을 separator에 추가했으나, 모든 경우 커버 X (구어체 종결 등). chunk_size 500자 = 약 750-1000 토큰, text-embedding-3-small max 8191 토큰 한참 안 닿음.

---

## 데이터 분석 (2026-05-22 측정)

52개 본문 길이 분포 (글자수):

| 지표 | 값 |
|---|---|
| 평균 | 2,698 |
| 중앙값 | 2,739 |
| 표준편차 | 719 |
| 최소 | 327 (단신 류) |
| 최대 | 5,022 |
| 10%ile | 2,029 |
| 90%ile | 3,383 |

→ 대부분 2000-3400자대 분포. 균일.

---

## 파라미터 비교

| 옵션 | chunk_size | overlap | 청크/기사 | 총 청크 (~52편) | 평가 |
|---|---|---|---|---|---|
| A. 작게 | 300 | 50 | ~9 | ~460 | 정밀도↑, 임베딩 비용↑ |
| **B. 중간 ✅** | **500** | **50** | **~5-6** | **~290** | **균형 |** |
| C. 크게 | 800 | 100 | ~3-4 | ~170 | LLM 컨텍스트↑, 정밀도↓ |

**B 채택 이유**:
1. 한국어 뉴스 한 단락 200-400자 → 500자면 1-2 단락 캡처
2. 약 290개 청크 = FAISS에서 즉시 검색, 임베딩 비용 거의 0
3. 검색 top-4 = ~2000자 컨텍스트 → gpt-4o-mini에 부담 없음

---

## 향후 개선 (v2-backlog 연계)

- **Semantic Chunking**: 의미 변화 감지 자동 분할 (v2)
- **Parent-Child Retriever**: 작은 청크로 검색, 부모 청크로 컨텍스트 확장 (v2)
- **Token-based 청킹**: tiktoken 기반 (필요 시)
