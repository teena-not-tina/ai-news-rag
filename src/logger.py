"""Retrieval-hit 로깅: AnswerResult → jsonl append. (Task 09)

운영 디버깅 + Task 11 평가 데이터 자동 축적.
DB 없이 file append (jsonl). 위치: data/logs/ (gitignored).

DB 이전 고려: 각 레코드에 id(uuid, 미래 PK) + schema_version 포함.
단 nested retrieved_chunks는 그대로 — 관계형 DB 갈 때 정규화 (v2-backlog).
"""
import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from src.generator import AnswerResult

DEFAULT_LOG_PATH = Path("data/logs/interactions.jsonl")
SCHEMA_VERSION = 1

_CITATION_RE = re.compile(r"\[(\d+)\]")


def extract_citations(answer: str) -> list[int]:
    """답변에서 [N] 인용 번호 추출 (중복 제거, 등장 순서 유지)."""
    seen: set[int] = set()
    out: list[int] = []
    for m in _CITATION_RE.findall(answer):
        n = int(m)
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def to_record(result: AnswerResult) -> dict:
    """AnswerResult → 로그 dict (jsonl 직렬화용)."""
    return {
        "id": str(uuid.uuid4()),         # 미래 DB primary key
        "schema_version": SCHEMA_VERSION,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "query": result.query,
        "llm_provider": result.llm_provider,
        "embed_provider": result.embed_provider,
        "k": len(result.hits),
        "retrieved_chunks": [
            {"title": h.title, "source": h.source, "score": round(h.score, 4)}
            for h in result.hits
        ],
        "answer": result.answer,
        "citations": extract_citations(result.answer),
        "is_refusal": result.is_refusal,
        # Task 11에서 채울 필드 (있으면 기록)
        "latency_s": result.latency_s,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "cost_usd": result.cost_usd,
    }


def log_interaction(result: AnswerResult, path: Path = DEFAULT_LOG_PATH) -> None:
    """AnswerResult를 jsonl 한 줄로 append."""
    path.parent.mkdir(parents=True, exist_ok=True)
    record = to_record(result)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
