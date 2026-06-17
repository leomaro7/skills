#!/usr/bin/env python3
"""VS Code の GitHub Copilot Chat 履歴をコンパクトなダイジェストに圧縮する。

Copilot Chat のセッションは VS Code のワークスペースごとに保存される:
    ~/Library/Application Support/Code/User/workspaceStorage/<hash>/chatSessions/*.json|*.jsonl

`<hash>` は同階層の `workspace.json`（`folder: "file:///..."`）で実フォルダに対応づく。
このスクリプトは対象プロジェクトのフォルダパスから `<hash>` を逆引きし、その配下の
セッションを読んで、トークン効率の良いダイジェスト（ユーザープロンプト、アシスタント本文、
ツール呼び出し）を出力する。`thinking` など大量のノイズは捨てる。

2つのセッション形式に対応:
  - .json  : version 3 の単一オブジェクト。`requests[]` を持つ。
  - .jsonl : 追記ログ。`kind:2` の行の `v` に request 配列が入る（`kind:0` はヘッダ）。

使い方:
    digest_copilot.py [--project-path DIR] [--limit N] [--max-chars C]
                      [--workspace-hash HASH] [--storage-root DIR]

既定値:
    --project-path : 現在の作業ディレクトリ
    --limit        : 10（新しい順のセッション数）
    --max-chars    : 600（テキストフィールドごとの切り詰め文字数）
    --storage-root : ~/Library/Application Support/Code/User/workspaceStorage

注意: macOS のパスを既定にしている。別 OS や VS Code Insiders を使う場合は
--storage-root を渡す（例: Linux は ~/.config/Code/User/workspaceStorage、
Insiders は "Code - Insiders"）。
"""
import argparse
import glob
import json
import os
import re
import sys

DEFAULT_STORAGE_ROOT = os.path.expanduser(
    "~/Library/Application Support/Code/User/workspaceStorage"
)
_LINK_RE = re.compile(r"\[[^\]]*\]\((file://)?[^)]*\)")


def truncate(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    if len(text) > limit:
        return text[:limit] + " …[truncated]"
    return text


def resolve_workspace_hashes(project_path: str, storage_root: str):
    """project_path に一致するワークスペースの hash を返す（前方一致も拾う）。"""
    target = "file://" + os.path.abspath(os.path.expanduser(project_path))
    hits = []
    for wj in glob.glob(os.path.join(storage_root, "*", "workspace.json")):
        try:
            folder = json.load(open(wj, encoding="utf-8")).get("folder", "")
        except (json.JSONDecodeError, OSError):
            continue
        if folder == target or folder.rstrip("/") == target.rstrip("/"):
            hits.append(os.path.basename(os.path.dirname(wj)))
    return hits


def text_from_response(response, limit: int):
    """Copilot の response ブロック配列から、本文とツール呼び出しを抽出する。"""
    out = []
    if not isinstance(response, list):
        return out
    for b in response:
        if not isinstance(b, dict):
            continue
        kind = b.get("kind")
        if kind == "thinking":
            continue  # 破棄: 量が多く、セッション横断のシグナルは乏しい
        if kind is None and "value" in b:  # 本文（markdownContent 相当）
            v = b.get("value")
            if isinstance(v, dict):
                v = v.get("value", "")
            if str(v).strip():
                out.append(("text", truncate(v, limit)))
        elif kind == "toolInvocationSerialized":
            tool = b.get("toolId", "?")
            inv = b.get("invocationMessage")
            if isinstance(inv, dict):
                inv = inv.get("value", "")
            inv = _LINK_RE.sub(lambda m: m.group(0).split("](")[0][1:], str(inv))
            out.append(("tool", truncate(f"{tool}: {inv}", limit)))
    return out


def iter_requests(path: str):
    """.json / .jsonl のどちらからでも request オブジェクトを順に返す。"""
    if path.endswith(".jsonl"):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("kind") == 2 and isinstance(obj.get("v"), list):
                yield from (r for r in obj["v"] if isinstance(r, dict))
    else:
        try:
            d = json.load(open(path, encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        yield from (r for r in d.get("requests", []) if isinstance(r, dict))


def digest_session(path: str, max_chars: int) -> dict:
    events = []
    ts_first = ts_last = None
    for r in iter_requests(path):
        ts = r.get("timestamp")
        if ts:
            ts_first = ts_first or ts
            ts_last = ts
        msg = r.get("message")
        text = msg.get("text") if isinstance(msg, dict) else msg
        if text and str(text).strip():
            events.append(("user/text", truncate(text, max_chars)))
        for kind, txt in text_from_response(r.get("response"), max_chars):
            events.append((f"assistant/{kind}", txt))
    return {
        "session": os.path.basename(path).rsplit(".", 1)[0],
        "started": ts_first,
        "ended": ts_last,
        "events": events,
    }


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--project-path", default=os.getcwd())
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--max-chars", type=int, default=600)
    ap.add_argument("--workspace-hash", default=None)
    ap.add_argument("--storage-root", default=DEFAULT_STORAGE_ROOT)
    args = ap.parse_args()

    if not os.path.isdir(args.storage_root):
        print(f"エラー: workspaceStorage が見つかりません: {args.storage_root}", file=sys.stderr)
        print("--storage-root で明示的に指定してください（OS や VS Code Insiders で場所が異なる）。", file=sys.stderr)
        sys.exit(1)

    if args.workspace_hash:
        hashes = [args.workspace_hash]
    else:
        hashes = resolve_workspace_hashes(args.project_path, args.storage_root)
        if not hashes:
            print(f"プロジェクト {args.project_path} に対応する Copilot ワークスペースが見つかりません。", file=sys.stderr)
            print("--workspace-hash で直接指定するか、--project-path を確認してください。", file=sys.stderr)
            sys.exit(1)

    files = []
    for h in hashes:
        files += glob.glob(os.path.join(args.storage_root, h, "chatSessions", "*.json"))
        files += glob.glob(os.path.join(args.storage_root, h, "chatSessions", "*.jsonl"))
    files = sorted(set(files), key=os.path.getmtime, reverse=True)[: args.limit]

    if not files:
        print(f"対象ワークスペース {hashes} に chatSessions が見つかりません。", file=sys.stderr)
        sys.exit(1)

    print(f"# Copilot セッションダイジェスト — {args.project_path}")
    print(f"# ワークスペース {hashes} / 直近 {len(files)} セッション（新しい順）\n")
    for path in files:
        d = digest_session(path, args.max_chars)
        print(f"## セッション {d['session']}")
        print(f"   期間(ms): {d['started']} → {d['ended']}")
        for kind, txt in d["events"]:
            print(f"   [{kind}] {txt}")
        print()


if __name__ == "__main__":
    main()
