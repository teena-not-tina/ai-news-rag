"""E2E 스모크 테스트 — 전체 파이프라인 연결 검증 (Fake 모델, API 호출 X).

검증 목적: 부품들이 서로 맞물려 안 깨지고 흐르나 (wiring).
  - 실제 데이터(기사 md)는 사용. 모델(임베딩/LLM)만 Fake.
  - 실제 출력 품질(정확도/노이즈/인용)은 Task 11에서 진짜 6조합으로 평가.

체인: load_all(실제 기사) → build_index(Fake임베딩) → search
      → generate(Fake LLM) → answer → log_interaction
"""
import json
from pathlib import Path

import pytest
from langchain_core.embeddings import FakeEmbeddings
from langchain_core.language_models.fake_chat_models import FakeListChatModel

import src.search as search_mod
from src.generator import AnswerResult, answer, generate
from src.indexer import build_index
from src.logger import log_interaction
from src.parser import load_all
from src.search import search

DATA_DIR = Path(__file__).parent.parent / "data"
ARTICLE_LIMIT = 5
FAKE_EMBED_DIM = 8


@pytest.fixture(autouse=True)
def _clear_store_cache():
    """모듈 캐시 초기화 — tmp_path 인덱스 격리."""
    search_mod._STORE_CACHE.clear()
    yield
    search_mod._STORE_CACHE.clear()


def test_e2e_pipeline_smoke(tmp_path):
    """기사 → 인덱싱 → 검색 → 생성 → 로깅 전체가 안 깨지고 연결되나."""
    # 1. 실제 기사 로드 + Fake 임베딩으로 인덱싱
    articles = load_all(DATA_DIR)[:ARTICLE_LIMIT]
    assert len(articles) > 0, "기사 로드 실패"
    fake_emb = FakeEmbeddings(size=FAKE_EMBED_DIM)
    build_index(articles, provider="test", embedder=fake_emb,
                store_dir=tmp_path, cache_dir=tmp_path / "cache")

    # 2. 검색 — retrieval assertion (메타데이터 보존)
    hits = search("AI 뉴스", provider="test", k=3,
                  embedder=fake_emb, store_dir=tmp_path)
    assert len(hits) > 0, "검색 결과 0건"
    assert hits[0].title, "title 메타데이터 누락"
    assert hits[0].source.startswith("http"), "source URL 누락"

    # 3. 생성 — Fake LLM (체인 prompt|llm|parser 연결 확인)
    fake_llm = FakeListChatModel(responses=["테스트 답변입니다[1]."])
    out = generate("AI 뉴스", hits, llm=fake_llm)
    assert isinstance(out, str) and out, "생성 답변 없음"

    # 4. 전체 파이프라인 answer() → AnswerResult
    result = answer("AI 뉴스", embed_provider="test", llm=fake_llm,
                    embedder=fake_emb, store_dir=tmp_path, k=3)
    assert isinstance(result, AnswerResult)
    assert result.answer, "answer 비어있음"
    assert len(result.hits) > 0, "answer hits 0건"

    # 5. 로깅 — jsonl 1줄 쓰이고 다시 읽히나
    log_path = tmp_path / "logs" / "e2e.jsonl"
    log_interaction(result, path=log_path)
    assert log_path.exists(), "로그 파일 미생성"
    rec = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert rec["query"] == "AI 뉴스"
    assert len(rec["retrieved_chunks"]) > 0
