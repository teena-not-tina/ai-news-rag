"""Tests for chunking in src.indexer"""
from pathlib import Path

from src.indexer import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, chunk_articles
from src.parser import load_all

DATA_DIR = Path(__file__).parent.parent / "data"


def test_chunking_produces_nonempty_chunks():
    """청크가 생성되고 모두 비어있지 않은지."""
    articles = load_all(DATA_DIR)
    chunks = chunk_articles(articles)

    assert len(chunks) > 0, "no chunks produced"
    for c in chunks:
        assert c.page_content.strip(), "empty chunk found"


def test_chunks_preserve_metadata():
    """모든 청크가 title/source 메타데이터를 보존하는지."""
    articles = load_all(DATA_DIR)
    chunks = chunk_articles(articles)

    for c in chunks:
        assert c.metadata.get("title"), "chunk missing title"
        assert c.metadata.get("source", "").startswith("http"), \
            f"chunk source not a URL: {c.metadata.get('source')!r}"


def test_chunks_respect_default_size_bound():
    """default chunk_size + overlap 이내 (Recursive splitter는 separator 경계로 약간 여유)."""
    articles = load_all(DATA_DIR)
    chunks = chunk_articles(articles)

    upper_bound = DEFAULT_CHUNK_SIZE + DEFAULT_CHUNK_OVERLAP + 50  # 50자 separator 여유
    for c in chunks:
        assert len(c.page_content) <= upper_bound, \
            f"chunk too large: {len(c.page_content)} > {upper_bound}"


def test_chunking_respects_custom_params():
    """caller가 chunk_size override하면 그에 맞게 동작 (의존성 주입 검증)."""
    articles = load_all(DATA_DIR)
    chunks_default = chunk_articles(articles)
    chunks_small = chunk_articles(articles, chunk_size=200, chunk_overlap=20)

    # 작은 chunk_size = 더 많은 청크 생성
    assert len(chunks_small) > len(chunks_default), \
        f"smaller chunks should produce more chunks: {len(chunks_small)} vs {len(chunks_default)}"

    # 모든 작은 청크는 새 size 한도 내
    upper_bound = 200 + 20 + 50
    for c in chunks_small:
        assert len(c.page_content) <= upper_bound, \
            f"custom chunk too large: {len(c.page_content)} > {upper_bound}"
