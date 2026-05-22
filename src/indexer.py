"""Indexer: 청킹 + 임베딩 + FAISS 저장 (Task 04는 청킹까지)."""
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.parser import NewsArticle

# ADR 002: 청킹 전략 결정값
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
SEPARATORS = ["\n\n", "\n", "다. ", ". ", " ", ""]


def chunk_articles(articles: list[NewsArticle]) -> list[Document]:
    """NewsArticle 리스트를 LangChain Document(청크) 리스트로 변환.

    metadata 보존: title / source / published / keywords / article_idx
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=SEPARATORS,
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


if __name__ == "__main__":
    from pathlib import Path
    from src.parser import load_all

    articles = load_all(Path("data"))
    chunks = chunk_articles(articles)

    print(f"✅ Total chunks: {len(chunks)} (from {len(articles)} articles)")
    print(f"   Average chunks/article: {len(chunks) / len(articles):.1f}")
    print(f"   Average chars/chunk:    {sum(len(c.page_content) for c in chunks) // len(chunks)}")
    print()
    print("Sample (first 3 chunks of first article):")
    first_chunks = [c for c in chunks if c.metadata["article_idx"] == 2]
    for i, c in enumerate(first_chunks, 1):
        print(f"\n--- Chunk {i} ({len(c.page_content)} chars) ---")
        print(f"  title: {c.metadata['title'][:60]}")
        print(f"  text:  {c.page_content}")
