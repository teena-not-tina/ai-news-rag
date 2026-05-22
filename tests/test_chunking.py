"""Tests for chunking in src.indexer"""
from pathlib import Path

from src.indexer import CHUNK_SIZE, CHUNK_OVERLAP, chunk_articles
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


def test_chunks_respect_size_bound():
    """청크 크기는 chunk_size + chunk_overlap 이내 (Recursive splitter 특성상 약간의 여유)."""
    articles = load_all(DATA_DIR)
    chunks = chunk_articles(articles)

    # RecursiveCharacterTextSplitter는 separator 경계 때문에 약간 초과 가능
    upper_bound = CHUNK_SIZE + CHUNK_OVERLAP + 50  # 50자 여유
    for c in chunks:
        assert len(c.page_content) <= upper_bound, \
            f"chunk too large: {len(c.page_content)} > {upper_bound}"
