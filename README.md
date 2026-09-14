# skills

Claude Code の再利用可能なスキル（`.claude/skills/`）を集めたリポジトリ。各スキルは `<name>/SKILL.md` を本体とし、必要に応じて `references/`（詳細資料）・`assets/`（雛形）・`scripts/`（実行コード）を持つ。

スキルはユーザーが明示的に呼び出すものではなく、`SKILL.md` の `description` に書かれたトリガー文言や場面に一致したときにエージェントが自律的に読み込む（progressive disclosure）。スキルの書き方・命名・相互参照の規約は [`CLAUDE.md`](./CLAUDE.md) を参照。

## サイクルで見る

要件定義から改善までの開発サイクルに沿って分類すると、以下のようになる。フェーズをまたいで使うスキル（エージェント運用・意思決定の記録）は下段に分けている。

```mermaid
flowchart TB
    subgraph P1["① 要件定義・計画"]
        direction LR
        RD[requirements-definition]
        TSK[task-breakdown]
    end
    subgraph P2["② 設計"]
        direction LR
        DBS[database-selection]
        MR[modifiability-review]
    end
    subgraph P3["③ 実装"]
        direction LR
        RF[refactoring]
        PO[performance-optimization]
        DBP[database-performance]
        DM[dependency-management]
    end
    subgraph P4["④ テスト"]
        direction LR
        TW[test-writer]
        E2E[e2e-testing]
    end
    subgraph P5["⑤ レビュー・PR"]
        direction LR
        CR[code-reviewer]
        PRC[pull-request-composer]
        PCS[pre-commit-scrubber]
    end
    subgraph P6["⑥ リリース"]
        direction LR
        CICD[ci-cd-pipeline-optimizer]
        RS[release-strategy]
    end
    subgraph P7["⑦ 運用"]
        direction LR
        ND[notification-design]
        DBG[debugging]
    end
    subgraph P8["⑧ 改善"]
        DP[development-productivity]
    end

    P1 --> P2 --> P3 --> P4 --> P5 --> P6 --> P7 --> P8
    P8 -. フィードバック .-> P1
```

フェーズをまたいで、サイクル全体を下支えするスキル。

```mermaid
flowchart LR
    Cycle["要件定義〜改善の全サイクル"]
    DR[decision-records]
    AP[agent-parallelization]
    SD[subagent-delegation]
    AS[agent-security]
    CE[context-engineering]

    DR -. 後戻りしにくい決定を記録 .-> Cycle
    AP -. 複数エージェントの同時実行 .-> Cycle
    SD -. サブタスクの切り出し .-> Cycle
    AS -. 外部テキスト・権限の安全性 .-> Cycle
    CE -. CLAUDE.md/メモリの設計 .-> Cycle
```

### ① 要件定義・計画

| スキル | 概要 |
|---|---|
| `requirements-definition` | 曖昧な機能要望から、目的・受入基準・非対象・制約を実装着手前に固める |
| `task-breakdown` | 実装を、安全にマージ・revertできる小さな単位に分解する |

### ② 設計

| スキル | 概要 |
|---|---|
| `database-selection` | RDB・ドキュメント・KVS・DWHなど、用途に応じたデータストアを選ぶ |
| `modifiability-review` | 変更が「分ける／なおす／壊す」のどれかを分類し、変更容易性を点検する |

### ③ 実装

| スキル | 概要 |
|---|---|
| `refactoring` | 振る舞いを変えずに構造だけを整理し、構造変更と振る舞い変更を分離する |
| `performance-optimization` | 「遅い・重い」相談を、症状分類と優先順位づけで解決する |
| `database-performance` | ストレージ読み取り量の最小化を軸に、DBの遅さを解消する |
| `dependency-management` | 依存の追加は必要性の吟味から、更新はチェンジログ確認と一つずつの原則で進める |

### ④ テスト

| スキル | 概要 |
|---|---|
| `test-writer` | カバレッジ数値でなく「壊れたら確実に落ちる」防御的なテストを設計する |
| `e2e-testing` | 主要な動線に絞った、信頼できる小規模なE2Eスイートを維持する |

### ⑤ レビュー・PR

| スキル | 概要 |
|---|---|
| `code-reviewer` | 作成者以外の視点で、機械に任せられない判断（設計適合・要件充足など）に絞ってレビューする |
| `pull-request-composer` | 差分を粒度で診断し、分割案の提示・コミット・PR作成までを仕立てる |
| `pre-commit-scrubber` | `commit` 前にシークレット・PII・組織固有名の混入をスキャンする |

### ⑥ リリース

| スキル | 概要 |
|---|---|
| `ci-cd-pipeline-optimizer` | CIの高速化・リリース自動化・結果通知の3軸でパイプラインを改善する |
| `release-strategy` | デプロイとリリースを分離し、Feature Flagで段階的に機能を公開する |

### ⑦ 運用

| スキル | 概要 |
|---|---|
| `notification-design` | 問題に気づくまでの時間（MTTD）を縮める通知・監視を設計する |
| `debugging` | 仮説を立ててから1つずつ検証する、原因調査と本番障害対応の手順 |

### ⑧ 改善

| スキル | 概要 |
|---|---|
| `development-productivity` | 開発生産性を3段階で定義し、グッドハートの法則を警戒しながら計測・改善する |

### 横断（意思決定の記録）

| スキル | 概要 |
|---|---|
| `decision-records` | 後戻りしにくい決定を、軽量なADR形式で後から参照できる形に残す |

## AI駆動開発の運用基盤

コードの中身ではなく、「AIエージェントにどう作業させるか」という運用そのものを扱うスキル。上記どのフェーズでも使う。

| スキル | 概要 |
|---|---|
| `agent-parallelization` | 複数のAIエージェントを、作業ツリーを分離しながら同時実行する |
| `subagent-delegation` | 1つの有界なサブタスクを、メインの会話の文脈を汚さずに切り出す |
| `agent-security` | 外部テキストを指示として扱わず、ツール権限を許可リストで絞る |
| `context-engineering` | `CLAUDE.md`・永続メモリなど、エージェントに読ませる情報の置き場所を設計する |

## その他（リポジトリ運用ツール）

開発サイクルそのものではなく、このリポジトリ／個人の作業環境を運用するためのツール。

| スキル | 概要 |
|---|---|
| `catch-up-claude-code` | Claude Codeの未読リリースを検出・要約してVaultに保存する |
| `catch-up-vscode` | VS Codeの未読リリースを検出・要約してVaultに保存する |
| `reflect-on-sessions` | 過去のAIコーディングセッションを横断レビューし、繰り返すパターンを永続メモリへ反映する |
| `intro-video` | 手元の資料（README・設計ドキュメント等）からナレーション付きの紹介動画を生成する |

## 相関関係図

全27スキルの `SKILL.md`（と `references/`）を機械的に走査すると60本の参照が見つかるが、単純な言及数は実態を表さない。60本を実際に読んで、次の4種類に分類し直した。

| 分類 | 内容 | 本数 |
|---|---|---|
| **A: 必須の実行依存** | 手順の中で参照先の実行が必須ゲートになっている | 1本 |
| **B: 生産者/消費者関係** | 一方の出力・判断結果が他方の入力としてそのまま使われる | 18本 |
| D: 正典の引用 | 「詳細は◯◯を見よ、複製しない」という情報源の案内。実行を伴わない | 35本 |
| E: 境界宣言 | 「これは対象外、◯◯へ」という責務の切り離し | 6本 |

**実際にワークフロー上の繋がりと言えるのは60本中19本（32%）だけ。** 残りは「詳しくはこちらを見て」という案内か、「ここは自分の担当外」という宣言で、実行や成果物の受け渡しを伴わない。

さらに、B（生産者/消費者）19本のうち約半数は、**文章上の参照の向きと実際のデータが流れる向きが逆だった。** 「`decision-records`が`database-selection`を参照する」という書き方でも、実際に流れる情報は「`database-selection`で決定が出たら、その結果を`decision-records`が受け取って記録する」であり、データは逆方向に流れる。以下はデータフローの向きに直した図。

```mermaid
flowchart TB
    RD["requirements-definition"]
    TSK["task-breakdown"]
    DBS["database-selection"]
    MR["modifiability-review"]
    PO["performance-optimization"]
    DBP["database-performance"]
    DM["dependency-management"]
    E2E["e2e-testing"]
    CR["code-reviewer"]
    PRC["pull-request-composer"]
    PCS["pre-commit-scrubber"]
    RS["release-strategy"]
    ND["notification-design"]
    DBG["debugging"]
    DR["decision-records"]
    AP["agent-parallelization"]
    CE["context-engineering"]
    TW["test-writer"]

    PRC == 必須ゲート ==> PCS
    PCS -. 制御を返す .-> PRC
    RD --> AP
    RD --> CR
    RD --> E2E
    RD <--> TSK
    TSK --> AP
    TSK --> DM
    TSK --> PRC
    CE --> DR
    DBS --> DR
    MR --> DR
    PO --> DR
    RS --> DR
    DM --> DR
    PO --> DBP
    DBG --> ND
    DBG --> TW

    classDef sink fill:#fef2f2,stroke:#dc2626,stroke-width:2px
    class DR sink
```

この図から見えること：

- **必須の実行依存はリポジトリ全体で `pull-request-composer` ⇄ `pre-commit-scrubber` の1組だけ。** push前にシークレットスキャンを必ず通すという、唯一のハードな依存関係
- **`decision-records`（赤枠）は6つのスキルから決定結果を受け取る一方的なシンク（受け皿）。** 「後戻りしにくい決定が出たら記録する」という性質上、自然とそうなる
- **`requirements-definition` と `task-breakdown` は実データが流れ出す起点。** ここで固めた目的・受入基準・分解結果が、`agent-parallelization`・`code-reviewer`・`e2e-testing`・`pull-request-composer`・`dependency-management` へ流れていく
- 上記に載っていない残り9スキル（`ci-cd-pipeline-optimizer`・`refactoring`・`subagent-delegation`・`agent-security` など）は、他スキルとの間に**実行依存も成果物の受け渡しもない**——正典の引用や境界宣言でのみ繋がっている

個々の参照（引用・境界宣言を含む全60本）は各 `SKILL.md` を参照。

## スキルの書き方

新しいスキルの追加・既存スキルの改修は [`CLAUDE.md`](./CLAUDE.md) の規約に従う。要点だけ挙げると：

- 新規スキルは既存スキルへの参照を最低1本、多くても2〜3本に留める（孤島にしない、増やしすぎない）
- 同じ判断基準を複数のスキルに複製しない。正典を1つ決め、他方は参照に縮める
- 統合すべきか分けるべきかは、承認ゲートの性質・前提とする実行環境が違うかで判断する
