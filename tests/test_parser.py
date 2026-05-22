"""Tests for src.parser"""
from pathlib import Path

from src.parser import load_all, parse_file

DATA_DIR = Path(__file__).parent.parent / "data"


def test_parser_extracts_metadata():
    """첫 md 파일에서 title/source/published/keywords/body가 정상 추출되는지."""
    first_md = sorted(DATA_DIR.glob("*.md"))[0]
    article = parse_file(first_md)

    assert article.title, "title is empty"
    assert article.source.startswith("http"), f"source not a URL: {article.source!r}"
    assert article.published, "published is empty"
    assert isinstance(article.keywords, list), "keywords is not a list"
    assert article.body, "body is empty"


def test_parser_handles_all_52_files():
    """52개 전부 에러 없이 파싱되고, 모두 title이 비어있지 않은지."""
    articles = load_all(DATA_DIR)

    assert len(articles) == 52, f"expected 52 articles, got {len(articles)}"
    for article in articles:
        assert article.title, f"empty title for source={article.source}"


def test_parser_strips_footer():
    """본문에 byline/관련기사/저작권자 같은 footer 노이즈가 남아있지 않아야."""
    articles = load_all(DATA_DIR)
    for a in articles:
        assert "관련기사" not in a.body, f"'관련기사' leaked into body: {a.source}"
        assert "저작권자" not in a.body, f"'저작권자' leaked into body: {a.source}"
        assert "다른기사 보기" not in a.body, f"'다른기사 보기' leaked: {a.source}"
