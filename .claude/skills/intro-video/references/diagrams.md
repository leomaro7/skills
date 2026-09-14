# 図を入れる

## その画像は要るのか

紹介動画に**飾りの画像は要らない。** 抽象的なイラストや雰囲気の写真を挟んでも、視聴者が受け取る情報は増えず、ナレーションから注意がそれるだけになる。

入れる価値があるのは次の3つに限られる。

- **仕組みが分かる図** — 流れ、構成、層。言葉で説明すると長くなるものを一目にする
- **実物** — スクリーンショット、コマンドの出力、ビフォーアフター
- **数値の比較** — 棒や数字。「速くなった」より「240分が12分」のほうが耳に残る

いずれもコードで描ける。**画像ファイルを貼るのではなくスライドの中で描くと、テーマを差し替えたときに図の色も一緒に変わり、解像度も落ちない。**

## 使える部品

すべてテーマ変数を参照しているので、`apply_theme.py` でテーマを変えると図も追従する。

| 部品 | 用途 |
|---|---|
| `.flow` | 横並びの流れ（A → B → C） |
| `.compare` | 前後・2案の並置 |
| `.bars` | 比率の比較（横棒） |
| `.stack` | 層の積み重ね（構成図） |
| `.figure` + インライン SVG | 上記で描けない任意の図 |
| `.media` / `slide--bleed` | スクリーンショットや写真（`references/layouts.md`） |

### 流れ

```html
<div class="flow">
  <div class="flow__box"><div class="t">素材</div><div class="d">README・議事録</div></div>
  <div class="flow__arrow">→</div>
  <div class="flow__box"><div class="t">台本</div><div class="d">narration.json</div></div>
  <div class="flow__arrow">→</div>
  <div class="flow__box flow__box--accent"><div class="t">動画</div><div class="d">intro.mp4</div></div>
</div>
```

`flow__box--accent` は差し色で塗る。**ゴールにあたる1箱だけに付ける。** 複数に付けるとどこが終点か分からなくなる。箱は4つまで。

### 前後の比較

```html
<div class="compare">
  <div class="compare__col">
    <div class="compare__h">BEFORE</div>
    <div class="compare__b">スライドを作り、録音し、編集する。<br><b>半日かかる。</b></div>
  </div>
  <div class="compare__col compare__col--after">
    <div class="compare__h">AFTER</div>
    <div class="compare__b">素材を渡して台本を直す。<br><b>30秒で組み上がる。</b></div>
  </div>
</div>
```

`<b>` で囲んだ部分だけ本文色になる。各カラムで**言い切りの1文だけ**を強調する。

### 比率

```html
<div class="bars">
  <div class="bar bar--muted">
    <div class="bar__l"><span>手作業で制作</span><span class="v">約240分</span></div>
    <div class="bar__t"><div class="bar__f" style="--w: 100%"></div></div>
  </div>
  <div class="bar">
    <div class="bar__l"><span>このスキル</span><span class="v">約12分</span></div>
    <div class="bar__t"><div class="bar__f" style="--w: 5%"></div></div>
  </div>
</div>
```

`--w` に幅をパーセントで書く。**比較対象は2〜3本まで。** それ以上はグラフを読む時間が要る＝読む資料になる。基準にする側へ `bar--muted` を付けると、どちらが主役か迷わない。

### 層

```html
<div class="stack">
  <div class="stack__l stack__l--accent">動画 <div class="d">mp4 / 2〜3分</div></div>
  <div class="stack__l">結合 <div class="d">ffmpeg</div></div>
  <div class="stack__l">音声合成 <div class="d">OS標準 / piper / VOICEVOX</div></div>
</div>
```

上から下へ「抽象 → 具体」または「出口 → 入口」の順に並べる。4層まで。

## 任意の図をインライン SVG で描く

上記で足りない図（分岐、循環、対応関係など）は SVG を直接書く。ポイントは一つ、**色をテーマ変数で書くこと。**

```html
<div class="figure">
  <svg viewBox="0 0 1200 240" role="img" aria-label="図の内容を一文で">
    <rect x="0" y="30" width="330" height="180" rx="14"
          fill="var(--panel)" stroke="var(--rule)" stroke-width="2"/>
    <text x="165" y="112" text-anchor="middle" font-size="34" font-weight="600"
          fill="var(--ink)">台本</text>
    <text x="165" y="160" text-anchor="middle" font-size="26" fill="var(--muted)">耳に届ける</text>

    <path d="M790 120 H856" stroke="var(--accent)" stroke-width="4" fill="none"/>
    <path d="M844 106 L862 120 L844 134 Z" fill="var(--accent)"/>

    <rect x="874" y="30" width="326" height="180" rx="14"
          fill="var(--accent)" stroke="var(--accent)"/>
    <text x="1037" y="130" text-anchor="middle" font-size="36" font-weight="700"
          fill="var(--bg)">動画</text>
  </svg>
  <div class="figure__cap">必要なら図の下に短い注釈。</div>
</div>
```

- **書体は指定しない。** SVG の `text` は親の CSS から `font-family` を継承するので、テーマの書体がそのまま効く。`font-family="var(--font)"` と属性で書いても効かない。
- `viewBox` の幅は 1200 前後にしておくと、`.figure` が横幅いっぱいに伸ばしたときに文字サイズが本文と揃う。
- **角の丸みは書かなくてよい。** `rect` の `rx` はテンプレート側で `--radius` を当ててあるので、`corporate` や `mono` のように角を落とすテーマでは自動で直角になる。特定の矩形だけ変えたいときは `style="rx: 0"` で上書きする。
- `role="img"` と `aria-label` は、図が何を示しているかを一文で書く。ここを書こうとして書けない図は、たいてい情報を詰めすぎている。

## 複雑な依存関係は graphviz

箱と線が10個を超えるような図（モジュール依存、データフロー）は手で SVG を書くより `dot` のほうが速い。

```bash
dot -Tsvg graph.dot -o graph.svg
```

出力した SVG を `.figure` の中に貼り、`fill` / `stroke` をテーマ変数に置換する。ただし **10個を超える箱は動画では読めない。** graphviz を使いたくなった時点で、そのスライドは情報を詰めすぎている可能性が高いので、まず図を分割できないか考える。

## 写真やイラストが要るとき

このスキルは画像を生成しない。用意する手段は3つある。

- **実物を撮る** — スクリーンショットが最も情報量が多い。`.media` で置く
- **社内やフリーの素材を使う** — ライセンスを確認する
- **外部の画像生成サービスを使う** — プロンプトと素材が外部に出る。音声エンジンの `neural` と同じ判断（`references/setup.md`）が必要で、機密性のある素材では使えない

ただし冒頭に戻ると、**紹介動画で画像が足りないと感じる場面の多くは、実際には図が足りない。** まず上の部品で描けないか考える。
