"""Tests for src.logger (파일 I/O, API 호출 X)."""
import json

from src.generator import AnswerResult
from src.logger import (
    SCHEMA_VERSION,
    extract_citations,
    log_interaction,
    to_record,
)
from src.search import SearchHit


def _result(answer="답변입니다[1][3]. 추가 문장[1].", n_hits=4):
    hits = [
        SearchHit(text="본문", title=f"제목{i}", source=f"https://e.com/{i}",
                  published="2026-05-21", score=0.1 * i)
        for i in range(1, n_hits + 1)
    ]
    return AnswerResult(query="질문", answer=answer, hits=hits,
                        llm_provider="openai", embed_provider="openai-small")


def test_extract_citations_dedup_ordered():
    """[N] 추출 — 중복 제거 + 등장 순서 유지."""
    assert extract_citations("문장[1][3]. 또[1]. 그리고[2].") == [1, 3, 2]


def test_extract_citations_empty():
    """인용 없으면 빈 리스트."""
    assert extract_citations("출처 없는 답변") == []


def test_to_record_shape():
    """레코드에 필수 필드 + DB 이전 고려 필드(id/schema_version)."""
    rec = to_record(_result())
    assert rec["query"] == "질문"
    assert rec["llm_provider"] == "openai"
    assert rec["embed_provider"] == "openai-small"
    assert rec["k"] == 4
    assert len(rec["retrieved_chunks"]) == 4
    assert rec["retrieved_chunks"][0]["title"] == "제목1"
    assert "source" in rec["retrieved_chunks"][0]
    assert "score" in rec["retrieved_chunks"][0]
    assert rec["citations"] == [1, 3]
    assert rec["is_refusal"] is False
    # DB 이전 고려 필드
    assert "id" in rec and len(rec["id"]) > 0
    assert rec["schema_version"] == SCHEMA_VERSION
    assert "timestamp" in rec


def test_to_record_unique_ids():
    """레코드마다 id가 고유 (미래 DB PK)."""
    assert to_record(_result())["id"] != to_record(_result())["id"]


def test_log_interaction_appends_jsonl(tmp_path):
    """여러 번 호출하면 jsonl에 줄 단위로 누적."""
    path = tmp_path / "logs" / "test.jsonl"
    log_interaction(_result(), path=path)
    log_interaction(_result(answer="두번째 답변[2]."), path=path)

    lines = path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["citations"] == [1, 3]
    assert json.loads(lines[1])["citations"] == [2]


def test_log_interaction_creates_parent_dir(tmp_path):
    """부모 디렉토리가 없어도 자동 생성."""
    path = tmp_path / "a" / "b" / "c.jsonl"
    log_interaction(_result(), path=path)
    assert path.exists()
