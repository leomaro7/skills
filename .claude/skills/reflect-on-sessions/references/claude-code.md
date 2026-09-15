# バリアント: Claude Code

Claude Code のセッションを振り返り、ファイルベースのメモリ（`MEMORY.md` ＋ `memory/`）への 更新案を作るときの、入力（ログ）と出力（メモリ）の具体仕様。
共通ワークフローは SKILL.md を参照。

## 入力 — トランスクリプトの場所と読み方

- 場所: `~/.claude/projects/<slug>/*.jsonl`
  - `<slug>` は作業ディレクトリの `/` を `-` に置換したもの（例: `/Users/you/myproject` → `-Users-you-myproject`）
- ダイジェスト生成（生 `.jsonl` を直接読まない。
  `thinking` や巨大なツール出力でコンテキストを浪費するため）:

```bash
python3 scripts/digest_claude_code.py --limit 10
```

  - `--project-dir` で別プロジェクトを対象にできる（既定は cwd から自動導出）
  - `--limit`（新しい順のセッション数）と `--max-chars`（切り詰め文字数）を要望に応じて調整。
    まず 10。
  - ダイジェストはユーザープロンプト、アシスタント本文、ツール呼び出し、エラーを残す。

## 出力 — メモリストアの場所と規約

- 場所: `~/.claude/projects/<slug>/memory/`（`MEMORY.md` ＋ 事実1件ごとのファイル）
- まず `MEMORY.md` と個別ファイルを読み、提案を「本当に新しいもの」に絞る（重複回避・陳腐化検出）。
- 反映時は**セッションで提供される最新のメモリ規約が最優先**。
  確立済みフォーマットの要点:
  - 1ファイル1事実。
    `name` は kebab-case。
    frontmatter に `name` / `description` / `metadata.type`（`type` は `user | feedback | project | reference`）。
  - `feedback` と `project` の本文には `**Why:**` と `**How to apply:**` の行を入れる。
  - 関連メモリは `[[other-name]]` でリンク。
    相対的な日付は絶対日付に変換。
  - 各ファイルを書いたら `MEMORY.md` に1行のポインタを追記 （`- [Title](file.md) — hook`）。
    `MEMORY.md` 本体に事実の中身は書かない。
  - 既存ファイルは重複を作らず、その場で更新・削除する。
