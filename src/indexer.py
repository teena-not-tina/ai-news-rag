"""Indexer: 청킹 + 임베딩(캐시) + FAISS 저장."""
from pathlib import Path

from langchain.embeddings import CacheBackedEmbeddings
from langchain.storage import LocalFileStore
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.embedder import get_embedder
from src.parser import NewsArticle

# ADR 002 default — caller가 override 가능
DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 50
DEFAULT_SEPARATORS = ["\n\n", "\n", "다. ", ". ", " ", ""]

# ADR 004 기본 경로
DEFAULT_STORE_DIR = Path("data/vector_store")
DEFAULT_CACHE_DIR = Path("data/embedding_cache")


def chunk_articles(
    articles: list[NewsArticle],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    separators: list[str] | None = None,
) -> list[Document]:
    """NewsArticle 리스트를 LangChain Document(청크) 리스트로 변환.

    metadata 보존: title / source / published / keywords / article_idx
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators or DEFAULT_SEPARATORS,
    )
    docs: list[Document] = []
    for idx, article in enumerate(articles):
        for chunk_text in splitter.split_text(article.body):
            docs.append(Document(
                page_content=chunk_text,
                metadata={
                    "title": article.title,
                    "source": article.source,
                    "published": article.published,
                    "keywords": ",".join(article.keywords),
                    "article_idx": idx,
                },
            ))
    return docs


def build_index(
    articles: list[NewsArticle],
    provider: str = "openai-small",
    embedder: Embeddings | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    separators: list[str] | None = None,
    store_dir: Path = DEFAULT_STORE_DIR,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> Path:
    """청킹 → 캐시 임베딩 → FAISS 저장.

    파라미터:
        provider: embedder 이름. embedder=None일 때 get_embedder(provider) 사용.
        embedder: 직접 Embeddings 인스턴스 주입 (테스트/대체용).
        store_dir / cache_dir: 저장 루트. provider별 하위 디렉토리 자동 생성.

    반환: 인덱스 저장 경로 (예: data/vector_store/openai_small/)
    """
    chunks = chunk_articles(articles, chunk_size, chunk_overlap, separators)

    if embedder is None:
        embedder = get_embedder(provider)

    namespace = provider.replace("-", "_")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached_embedder = CacheBackedEmbeddings.from_bytes_store(
        underlying_embeddings=embedder,
        document_embedding_cache=LocalFileStore(str(cache_dir)),
        namespace=namespace,
    )

    vector_store = FAISS.from_documents(chunks, cached_embedder)
    out_path = store_dir / namespace
    out_path.mkdir(parents=True, exist_ok=True)
    vector_store.save_local(str(out_path))

    return out_path


if __name__ == "__main__":
    """CLI:
      python -m src.indexer                 → 청킹 데모 (API 호출 X)
      python -m src.indexer build           → openai-small로 인덱스 빌드
      python -m src.indexer build --provider gemini
      python -m src.indexer build-all       → 3개 provider 모두 빌드
    """
    import sys

    from dotenv import load_dotenv

    from src.embedder import EMBEDDING_MODELS
    from src.parser import load_all

    load_dotenv()  # .env에서 OPENAI_API_KEY, GOOGLE_API_KEY 로드

    args = sys.argv[1:]
    articles = load_all(Path("data"))

    if args and args[0] == "build":
        provider = "openai-small"
        if "--provider" in args:
            provider = args[args.index("--provider") + 1]
        print(f"📦 Building index for provider={provider}...")
        out_path = build_index(articles, provider=provider)
        print(f"✅ Saved to {out_path}")

    elif args and args[0] == "build-all":
        for provider in EMBEDDING_MODELS:
            print(f"\n📦 Building index for provider={provider}...")
            out_path = build_index(articles, provider=provider)
            print(f"✅ Saved to {out_path}")

    else:
        # 기본: 청킹 데모 (API 호출 X)
        chunks = chunk_articles(articles)
        print(f"✅ Total chunks: {len(chunks)} (from {len(articles)} articles)")
        print(f"   Average chunks/article: {len(chunks) / len(articles):.1f}")
        print(f"   Average chars/chunk:    {sum(len(c.page_content) for c in chunks) // len(chunks)}")
        print()
        print("Sample (first 3 chunks of first article):")
        first_chunks = [c for c in chunks if c.metadata["article_idx"] == 0][:3]
        for i, c in enumerate(first_chunks, 1):
            print(f"\n--- Chunk {i} ({len(c.page_content)} chars) ---")
            print(f"  title: {c.metadata['title'][:60]}")
            print(f"  text:  {c.page_content[:180]}...")
