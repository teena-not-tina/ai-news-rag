"""Tests for src.search.search (FakeEmbeddings, API 호출 X)."""
from pathlib import Path

import pytest
from langchain_core.embeddings import FakeEmbeddings

from src.indexer import build_index
from src.parser import load_all
from src.search import DEFAULT_K, SearchHit, search
import src.search as search_mod

DATA_DIR = Path(__file__).parent.parent / "data"

# 테스트 픽스처 상수
ARTICLE_LIMIT = 5    # k=DEFAULT_K(4) 안전 커버: 5 기사 × 평균 3 청크 ≈ 15 청크
FAKE_EMBED_DIM = 8   # FakeEmbeddings 차원 — 작을수록 테스트 빠름 (실제 차원과 무관)


@pytest.fixture(autouse=True)
def _clear_store_cache():
    """매 테스트마다 모듈 캐시 초기화 — tmp_path 인덱스 격리."""
    search_mod._STORE_CACHE.clear()
    yield
    search_mod._STORE_CACHE.clear()


@pytest.fixture
def fake_index(tmp_path):
    """ARTICLE_LIMIT 기사로 작은 FAISS 인덱스 빌드 후 (store_dir, embedder, provider) 반환."""
    articles = load_all(DATA_DIR)[:ARTICLE_LIMIT]
    fake = FakeEmbeddings(size=FAKE_EMBED_DIM)
    provider = "test"
    build_index(
        articles=articles,
        provider=provider,
        embedder=fake,
        store_dir=tmp_path,
        cache_dir=tmp_path / "cache",
    )
    return tmp_path, fake, provider


def test_search_returns_default_k_hits(fake_index):
    """k 미지정 시 DEFAULT_K개 반환."""
    store_dir, fake, provider = fake_index
    hits = search("test query", provider=provider,
                  embedder=fake, store_dir=store_dir)
    assert len(hits) == DEFAULT_K
    assert all(isinstance(h, SearchHit) for h in hits)


def test_search_respects_k_override(fake_index):
    """k를 default와 다른 값으로 호출 시 그대로 반영 — per-query 파라미터 검증."""
    store_dir, fake, provider = fake_index
    override_k = DEFAULT_K - 2
    hits = search("test query", provider=provider, k=override_k,
                  embedder=fake, store_dir=store_dir)
    assert len(hits) == override_k


def test_search_hit_preserves_metadata(fake_index):
    """SearchHit에 title/source가 채워져 있고 URL 형식."""
    store_dir, fake, provider = fake_index
    hits = search("test query", provider=provider, k=1,
                  embedder=fake, store_dir=store_dir)
    h = hits[0]
    assert h.title, "title missing"
    assert h.source.startswith("http"), f"source not a URL: {h.source!r}"
    assert h.text, "text missing"


def test_search_score_is_float_and_sorted(fake_index):
    """score는 float이고, top-k는 L2 distance 오름차순 (작을수록 유사)."""
    store_dir, fake, provider = fake_index
    hits = search("test query", provider=provider,
                  embedder=fake, store_dir=store_dir)
    scores = [h.score for h in hits]
    assert all(isinstance(s, float) for s in scores)
    assert scores == sorted(scores), f"scores not ascending: {scores}"


def test_search_missing_store_raises(tmp_path):
    """인덱스 없는 디렉토리에 search → FileNotFoundError + 빌드 안내 메시지."""
    fake = FakeEmbeddings(size=FAKE_EMBED_DIM)
    with pytest.raises(FileNotFoundError, match="Run `python -m src.indexer build"):
        search("q", provider="test", embedder=fake, store_dir=tmp_path)
