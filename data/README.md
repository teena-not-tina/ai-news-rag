# `data/` — 뉴스 데이터 폴더

이 폴더는 RAG가 인덱싱할 한국어 AI 뉴스 마크다운 파일을 보관합니다.

> ⚠️ **저작권**: `data/*.md`는 외부 뉴스 매체의 저작물입니다. 따라서 git에 커밋되지 않으며(`.gitignore`로 제외), 본인이 로컬에서 직접 옵시디언 등으로 수집해 넣어야 합니다.

## 폴더 구조

```
data/
├── *.md            # 뉴스 기사 (gitignored)
├── vector_store/   # FAISS 인덱스 (gitignored, indexer 실행 시 자동 생성)
└── README.md       # 이 파일
```

## 지원 포맷: AItimes 옵시디언 클립

현재 MVP 파서(`src/parser.py`)는 **AI타임스 (aitimes.com) 옵시디언 클립 포맷 전용**으로 구현됨.

기대하는 frontmatter 필드:

```yaml
---
title: "기사 제목"
source: "https://www.aitimes.com/news/articleView.html?idxno=..."
author:
  - "[[기자명]]"
published: 2026-05-20
created: 2026-05-22
description: "도입부"
tags:
  - "clippings"
---
```

본문 끝의 footer (byline / 관련기사 / 키워드 / 저작권자)는 파서가 자동 제거합니다.

## 다른 포털 지원

연합뉴스, 조선일보, 중앙일보 등 다른 포털의 마크다운 포맷은 현재 미지원.
v2 백로그에 **다중 뉴스 포털 파서 (Strategy Pattern)** 으로 등록됨 — `docs/decisions/v2-backlog.md` 참고.
