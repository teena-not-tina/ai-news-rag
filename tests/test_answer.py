"""Tests for src.generator (Fake LLM, 실제 API 호출 X).

단위 테스트는 성능지표(정확도/노이즈/latency/비용) 측정이 아님 — 코드 로직만 검증:
- format_context 형식
- 빈 hits → NO_ANSWER (LLM 호출 없음)
- generate가 LLM 출력을 그대로 통과시키는지
- AnswerResult.is_refusal
- get_llm unknown provider 에러
실제 6조합 성능 비교는 Task 11 (scripts/evaluate.py).
"""
import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.generator import (
    NO_ANSWER,
    AnswerResult,
    format_context,
    generate,
    get_llm,
)
from src.search import SearchHit


def _hit(title="제목A", source="https://example.com/1", text="본문 내용", score=0.5):
    return SearchHit(text=text, title=title, source=source,
                     published="2026-05-21", score=score)


def test_format_context_numbers_and_hides_score():
    """순위 번호 + title/source/text 포함, raw score는 미포함 (rank-only)."""
    hits = [_hit(title="첫째", score=0.123), _hit(title="둘째", score=0.456)]
    ctx = format_context(hits)
    assert "[1]" in ctx and "[2]" in ctx
    assert "첫째" in ctx and "둘째" in ctx
    assert "0.123" not in ctx and "0.456" not in ctx, "raw score가 노출됨"


def test_generate_empty_hits_returns_no_answer():
    """hits가 비면 LLM 호출 없이 즉시 NO_ANSWER."""
    out = generate("아무 질문", hits=[], llm=None)
    assert out == NO_ANSWER


def test_generate_passes_llm_output():
    """generate가 LLM 답변을 그대로 반환 (LCEL 체인 + StrOutputParser 동작)."""
    fake = FakeListChatModel(
        responses=["미소스는 앤트로픽의 모델입니다. [제목A](https://example.com/1)"]
    )
    out = generate("미소스가 뭐야?", hits=[_hit()], llm=fake)
    assert "미소스" in out
    assert "https://example.com/1" in out, "인용 URL이 답변에 없음"


def test_answer_result_is_refusal():
    """is_refusal이 NO_ANSWER를 정확히 판별."""
    refusal = AnswerResult(query="q", answer=NO_ANSWER, hits=[],
                           llm_provider="openai", embed_provider="openai-small")
    answered = AnswerResult(query="q", answer="실제 답변 [제목A](url)", hits=[_hit()],
                            llm_provider="openai", embed_provider="openai-small")
    assert refusal.is_refusal is True
    assert answered.is_refusal is False


def test_answer_result_is_refusal_ignores_whitespace():
    """앞뒤 공백이 있어도 거부로 판별 (strip)."""
    r = AnswerResult(query="q", answer=f"  {NO_ANSWER}\n", hits=[],
                     llm_provider="openai", embed_provider="openai-small")
    assert r.is_refusal is True


def test_get_llm_unknown_provider_raises():
    """알 수 없는 LLM provider면 ValueError."""
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        get_llm("invalid-llm")
