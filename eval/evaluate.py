"""Task 11 평가 러너. Golden Dataset × 2조합 실행 → 자동 지표 + 수동 채점 시트.

비교 설계: 임베더 고정(openai-small) + temp 고정(0) → LLM만 gpt-4o-mini vs gemini-2.0-flash.
변수 1개(LLM)라 "같은 검색결과 주고 누가 더 잘 답하나" 순수 비교.

자동 지표: latency / tokens / cost / recall@k / 거부율 / citation coverage
수동 채점: 정확도(1-5) / Noise(0-4) / Citation 일치 — scoring_sheet.md에서 채움

실행: python -m eval.evaluate
출력: eval/results/results.jsonl + eval/results/scoring_sheet.md (gitignored)
"""
import json
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate

from src.generator import (
    HUMAN_PROMPT,
    LLM_MODELS,
    NO_ANSWER,
    SYSTEM_PROMPT,
    format_context,
    get_llm,
)
from src.search import DEFAULT_K, search

GOLDEN_PATH = Path("eval/golden_dataset.json")
OUT_DIR = Path("eval/results")
TEMPERATURE = 0.0  # 공정 비교 위해 고정 (ADR 006)

# (embed_provider, llm_provider, 표시명)
COMBOS = [
    ("openai-small", "openai", "ChatGPT (gpt-4o-mini)"),
    ("openai-small", "gemini", "Gemini (gemini-2.5-flash)"),
]

_IDXNO_RE = re.compile(r"idxno=(\d+)")
_CITE_RE = re.compile(r"\[\d+\]")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def extract_idxno(url: str) -> int | None:
    m = _IDXNO_RE.search(url or "")
    return int(m.group(1)) if m else None


def recall_at_k(hits, expected_ids: list[int]) -> float | None:
    """expected 기사 중 top-k에 들어온 비율. 환각테스트(expected=[])는 None."""
    if not expected_ids:
        return None
    retrieved = {extract_idxno(h.source) for h in hits}
    found = sum(1 for e in expected_ids if e in retrieved)
    return round(found / len(expected_ids), 3)


def citation_coverage(answer: str) -> float | None:
    """문장 중 [N] 인용 달린 비율. 거부 답변은 None."""
    if answer.strip() == NO_ANSWER:
        return None
    sentences = [s for s in _SENT_SPLIT.split(answer.strip()) if s.strip()]
    if not sentences:
        return None
    cited = sum(1 for s in sentences if _CITE_RE.search(s))
    return round(cited / len(sentences), 3)


def cost_usd(usage: dict, llm_provider: str) -> float | None:
    if not usage:
        return None
    _, in_price, out_price = LLM_MODELS[llm_provider]
    it = usage.get("input_tokens", 0) or 0
    ot = usage.get("output_tokens", 0) or 0
    return round(it / 1_000_000 * in_price + ot / 1_000_000 * out_price, 6)


def run_one(q: dict, embed_p: str, llm_p: str, prompt, k: int = DEFAULT_K) -> dict:
    query = q["query"]
    llm = get_llm(llm_p, temperature=TEMPERATURE)
    chain = prompt | llm  # StrOutputParser 없이 → AIMessage(usage 포함) 확보

    t0 = time.time()
    hits = search(query, provider=embed_p, k=k)
    msg = chain.invoke({"context": format_context(hits), "question": query})
    latency = round(time.time() - t0, 3)

    answer = msg.content
    usage = getattr(msg, "usage_metadata", None) or {}
    return {
        "qid": q["id"],
        "query": query,
        "type": q["type"],
        "embed_provider": embed_p,
        "llm_provider": llm_p,
        "answer": answer,
        "retrieved": [
            {"idxno": extract_idxno(h.source), "title": h.title, "score": round(h.score, 4)}
            for h in hits
        ],
        "latency_s": latency,
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "cost_usd": cost_usd(usage, llm_p),
        "is_refusal": answer.strip() == NO_ANSWER,
        "recall_at_k": recall_at_k(hits, q["expected_article_ids"]),
        "citation_coverage": citation_coverage(answer),
        "expect_refusal": q["expect_refusal"],
        "expected_article_ids": q["expected_article_ids"],
        "failure_labels": q["failure_labels"],
    }


def _avg(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 3) if vals else None


def summarize(records: list[dict]) -> dict:
    """조합별 자동 지표 집계."""
    summary = {}
    for embed_p, llm_p, label in COMBOS:
        rs = [r for r in records if r["embed_provider"] == embed_p and r["llm_provider"] == llm_p]
        # 거부 정확도: expect_refusal과 실제 is_refusal 일치 비율
        refusal_correct = sum(1 for r in rs if r["is_refusal"] == r["expect_refusal"])
        summary[label] = {
            "n": len(rs),
            "avg_latency_s": _avg([r["latency_s"] for r in rs]),
            "total_cost_usd": round(sum(r["cost_usd"] or 0 for r in rs), 6),
            "avg_output_tokens": _avg([r["output_tokens"] for r in rs]),
            "refusal_rate": round(sum(r["is_refusal"] for r in rs) / len(rs), 3),
            "refusal_accuracy": round(refusal_correct / len(rs), 3),
            "avg_recall_at_k": _avg([r["recall_at_k"] for r in rs]),
            "avg_citation_coverage": _avg([r["citation_coverage"] for r in rs]),
        }
    return summary


def write_scoring_sheet(records: list[dict], path: Path):
    """문항별로 두 조합 답변 나란히 + 수동 채점 빈칸."""
    by_q: dict[str, list[dict]] = {}
    for r in records:
        by_q.setdefault(r["qid"], []).append(r)

    lines = ["# Task 11 수동 채점 시트", "",
             "각 답변에 대해 채점: 정확도(1-5) / Noise(top-4 중 무관 청크 수 0-4) / Citation일치(Y/N).",
             "환각테스트(q9~q11)는 '거부했나'만 보면 됨.", ""]
    for qid in sorted(by_q, key=lambda x: int(x[1:])):
        recs = by_q[qid]
        q0 = recs[0]
        lines += [f"## {qid} — {q0['query']}  ({q0['type']})",
                  f"기대 기사: {q0['expected_article_ids']} | 기대 거부: {q0['expect_refusal']}", ""]
        for r in recs:
            label = next(c[2] for c in COMBOS
                         if c[0] == r["embed_provider"] and c[1] == r["llm_provider"])
            auto = (f"recall={r['recall_at_k']} | refusal={r['is_refusal']} "
                    f"| cite_cov={r['citation_coverage']} | latency={r['latency_s']}s "
                    f"| out_tok={r['output_tokens']} | cost=${r['cost_usd']}")
            chunks = "\n".join(f"      - [{c['idxno']}] {c['title'][:50]} (score={c['score']})"
                               for c in r["retrieved"])
            lines += [f"### {label}",
                      f"**답변:** {r['answer']}", "",
                      f"검색된 기사:\n{chunks}", "",
                      f"자동: {auto}",
                      "수동 채점 → 정확도(1-5): ___   Noise(0-4): ___   Citation일치(Y/N): ___", ""]
        lines.append("---")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    load_dotenv()
    data = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    questions = data["questions"]
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", HUMAN_PROMPT),
    ]).partial(no_answer=NO_ANSWER)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 인덱스 warmup (첫 검색의 디스크 로드를 latency에서 제외 → 공정 비교)
    print("🔥 warming up index...")
    search("warmup", provider="openai-small", k=1)

    records = []
    print(f"▶ {len(questions)}문항 × {len(COMBOS)}조합 = {len(questions)*len(COMBOS)}회 실행\n")
    for q in questions:
        for embed_p, llm_p, label in COMBOS:
            rec = run_one(q, embed_p, llm_p, prompt)
            records.append(rec)
            mark = "🚫" if rec["is_refusal"] else "✅"
            print(f"  {mark} {q['id']:4s} {label:28s} "
                  f"recall={rec['recall_at_k']} cite={rec['citation_coverage']} "
                  f"{rec['latency_s']}s ${rec['cost_usd']}")

    # 결과 저장
    results_path = OUT_DIR / "results.jsonl"
    with results_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    sheet_path = OUT_DIR / "scoring_sheet.md"
    write_scoring_sheet(records, sheet_path)

    # 요약표
    summary = summarize(records)
    print("\n" + "=" * 70)
    print("📊 자동 지표 요약")
    print("=" * 70)
    for label, s in summary.items():
        print(f"\n[{label}]")
        for k, v in s.items():
            print(f"  {k:24s}: {v}")

    print(f"\n✅ 저장: {results_path}")
    print(f"✅ 채점 시트: {sheet_path}  ← 이거 열어서 수동 채점")


if __name__ == "__main__":
    main()
