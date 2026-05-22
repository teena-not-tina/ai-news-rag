"""Tests for build_index (FakeEmbeddings 사용, API 호출 X)."""
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import FakeEmbeddings

from src.indexer import build_index
from src.parser import load_all

DATA_DIR = Path(__file__).parent.parent / "data"


def test_build_index_creates_faiss_files(tmp_path):
    """build_index가 FAISS 인덱스 파일(index.faiss + index.pkl)을 저장하는지."""
    articles = load_all(DATA_DIR)[:3]  # 빠른 테스트 위해 3개만
    fake = FakeEmbeddings(size=1536)

    out_path = build_index(
        articles=articles,
        provider="test",  # cache namespace 용도만
        embedder=fake,
        store_dir=tmp_path,
        cache_dir=tmp_path / "cache",
    )

    assert out_path.exists(), "output dir not created"
    assert (out_path / "index.faiss").exists(), "index.faiss not saved"
    assert (out_path / "index.pkl").exists(), "index.pkl not saved"


def test_build_index_preserves_metadata(tmp_path):
    """인덱스 로드 시 청크 metadata(title/source)가 유지되는지."""
    articles = load_all(DATA_DIR)[:3]
    fake = FakeEmbeddings(size=1536)

    out_path = build_index(
        articles=articles,
        provider="test",
        embedder=fake,
        store_dir=tmp_path,
        cache_dir=tmp_path / "cache",
    )

    loaded = FAISS.load_local(
        str(out_path),
        fake,
        allow_dangerous_deserialization=True,
    )
    docs = loaded.similarity_search("test query", k=1)
    assert len(docs) > 0, "no docs retrieved from loaded index"
    assert docs[0].metadata.get("title"), "title missing in loaded metadata"
    assert docs[0].metadata.get("source", "").startswith("http"), \
        "source URL missing in loaded metadata"
