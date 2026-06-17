# バリアント: GitHub Copilot (VS Code)

VS Code の GitHub Copilot Chat 履歴を振り返り、Copilot の永続指示
（`.github/copilot-instructions.md` など）への更新案を作るときの、入力と出力の具体仕様。
共通ワークフローは SKILL.md を参照。

> 注意: このスキル自体は Claude Code の中で動く。ここで対象にするのは「Copilot のログを読み、
> Copilot の指示ファイルへの提案を作る」ことであって、Copilot 上でスキルが動くわけではない。

## 入力 — Copilot Chat 履歴の場所と読み方

- 場所（macOS）: `~/Library/Application Support/Code/User/workspaceStorage/<hash>/chatSessions/*.json|*.jsonl`
  - `<hash>` は同階層の `workspace.json`（`folder: "file:///..."`）で実フォルダに対応づく。
  - 別 OS / VS Code Insiders ではルートが異なる（Linux: `~/.config/Code/User/workspaceStorage`、
    Insiders: `"Code - Insiders"`）。その場合は `--storage-root` を渡す。
- ダイジェスト生成（プロジェクトパスから `<hash>` を自動逆引きする）:

```bash
python3 scripts/digest_copilot.py --project-path /path/to/project --limit 10
```

  - 逆引きできないときは `--workspace-hash <hash>` で直接指定。
  - 2つのセッション形式に対応済み: `.json`（`requests[]`）と `.jsonl`（`kind:2` の `v` に request 配列）。
  - ダイジェストはユーザープロンプト、アシスタント本文、ツール呼び出しを残す（`thinking` は破棄）。

## 出力 — Copilot の永続指示（MEMORY.md 相当はない）

Copilot には Claude Code の `MEMORY.md` のような構造化メモリストアは**ない**。永続的な指示は
リポジトリ単位の指示ファイルに書く。提案の反映先は次のいずれか:

- `.github/copilot-instructions.md` — そのリポジトリ全体に効く既定の指示（最有力）。
- `.github/instructions/*.instructions.md` — `applyTo` の glob で対象ファイルを絞れる個別指示。

書き方の要点:
- 1事実1ファイルではなく、**1つの指示文書に箇条書きで追記**していく形式。
- 既存の `copilot-instructions.md` があれば必ず読み、重複・矛盾を避けて追記/更新する。
- 簡潔な命令形（「〜する」「〜しない」）で書く。Copilot は全文を毎回読み込むため冗長さはコスト。
- 抽出した知見のうち「繰り返す好み・規約」は指示文書向き。一過性の事実やプロジェクト固有メモは
  無理に書かない（Claude Code の `project` メモリほど構造化された置き場がないため）。

### 提案のみ（重要）
`.github/copilot-instructions.md` は人間とチームが共有するファイル。**勝手に書き換えない**。
追加/更新/削除の提案リストを提示し、ユーザーが承認したものだけを反映する。
