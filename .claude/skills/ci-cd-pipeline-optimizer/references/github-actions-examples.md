# GitHub Actions 実装例集

SKILL.md本文の各手法に対応する、GitHub Actionsでの実装イメージ。値やパスはリポジトリの実態に合わせて調整すること。ここに挙げるのは「型」であり、そのままコピーして動く完成品ではない。

## 目次

- [キャッシュ](#キャッシュ)
- [変更検出とスキップ](#変更検出とスキップ)
- [matrix並列化](#matrix並列化)
- [リリース自動化](#リリース自動化)
- [通知](#通知)

## キャッシュ

依存関係のロックファイルをキャッシュキーにする。Node.jsの例:

```yaml
- uses: actions/setup-node@v4
  with:
    node-version: '20'
    cache: 'npm'
    cache-dependency-path: package-lock.json
```

`actions/setup-node`等の言語別setup actionにキャッシュ機能が無い、または依存関係インストール以外(ビルド成果物・テストDBのスキーマなど)をキャッシュしたい場合は `actions/cache` を使う。

```yaml
- uses: actions/cache@v4
  with:
    path: |
      ~/.cache/pip
      .venv
    key: ${{ runner.os }}-pip-${{ hashFiles('**/poetry.lock') }}
    restore-keys: |
      ${{ runner.os }}-pip-
```

ポイント:
- `key` にロックファイルのハッシュを含めることで、依存関係が変わらない限りキャッシュを再利用できる
- `restore-keys` にプレフィックスだけの部分一致キーを用意しておくと、完全一致キャッシュが無い場合でも近いキャッシュを取得でき、フルインストールより速くなる

## 変更検出とスキップ

`.md`やdocsディレクトリのみの変更ではテストを省略したいが、ワークフロー自体は必須ステータスチェックの都合で常に起動させ、内部のジョブ側でスキップ判定する。

```yaml
jobs:
  changes:
    runs-on: ubuntu-latest
    outputs:
      code: ${{ steps.filter.outputs.code }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            code:
              - '!**/*.md'
              - '!docs/**'

  test:
    needs: changes
    if: needs.changes.outputs.code == 'true'
    runs-on: ubuntu-latest
    steps:
      - run: echo "run tests"
```

`test` ジョブ自体は必須ステータスチェックとして常に「実行される（結果がskipped/successいずれか）」状態を保ちながら、ドキュメントのみの変更では実質的な処理をスキップできる。ワークフロー全体を`on.paths-ignore`で止めてしまうと、必須チェックに指定されたワークフローが「実行されない」扱いになりPRがマージ不可のまま止まる点に注意する。

## matrix並列化

テストスイートを分割し、複数ジョブで同時実行する。

```yaml
jobs:
  test:
    strategy:
      fail-fast: false
      matrix:
        shard: [1, 2, 3, 4]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npx jest --shard=${{ matrix.shard }}/${{ strategy.job-total }}
```

ポイント:
- 総所要時間は最も遅いシャードで決まる。ファイル数の機械的な等分ではなく、実行時間ベースで分割できるツール(各言語のテストランナーのshard機能や、CIベンダー提供の実行時間分散機能)を使うと、シャード間の完了時刻が揃いやすい
- `fail-fast: false` にしておくと、1シャードの失敗で他シャードの結果が見えなくなるのを防げる

## リリース自動化

マージ済みPRからリリースノートを自動生成し、リリース用PRを自動作成するワークフロー。`googleapis/release-please-action` のようなツールを使う例:

```yaml
name: release-please
on:
  push:
    branches: [main]

jobs:
  release-please:
    runs-on: ubuntu-latest
    steps:
      - uses: googleapis/release-please-action@v4
        with:
          release-type: node
```

このワークフローは、mainへの変更を検知するとリリースノートを含むリリース用PRを自動作成・更新する。人間はこのPRをレビューしてマージするだけでよい。

mainへのマージ(＝リリースPRのマージ)をトリガーに本番デプロイを実行する、責務を分離した別ワークフロー:

```yaml
name: deploy-production
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: ./deploy.sh production
```

「リリースノート生成・リリースPR作成」と「本番デプロイの実行」を別ワークフローに分けておくと、それぞれの責務がはっきりし、デプロイだけを個別に再実行する、リリースPRの仕組みだけを差し替える、といった変更がしやすくなる。

## 通知

デプロイジョブの末尾に、成功・失敗どちらでも必ず実行される通知ステップを置く。

```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: ./deploy.sh production

      - name: Notify Slack
        if: always()
        uses: slackapi/slack-github-action@v2
        with:
          method: chat.postMessage
          token: ${{ secrets.SLACK_BOT_TOKEN }}
          payload: |
            channel: "C0123456789"
            text: "${{ job.status == 'success' && ':white_check_mark: production deploy succeeded' || ':x: production deploy failed' }} (${{ github.sha }})"
```

`if: always()` が無いと、直前のステップが失敗した時点でワークフローが打ち切られ、このステップ自体が実行されない。成功時にも通知を送ることで、「通知が来ない」ことが成功なのか通知経路自体の故障なのかを区別できるようにする。
