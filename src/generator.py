"""Generation: 검색된 청크 + 질문 → LLM 답변 (출처 인용, 환각 방지).

ADR 006 참고.

설계 핵심:
- get_llm(provider): LLM 추상화 (embedder의 get_embedder 미러)
- generate(query, hits): 청크 리스트 → 답변 (search와 분리, 테스트 용이)
- answer(query): search + generate 전체 파이프라인 → AnswerResult

provider 네임스페이스 주의 (서로 다름):
- embed_provider: 검색용 임베더 (openai-small / openai-large / gemini)
- llm_provider:   생성용 LLM     (openai / gemini)
→ 임베더 3 × LLM 2 = 6조합 자유 비교 가능 (Task 11).
"""
from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from src.search import DEFAULT_K, SearchHit, search

# (model_id, price_per_1M_input_USD, price_per_1M_output_USD) — Task 11 비용 계산용
LLM_MODELS: dict[str, tuple[str, float, float]] = {
    "openai": ("gpt-4o-mini", 0.15, 0.60),
    "gemini": ("gemini-2.0-flash", 0.0, 0.0),  # free tier
}

DEFAULT_LLM_PROVIDER = "openai"
DEFAULT_EMBED_PROVIDER = "openai-small"
# 0 = 결정적. 같은 질문 → 같은 답 (Task 11 공정 비교 + 환각 억제).
# fluency용 상향(0.2~0.3)은 Task 11 이후 실측 실험으로 결정 (ADR 006).
DEFAULT_TEMPERATURE = 0.0

# 근거 부족 시 정확히 이 문장만 출력하도록 프롬프트로 강제 (거부율 측정 기준)
NO_ANSWER = "제공된 뉴스 데이터에서 관련 정보를 찾지 못했습니다."

SYSTEM_PROMPT = """당신은 한국어 AI 뉴스 검색 어시스턴트입니다. 아래 [참고 자료]에 주어진 뉴스 기사 발췌문만 근거로 답변하세요.

규칙:
1. [참고 자료]에 있는 내용만 사용하세요. 배경지식이나 추측은 절대 사용하지 마세요.
2. [참고 자료]가 질문의 주제를 다루고 있으면, 그 안에 담긴 사실로 답하세요. 질문의 주제 자체가 [참고 자료]에 없거나 무관할 때만 다른 어떤 말도 하지 말고 정확히 다음 문장만 답하세요: "{no_answer}" (추측·창작은 아래 규칙 3에서 금지합니다)
3. 기사에 없는 해석·추론·일반화를 하지 마세요. 여러 기사를 종합해 요약하는 것은 괜찮지만, 기사에 명시되지 않은 새로운 결론은 만들지 마세요.
4. 질문에 부정 표현("X가 아닌", "제외", "말고" 등)이 포함된 경우, [참고 자료]에 해당 조건이 명시적으로 드러난 경우에만 답하세요. 조건을 판단할 근거가 부족하면 "{no_answer}"를 출력하세요.
5. [참고 자료]는 검색 시스템이 판단한 관련성 순으로 정렬되어 있습니다. 단, 순위가 높다고 해서 질문에 대한 정답 근거임을 보장하지는 않습니다.

답변 형식:
- 각 문장은 반드시 하나 이상의 출처 인용으로 끝나야 합니다.
- 각 문장 끝에 근거 자료의 번호를 [1], [2] 형식으로 인용하세요. 번호는 위 [참고 자료]의 번호와 일치해야 합니다.
- 여러 자료가 근거면 [1][3]처럼 함께 표기하세요.
- 출처를 댈 수 없는 문장은 출력하지 마세요.

한국어로 답하세요."""

HUMAN_PROMPT = """[참고 자료]
{context}

질문: {question}"""


@dataclass
class AnswerResult:
    """답변 1건 + 추적 정보. Task 09 로깅 / Task 11 평가에서 직렬화·확장."""
    query: str
    answer: str
    hits: list[SearchHit]
    llm_provider: str
    embed_provider: str
    # Task 11에서 채울 필드 (지금은 골격만)
    latency_s: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None

    @property
    def is_refusal(self) -> bool:
        """답변이 '근거 없음' 거부인지 (거부율 측정용)."""
        return self.answer.strip() == NO_ANSWER


def get_llm(
    provider: str = DEFAULT_LLM_PROVIDER,
    temperature: float = DEFAULT_TEMPERATURE,
) -> BaseChatModel:
    """Provider 이름으로 LangChain ChatModel 반환. (.env에서 API 키 자동 로드)"""
    if provider not in LLM_MODELS:
        raise ValueError(
            f"Unknown LLM provider: {provider!r}. Available: {list(LLM_MODELS)}"
        )
    model_id = LLM_MODELS[provider][0]

    if provider == "openai":
        return ChatOpenAI(model=model_id, temperature=temperature)
    if provider == "gemini":
        return ChatGoogleGenerativeAI(model=model_id, temperature=temperature)

    raise ValueError(f"No factory branch for {provider!r}")  # safety net


def format_context(hits: list[SearchHit]) -> str:
    """SearchHit 리스트 → 프롬프트용 텍스트. Rank-only (순위 번호만, raw score 미포함)."""
    blocks = []
    for i, h in enumerate(hits, 1):
        blocks.append(
            f"[{i}] 제목: {h.title}\n"
            f"    출처: {h.source}\n"
            f"    내용: {h.text}"
        )
    return "\n\n".join(blocks)


def _build_chain(llm: BaseChatModel):
    """LCEL 체인: prompt → llm → str. (Task 11 batch/stream 대비)"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", HUMAN_PROMPT),
    ]).partial(no_answer=NO_ANSWER)
    return prompt | llm | StrOutputParser()


def generate(
    query: str,
    hits: list[SearchHit],
    provider: str = DEFAULT_LLM_PROVIDER,
    temperature: float = DEFAULT_TEMPERATURE,
    llm: BaseChatModel | None = None,
) -> str:
    """청크(hits) + 질문 → LLM 답변 문자열. search와 분리되어 단위 테스트 용이.

    hits가 비어있으면 LLM 호출 없이 즉시 NO_ANSWER 반환.
    llm: DI — 테스트 시 Fake LLM 주입.
    """
    if not hits:
        return NO_ANSWER
    if llm is None:
        llm = get_llm(provider, temperature)
    chain = _build_chain(llm)
    return chain.invoke({"context": format_context(hits), "question": query})


def answer(
    query: str,
    llm_provider: str = DEFAULT_LLM_PROVIDER,
    embed_provider: str = DEFAULT_EMBED_PROVIDER,
    k: int = DEFAULT_K,
    temperature: float = DEFAULT_TEMPERATURE,
    llm: BaseChatModel | None = None,
    **search_kwargs,
) -> AnswerResult:
    """전체 파이프라인: 검색 → 생성 → AnswerResult.

    llm_provider:   생성 LLM (openai / gemini)
    embed_provider: 검색 임베더 (openai-small / openai-large / gemini)
    → 둘을 따로 줘서 6조합(임베더3×LLM2) 비교 가능.
    """
    hits = search(query, provider=embed_provider, k=k, **search_kwargs)
    response = generate(query, hits, provider=llm_provider,
                        temperature=temperature, llm=llm)
    return AnswerResult(
        query=query,
        answer=response,
        hits=hits,
        llm_provider=llm_provider,
        embed_provider=embed_provider,
    )


if __name__ == "__main__":
    """CLI:
      python -m src.generator "질문"
      python -m src.generator "질문" --llm gemini --embed gemini --k 6
    """
    import sys

    from dotenv import load_dotenv

    load_dotenv()

    args = sys.argv[1:]
    if not args:
        print('Usage: python -m src.generator "질문" '
              '[--llm openai|gemini] [--embed openai-small|openai-large|gemini] [--k N]')
        sys.exit(1)

    query = args[0]
    llm_provider = DEFAULT_LLM_PROVIDER
    embed_provider = DEFAULT_EMBED_PROVIDER
    k = DEFAULT_K
    if "--llm" in args:
        llm_provider = args[args.index("--llm") + 1]
    if "--embed" in args:
        embed_provider = args[args.index("--embed") + 1]
    if "--k" in args:
        k = int(args[args.index("--k") + 1])

    print(f"🤖 query=    {query!r}")
    print(f"   llm=      {llm_provider}")
    print(f"   embed=    {embed_provider}")
    print(f"   k=        {k}")
    print()

    result = answer(query, llm_provider=llm_provider,
                    embed_provider=embed_provider, k=k)
    print("─" * 70)
    print(result.answer)
    print("─" * 70)
    print(f"\n{'🚫 거부됨' if result.is_refusal else '✅ 답변함'} "
          f"| 근거 청크 {len(result.hits)}개:")
    for i, h in enumerate(result.hits, 1):
        print(f"  [{i}] {h.title[:60]}  ({h.source})")
