"""Retriever: FAISS top-k similarity search (with L2 score) → SearchHit 리스트.

ADR 005 참고.

호출 예:
    hits = search("OpenAI o3 벤치마크?", provider="openai-small", k=4)
    for h in hits:
        print(h.score, h.title, h.source)
"""
from dataclasses import dataclass
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from src.embedder import get_embedder

DEFAULT_STORE_DIR = Path("data/vector_store")
DEFAULT_K = 4

# 모듈 레벨 캐시: 같은 provider 반복 호출 시 디스크 I/O 0
_STORE_CACHE: dict[str, FAISS] = {}


@dataclass
class SearchHit:
    """검색 결과 1건. text + 메타데이터 + L2 distance."""
    text: str
    title: str
    source: str       # 원문 URL
    published: str
    score: float      # L2 distance (작을수록 유사)

    @classmethod
    def from_document(cls, doc: Document, score: float) -> "SearchHit":
        m = doc.metadata
        return cls(
            text=doc.page_content,
            title=m.get("title", ""),
            source=m.get("source", ""),
            published=m.get("published", ""),
            score=float(score),
        )


def _load_store(
    provider: str,
    embedder: Embeddings,
    store_dir: Path,
    cache_key: str,
) -> FAISS:
    """캐시 우선 조회. 없으면 디스크에서 load 후 캐시.

    cache_key: 호출자가 캐시 키를 직접 지정 (테스트에서 충돌 방지용).
               기본 사용 시 provider 그대로 키로 씀.
    """
    if cache_key in _STORE_CACHE:
        return _STORE_CACHE[cache_key]

    namespace = provider.replace("-", "_")
    path = store_dir / namespace
    if not path.exists():
        raise FileNotFoundError(
            f"Vector store not found at {path}. "
            f"Run `python -m src.indexer build --provider {provider}` first."
        )

    store = FAISS.load_local(
        str(path),
        embedder,
        allow_dangerous_deserialization=True,  # ⚠️ 자체 빌드 인덱스만 로드
    )
    _STORE_CACHE[cache_key] = store
    return store


def search(
    query: str,
    provider: str = "openai-small",
    k: int = DEFAULT_K,
    embedder: Embeddings | None = None,
    store_dir: Path = DEFAULT_STORE_DIR,
) -> list[SearchHit]:
    """질문 → top-k SearchHit (L2 score 작은 순).

    파라미터:
        query: 사용자 질문
        provider: embedder/인덱스 이름. embedder=None일 때 get_embedder(provider) 사용.
        k: top-k. per-query 파라미터 (호출자가 매번 override 가능).
        embedder: DI — 테스트 시 FakeEmbeddings 주입.
        store_dir: 인덱스 루트. 기본 data/vector_store.

    반환: list[SearchHit] — k개. (인덱스에 청크가 k개 미만이면 그 수만큼)
    """
    if embedder is None:
        embedder = get_embedder(provider)

    # 캐시 키: 기본은 provider, embedder 주입 시 id(embedder) 포함하여 격리
    cache_key = provider if embedder is None else f"{provider}:{id(embedder)}"
    store = _load_store(provider, embedder, store_dir, cache_key)

    raw = store.similarity_search_with_score(query, k=k)
    return [SearchHit.from_document(doc, score) for doc, score in raw]


if __name__ == "__main__":
    """CLI:
      python -m src.search "질문"
      python -m src.search "질문" --provider gemini --k 6
    """
    import sys

    from dotenv import load_dotenv

    load_dotenv()

    args = sys.argv[1:]
    if not args:
        print('Usage: python -m src.search "질문" [--provider X] [--k N]')
        sys.exit(1)

    query = args[0]
    provider = "openai-small"
    k = DEFAULT_K
    if "--provider" in args:
        provider = args[args.index("--provider") + 1]
    if "--k" in args:
        k = int(args[args.index("--k") + 1])

    print(f"🔍 query=    {query!r}")
    print(f"   provider= {provider}")
    print(f"   k=        {k}")
    print()

    hits = search(query, provider=provider, k=k)
    for i, h in enumerate(hits, 1):
        print(f"--- #{i}  score={h.score:.4f} ---")
        print(f"  title:     {h.title[:80]}")
        print(f"  source:    {h.source}")
        print(f"  published: {h.published}")
        print(f"  text:      {h.text}")
        print()
