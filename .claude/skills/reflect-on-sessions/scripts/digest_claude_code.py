#!/usr/bin/env python3
"""Claude Code のセッショントランスクリプトをコンパクトなダイジェストに圧縮する。

プロジェクトの .jsonl トランスクリプトを読み、トークン効率の良いダイジェスト
（ユーザーのプロンプト、アシスタントの本文＋ツール呼び出し、エラー）を出力する。
`thinking` ブロックや巨大なツール出力といった大量のノイズは捨てる。このダイジェストを
`dream` スキルが読んで、セッション横断のパターンを探す。

使い方:
    digest_sessions.py [--project-dir DIR] [--limit N] [--max-chars C]

既定値:
    --project-dir : 現在の作業ディレクトリから導出（~/.claude/projects/<スラッシュをダッシュにしたcwd>）
    --limit       : 10（新しい順の直近セッション数）
    --max-chars   : 600（テキストフィールドごとの切り詰め文字数）

現在のセッション自身のトランスクリプトも含まれる。問題はないが、ダイジェストが
この reflect-on-sessions 実行そのものに言及しうる点に留意する。
"""
import argparse
import glob
import json
import os
import sys


def derive_project_dir() -> str:
    cwd = os.getcwd()
    slug = cwd.replace("/", "-")
    return os.path.expanduser(f"~/.claude/projects/{slug}")


def truncate(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) > limit:
        return text[:limit] + " …[truncated]"
    return text


def text_from_content(content, limit: int):
    """メッセージの content フィールドから、人が意味を読み取れるテキスト／ツール情報を抽出する。"""
    if isinstance(content, str):
        return [("text", truncate(content, limit))] if content.strip() else []
    out = []
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "thinking":
                continue  # 破棄: 量が多く、セッション横断のシグナルは乏しい
            if btype == "text":
                t = block.get("text", "")
                if t.strip():
                    out.append(("text", truncate(t, limit)))
            elif btype == "tool_use":
                name = block.get("name", "?")
                inp = block.get("input", {})
                desc = ""
                if isinstance(inp, dict):
                    desc = inp.get("description") or inp.get("command") or inp.get("file_path") or inp.get("query") or ""
                out.append(("tool", truncate(f"{name}: {desc}", limit)))
            elif btype == "tool_result":
                if block.get("is_error"):
                    c = block.get("content", "")
                    if isinstance(c, list):
                        c = " ".join(b.get("text", "") for b in c if isinstance(b, dict))
                    out.append(("error", truncate(str(c), limit)))
    return out


def digest_session(path: str, max_chars: int) -> dict:
    events = []
    ts_first = ts_last = None
    cwd = git_branch = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = obj.get("timestamp")
            if ts:
                ts_first = ts_first or ts
                ts_last = ts
            cwd = cwd or obj.get("cwd")
            git_branch = git_branch or obj.get("gitBranch")
            t = obj.get("type")
            if t not in ("user", "assistant", "system"):
                continue
            if t == "system":
                content = obj.get("content") or obj.get("message", {})
                if isinstance(content, dict):
                    content = content.get("content", "")
                txt = str(content)
                if any(k in txt.lower() for k in ("error", "fail", "denied", "rejected")):
                    events.append(("system", truncate(txt, max_chars)))
                continue
            msg = obj.get("message", {})
            for kind, txt in text_from_content(msg.get("content"), max_chars):
                role = "user" if t == "user" else "assistant"
                events.append((f"{role}/{kind}", txt))
    return {
        "session": os.path.basename(path).replace(".jsonl", ""),
        "cwd": cwd,
        "git_branch": git_branch,
        "started": ts_first,
        "ended": ts_last,
        "events": events,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project-dir", default=None)
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--max-chars", type=int, default=600)
    args = ap.parse_args()

    project_dir = args.project_dir or derive_project_dir()
    if not os.path.isdir(project_dir):
        print(f"エラー: プロジェクトのトランスクリプトディレクトリが見つかりません: {project_dir}", file=sys.stderr)
        print("--project-dir を明示的に指定してください。トランスクリプトは ~/.claude/projects/<slug>/ にあります。", file=sys.stderr)
        sys.exit(1)

    files = sorted(
        glob.glob(os.path.join(project_dir, "*.jsonl")),
        key=os.path.getmtime,
        reverse=True,
    )[: args.limit]

    if not files:
        print(f"{project_dir} に .jsonl トランスクリプトが見つかりません", file=sys.stderr)
        sys.exit(1)

    print(f"# セッションダイジェスト — {project_dir}")
    print(f"# 直近 {len(files)} セッション（新しい順）\n")
    for path in files:
        d = digest_session(path, args.max_chars)
        print(f"## セッション {d['session']}")
        print(f"   期間: {d['started']} → {d['ended']}  ブランチ: {d['git_branch']}")
        for kind, txt in d["events"]:
            print(f"   [{kind}] {txt}")
        print()


if __name__ == "__main__":
    main()
