"""CLI entrypoint.

  python main.py build [--provider openai-small] [--all]   # 인덱싱
  python main.py chat  [--llm openai] [--embed openai-small] [--k 4]   # 대화형 질의
"""
import argparse
from pathlib import Path

from dotenv import load_dotenv

DATA_DIR = Path("data")


def cmd_build(args):
    from src.embedder import EMBEDDING_MODELS
    from src.indexer import build_index
    from src.parser import load_all

    articles = load_all(DATA_DIR)
    providers = list(EMBEDDING_MODELS) if args.all else [args.provider]
    print(f"📰 {len(articles)}개 기사 로드. 빌드할 provider: {providers}\n")
    for p in providers:
        print(f"📦 Building index for {p}...")
        out = build_index(articles, provider=p)
        print(f"✅ Saved to {out}\n")


def cmd_chat(args):
    from src.generator import answer
    from src.logger import log_interaction

    print(f"💬 AI 뉴스 챗봇  (llm={args.llm}, embed={args.embed}, k={args.k})")
    print("   질문을 입력하세요. 종료: exit / quit / 빈 입력\n")
    while True:
        try:
            query = input("질문> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료합니다.")
            break
        if not query or query.lower() in ("exit", "quit"):
            print("종료합니다.")
            break

        result = answer(query, llm_provider=args.llm,
                        embed_provider=args.embed, k=args.k)
        print("\n" + "─" * 70)
        print(result.answer)
        print("─" * 70)
        if not result.is_refusal:
            print("📎 출처:")
            for i, h in enumerate(result.hits, 1):
                print(f"  [{i}] {h.title[:60]}  ({h.source})")
        log_interaction(result)
        print()


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="AI 뉴스 RAG CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    pb = sub.add_parser("build", help="인덱스 빌드")
    pb.add_argument("--provider", default="openai-small",
                    help="임베더 (openai-small/openai-large/gemini)")
    pb.add_argument("--all", action="store_true", help="모든 provider 빌드")
    pb.set_defaults(func=cmd_build)

    pc = sub.add_parser("chat", help="대화형 질의")
    pc.add_argument("--llm", default="openai", help="LLM (openai/gemini)")
    pc.add_argument("--embed", default="openai-small",
                    help="임베더 (openai-small/openai-large/gemini)")
    pc.add_argument("--k", type=int, default=4, help="검색 청크 수")
    pc.set_defaults(func=cmd_chat)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
