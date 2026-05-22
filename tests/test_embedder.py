"""Tests for src.embedder (API 키 의존 X, factory + 비용 계산만 검증)"""
import pytest

from src.embedder import EMBEDDING_MODELS, estimate_cost, get_embedder


def test_known_providers_registered():
    """3개 provider가 모두 등록되어 있는지."""
    expected = {"openai-small", "openai-large", "gemini"}
    assert set(EMBEDDING_MODELS) == expected


def test_each_provider_has_complete_tuple():
    """각 항목이 (model_id: str, dim: int, price: float) 형식인지."""
    for provider, value in EMBEDDING_MODELS.items():
        assert len(value) == 3, f"{provider} tuple incomplete"
        model_id, dim, price = value
        assert isinstance(model_id, str) and model_id
        assert isinstance(dim, int) and dim > 0
        assert isinstance(price, float) and price >= 0


def test_get_embedder_unknown_provider_raises():
    """알 수 없는 provider면 ValueError."""
    with pytest.raises(ValueError, match="Unknown"):
        get_embedder("invalid-provider")


def test_estimate_cost_zero_tokens_is_zero():
    """0 토큰이면 비용 0."""
    for provider in EMBEDDING_MODELS:
        assert estimate_cost(0, provider) == 0.0


def test_estimate_cost_scales_linearly():
    """비용은 토큰 수에 선형 비례."""
    for provider in EMBEDDING_MODELS:
        price = EMBEDDING_MODELS[provider][2]
        if price == 0:
            continue
        cost_1m = estimate_cost(1_000_000, provider)
        cost_2m = estimate_cost(2_000_000, provider)
        assert cost_1m == pytest.approx(price)
        assert cost_2m == pytest.approx(2 * price)


def test_estimate_cost_unknown_provider_raises():
    """알 수 없는 provider에 estimate_cost 호출 시 ValueError."""
    with pytest.raises(ValueError, match="Unknown"):
        estimate_cost(1000, "invalid")
