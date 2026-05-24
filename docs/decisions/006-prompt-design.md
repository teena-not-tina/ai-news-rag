# ADR 006: 생성 + 프롬프트 설계

- **결정일**: 2026-05-24
- **상태**: 컨펌 완료 (2026-05-24)
- **관련 Task**: Task 08

---

## 최종 결정

| 항목 | 값 | 근거 |
|---|---|---|
| LLM 추상화 | `get_llm(provider)` | embedder의 `get_embedder` 미러 — Task 11 6조합 비교 |
| LLM 매핑 | openai=`gpt-4o-mini`, gemini=`gemini-2.0-flash` | MVP 저렴/무료 tier |
| **temperature** | **0.0** | 재현성(같은 질문=같은 답) + 환각 억제. fluency 상향은 Task 11 후 실험 |
| 인터페이스 | LCEL 체인 (`prompt \| llm \| StrOutputParser`) | Task 11 batch/stream 대비 |
| score 전달 | Rank-only (순위 번호만, raw score X) | provider 간 score scale 다름 (ADR 005) |
| 인용 형식 | 번호 `[1], [2]` (참고자료 번호와 일치) | 토큰↓ 가독성↑, 출력 번호목록이 참고문헌 역할 (튜닝 결정) |
| 반환 | `AnswerResult` dataclass | 모델/답변/근거 추적 + Task 11 필드 확장 |
| 거부 문장 | 고정 상수 `NO_ANSWER` | 거부율 측정 기준 |

---

## 5요소

### 배경
검색(Task 07)이 청크를 가져옴 → LLM이 그 청크로 **출처 인용 + 환각 방지** 답변을 만드는 마지막 조각. 외부 리뷰(조각 1, 4)에서 "prompt-only grounding 한계" + "score≠관련성"을 반영.

### 임팩트
- 프롬프트 품질 = 환각율·인용 정확도 직결 (제품 신뢰도)
- LLM 추상화 = Task 11에서 임베더3×LLM2 = 6조합 비교 가능
- LCEL = Task 11 `chain.batch()` 한 줄로 10문항 평가

### 대안 비교
| 항목 | 선택 | 대안 | 왜 |
|---|---|---|---|
| 인터페이스 | LCEL | 수동 함수 조립 | 스트리밍/배치/트레이싱 공짜. Task 07 때 "LCEL은 Task 08에서" 약속 지점 |
| score 전달 | Rank-only | raw score 숫자 전달 | provider별 scale 달라(ADR 005) LLM이 절대값 오해 위험 |
| 반환형 | AnswerResult dataclass | tuple `(answer, hits)` | "무슨 모델로 무슨 답" 추적 구조화, Task 11 필드 확장 |

### 동작 원리
```
answer(query, llm_provider, embed_provider, k)
  → search(embed_provider) → hits
  → format_context(hits)  [순위 번호만, score 숨김]
  → (prompt | llm | StrOutputParser).invoke()
  → AnswerResult(answer, hits, providers, ...)
```
- `generate()`는 `search()`와 분리 → Fake LLM으로 단위 테스트 가능
- hits 비면 LLM 호출 없이 즉시 `NO_ANSWER`

### 사이드 이펙트 ⚠️
| 이슈 | 대응 |
|---|---|
| **Prompt-only grounding은 충분조건 아님** (citation laundering: 출처 달아도 내용 안 맞을 수 있음) | retrieval 품질이 진짜 해결. v2 MMR/Hybrid. Task 11 citation coverage로 측정 |
| LLM이 지시 무시 (출처 누락) | Task 11에서 측정, 프롬프트 반복 강조로 완화 |
| 한국어 답변 품질 | 시스템 프롬프트 한국어 + "한국어로 답하세요" 명시 |
| gemini-2.0-flash 가용성 | langchain-google-genai 2.0.4에서 미지원 시 1.5-flash fallback (v2-backlog) |

---

## 사고 과정 (결정의 여정)

### temperature: 0.2 고려 → 0 선택
1. 처음 0 제안 (사실 QA = 결정성/환각 억제)
2. "분석 답변엔 약간의 창의성이 필요할 수도, fluency 위해 올려보자" → 0.2 고려
3. **재현성 트레이드오프 발견**: temp>0이면 같은 질문도 실행마다 답이 달라짐 → Task 11 6조합 비교가 노이즈투성이가 됨
4. **결론: 평가 단계엔 temp=0이 필수** (공정 비교). 제품용 fluency(0.2~0.3 추정)는 Task 11 끝나고 실제 출력 보고 결정 — 추측 말고 측정.
→ temperature는 파라미터로 노출되어 언제든 스윕 가능.

### precision↑/recall↓ 트레이드오프 (의도적 선택)
이 프롬프트는 의도적으로:
- **precision↑, hallucination↓** (좋음)
- **recall↓, refusal↑** (대가)

→ **MVP에선 이게 맞다.** 현 단계 우선순위는 "틀린 자신감 있는 답"을 줄이는 것이지 coverage 최대화가 아님. recall 개선은 v2(Hybrid/MMR). 이 선택을 명시적으로 기록해 나중에 "왜 이렇게 빡빡해?"에 답할 수 있게 함.

### 프롬프트 규칙별 근거 (외부 리뷰 반영)
| 규칙 | 왜 |
|---|---|
| 2. 주제 다루면 답, 무관할 때만 NO_ANSWER | 거부율 측정 기준 + 환각 차단 (튜닝 후 ↓ 참고) |
| 3. 해석·추론·일반화 금지 (종합요약은 OK) | citation laundering 방지. 단 정당한 요약까지 막지 않게 "새 결론만 금지"로 미세 조정 |
| 4. 부정형은 명시적 근거 있을 때만 | E4(부정 표현) 실패 정조준 |
| 5. 순위 ≠ 정답 근거 | E2(score≠관련성) 정조준, LLM 과신 방지 |

### 첫 시연 후 튜닝 (검수 발견 반영, 2026-05-24)
첫 실제 생성 시연에서 2가지 발견 → 수정:

1. **과잉 거부 (규칙 2 완화)**: "미소스가 뭐야?"가 관련 청크 3개 있는데도 거부됨.
   원인 = 규칙 2가 "핵심 정보 명시적 포함"을 요구 → "미소스는 ~이다" 정의 문장 없으니 거부.
   → 규칙 2를 "주제를 다루면 그 사실로 답, 주제 자체가 없을 때만 거부"로 완화.
   재시연 결과: 미소스 답변됨 + 무관 쿼리(콜라곰탕)는 여전히 거부 → **precision 유지 + recall 회복**.
   이는 precision↑/recall↓ 트레이드오프에서 "뭐야?" 질문조차 거부하는 건 과하다는 판단.

2. **인용 형식 (제목 → 번호)**: 처음엔 [기사 제목](URL) 강제하려 했으나, LLM이 자연스럽게
   [1] 번호로 인용 → 사실 이게 더 합리적. 참고 자료를 [1][2][3][4]로 번호 매겨 주고
   출력에 번호 목록(제목+URL)을 함께 인쇄하므로, 번호 인용이 토큰↓·가독성↑이며
   참고문헌처럼 매핑됨. → **번호 인용 [1], [2] 채택** (제목 강제 철회).

3. **환각 오판 정정**: Round 1에서 "달리3/소라" 디테일을 환각 의심했으나, grep 결과 원문에
   실재 → LLM은 정확히 근거 기반이었음. (citation laundering의 *반대* 사례 — 정상 동작)

---

## 함수 시그니처

```python
@dataclass
class AnswerResult:
    query: str
    answer: str
    hits: list[SearchHit]
    llm_provider: str
    embed_provider: str
    latency_s / input_tokens / output_tokens / cost_usd: None  # Task 11 채움
    @property
    def is_refusal(self) -> bool  # 거부율 측정

def get_llm(provider="openai", temperature=0.0) -> BaseChatModel
def generate(query, hits, provider="openai", temperature=0.0, llm=None) -> str
def answer(query, llm_provider="openai", embed_provider="openai-small",
           k=4, temperature=0.0, llm=None) -> AnswerResult
```

CLI: `python -m src.generator "질문" [--llm openai|gemini] [--embed openai-small|openai-large|gemini] [--k N]`

---

## v2-backlog 연계
- temperature 스윕 (태스크별: 사실 답변 vs 분석)
- gemini 모델 버전 fallback (2.0-flash → 1.5-flash)
- Prompt-only 넘어선 grounding (MMR/Hybrid로 retrieval 품질 ↑)
- 스트리밍 답변 (Task 09 CLI UX)
