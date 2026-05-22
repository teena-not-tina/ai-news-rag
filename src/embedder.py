"""Embedder factory: get_embedder(provider) → LangChain Embeddings instance.

지원 provider:
- openai-small : OpenAI text-embedding-3-small  (1536-d, $0.02/1M tokens) — MVP 기본
- openai-large : OpenAI text-embedding-3-large  (3072-d, $0.13/1M tokens) — 가격 tier 비교
- gemini       : Google Gemini text-embedding-004 (768-d, free tier) — provider 비교

ADR 003 참고.
"""
from langchain_core.embeddings import Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings

# (model_id, dim, price_per_1M_tokens_USD)
EMBEDDING_MODELS: dict[str, tuple[str, int, float]] = {
    "openai-small": ("text-embedding-3-small", 1536, 0.02),
    "openai-large": ("text-embedding-3-large", 3072, 0.13),
    "gemini":       ("models/gemini-embedding-001", 3072, 0.0),
}


def get_embedder(provider: str = "openai-small") -> Embeddings:
    """Provider 이름으로 LangChain Embeddings 인스턴스 반환.

    환경변수에서 API 키 자동 로드 (.env).
    """
    if provider not in EMBEDDING_MODELS:
        raise ValueError(
            f"Unknown embedding provider: {provider!r}. "
            f"Available: {list(EMBEDDING_MODELS)}"
        )
    model_id = EMBEDDING_MODELS[provider][0]

    if provider.startswith("openai"):
        return OpenAIEmbeddings(model=model_id)
    if provider == "gemini":
        return GoogleGenerativeAIEmbeddings(model=model_id)

    raise ValueError(f"No factory branch for {provider!r}")  # safety net


def estimate_cost(num_tokens: int, provider: str) -> float:
    """주어진 토큰 수에 대한 USD 비용 추정."""
    if provider not in EMBEDDING_MODELS:
        raise ValueError(f"Unknown provider: {provider!r}")
    price = EMBEDDING_MODELS[provider][2]
    return num_tokens / 1_000_000 * price


if __name__ == "__main__":
    """청크 통계 + 3개 provider 비용 추정 (실제 API 호출 X)."""
    from pathlib import Path

    from dotenv import load_dotenv

    from src.indexer import chunk_articles
    from src.parser import load_all

    load_dotenv()
    articles = load_all(Path("data"))
    chunks = chunk_articles(articles)

    total_chars = sum(len(c.page_content) for c in chunks)
    est_tokens = int(total_chars * 1.5)  # 한국어 대략 1글자 ≈ 1.5 토큰

    print(f"📊 데이터 통계")
    print(f"   기사 수:      {len(articles)}")
    print(f"   청크 수:      {len(chunks):,}")
    print(f"   총 글자 수:   {total_chars:,}")
    print(f"   추정 토큰 수: {est_tokens:,} (한국어 1.5배 계수)")
    print()
    print(f"💰 인덱싱 비용 추정 (provider별 1회 실행)")
    print(f"   {'provider':15s} {'dim':>5s}  {'price':>10s}  {'cost':>10s}  {'KRW':>8s}")
    total_usd = 0.0
    for provider, (model, dim, price) in EMBEDDING_MODELS.items():
        cost = estimate_cost(est_tokens, provider)
        krw = cost * 1380  # 대략 환율
        total_usd += cost
        print(f"   {provider:15s} {dim:>5d}  ${price:>5.2f}/1M  ${cost:>8.4f}  {krw:>6.0f}원")
    print(f"   {'─' * 60}")
    print(f"   {'3종 합산':15s} {'':>5s}  {'':>10s}  ${total_usd:>8.4f}  {total_usd*1380:>6.0f}원")
