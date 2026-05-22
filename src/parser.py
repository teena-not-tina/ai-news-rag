"""Markdown parser: YAML frontmatter(title/source/published) + body + 키워드 추출."""
import re
from dataclasses import dataclass
from pathlib import Path

import frontmatter


@dataclass
class NewsArticle:
    title: str
    source: str          # 원문 URL
    published: str       # 발행일 (YYYY-MM-DD)
    keywords: list[str]  # 본문 끝 [#태그](url) 추출 결과 (중복 제거)
    body: str            # 본문 (이미지/footer 제거됨)


_IMAGE_MD = re.compile(r"!\[[^\]]*\]\([^)]*\)")  # ![alt](url) 형태
_KEYWORD_MD = re.compile(r"\[#([^\]]+)\]")       # [#키워드](url) 형태

# 본문이 끝나고 시작되는 footer 마커들. 가장 먼저 등장하는 곳에서 cut.
_FOOTER_PATTERNS = [
    re.compile(r"^[가-힣]+\s+기자\s+[\w.+-]+@[\w.+-]+\.\w+\s*$"),  # "장세민 기자 semim99@aitimes.com"
    re.compile(r"^관련기사\s*$"),
    re.compile(r"^키워드\s*$"),
    re.compile(r"^저작권자"),
]


def _strip_footer(text: str) -> str:
    """본문 끝의 byline / 관련기사 / 키워드 / 저작권자 섹션 제거.

    여러 마커 중 가장 먼저 등장하는 위치에서 cut.
    """
    lines = text.split("\n")
    cut_idx = len(lines)
    for i, line in enumerate(lines):
        if any(p.match(line) for p in _FOOTER_PATTERNS):
            cut_idx = i
            break
    return "\n".join(lines[:cut_idx]).rstrip()


def _clean_body(text: str) -> str:
    """이미지 마크다운 제거 + footer 제거 + 연속 빈 줄 압축."""
    text = _IMAGE_MD.sub("", text)
    text = _strip_footer(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_keywords(text: str) -> list[str]:
    """본문(footer 포함)에서 [#키워드](url) 패턴 추출 (중복 제거, 등장 순서 유지)."""
    seen: set[str] = set()
    result: list[str] = []
    for kw in _KEYWORD_MD.findall(text):
        if kw not in seen:
            seen.add(kw)
            result.append(kw)
    return result


def parse_file(path: Path) -> NewsArticle:
    """단일 .md 파일을 NewsArticle로 변환."""
    post = frontmatter.load(path)
    meta = post.metadata
    return NewsArticle(
        title=str(meta.get("title", "")),
        source=str(meta.get("source", "")),
        published=str(meta.get("published", "")),
        keywords=_extract_keywords(post.content),  # 원본에서 추출 (footer 포함)
        body=_clean_body(post.content),            # footer 제거된 본문
    )


def load_all(data_dir: Path) -> list[NewsArticle]:
    """data_dir 안의 모든 .md 파일을 NewsArticle 리스트로."""
    return [parse_file(p) for p in sorted(data_dir.glob("*.md"))]


if __name__ == "__main__":
    import sys
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data")
    articles = load_all(data_dir)
    print(f"✅ Parsed {len(articles)} articles\n")
    a = articles[2]
    print("Sample (first article):")
    print(f"  title:      {a.title}")
    print(f"  source:     {a.source}")
    print(f"  published:  {a.published}")
    print(f"  keywords:   {a.keywords}")
    print(f"  body[-300:]: ...{a.body[-300:]}")
    print(f"  body length: {len(a.body)} chars")
