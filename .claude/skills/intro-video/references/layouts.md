# 配置のカタログ

スライドは素の HTML なので、最終的には何でも書ける。
ただし毎回ゼロから組むと動画全体の統一感が崩れるので、**まずここにある部品の組み合わせで足りないかを見る**。
すべてテーマ（色・書体）と直交していて、どのテーマでも成立する。

## 土台の5レイアウト

| クラス | 中身 | 使いどころ |
|---|---|---|
| `slide--title` / `slide--closing` | `h1` + `.lead` | 開始と締め |
| `.points` | 3〜4項目の箇条書き | 並列する要点 |
| `slide--statement` | `.statement` 一文 | 刺したい一箇所 |
| `.split` | 左に説明、右に実物 | 具体例を見せる |
| `.steps` | 横並びの手順 | 流れ・手順 |

## 寄せを変える

`.slide` に足す。
既定は左寄せ・上から。

```html
<section class="slide slide--center" id="...">   <!-- 中央寄せ -->
<section class="slide slide--right"  id="...">   <!-- 右寄せ -->
<section class="slide slide--middle" id="...">   <!-- 垂直中央 -->
```

`slide--center` は箇条書きとカードの中身だけ左寄せのまま残す。
中央寄せの箇条書きは読みにくいため。

**動画では寄せを頻繁に変えないほうがいい。**
カットが切り替わるたびに視線の始点が動くと落ち着かない。
変えるのは、つかみ・締め・`statement` のような「区切り」の1枚に絞る。

## 分割の比率と向き

`.split` に足す。

```html
<div class="split split--wide">    <!-- 説明3 : 実物2。説明を厚く -->
<div class="split split--narrow">  <!-- 説明2 : 実物3。実物を大きく -->
<div class="split split--flip">    <!-- 左右を入れ替える -->
```

`split--flip` は、同じ `.split` が続くときに交互にすると単調さが消える。

## 格子（カード）

項目が5つ以上あるとき、`.points` の縦積みより収まる。

```html
<div class="grid cols-3">
  <div class="card"><div class="t">見出し</div><div class="d">短い補足。</div></div>
  <div class="card"><div class="t">見出し</div><div class="d">短い補足。</div></div>
  <div class="card"><div class="t">見出し</div><div class="d">短い補足。</div></div>
</div>
```

`cols-2` / `cols-3` / `cols-4` を切り替える。
**`cols-4` は1枚に8項目まで置けてしまうが、そこまで載せると聞く資料ではなくなる。**
6つを超えたらスライドを分ける。

## 数字を見せる

「2分」「3ステップ」「80%削減」のような数字は、文章に埋めるより単独で置くほうが耳にも残る。

```html
<div class="metrics">
  <div><div class="metric__v">2分</div><div class="metric__l">1本あたりの制作時間</div></div>
  <div><div class="metric__v">4つ</div><div class="metric__l">選べる音声エンジン</div></div>
  <div><div class="metric__v">0</div><div class="metric__l">外部に送るデータ</div></div>
</div>
```

数字は `--accent` の色になる。
2〜4個までが収まりがよい。

## 画像・スクリーンショットを置く

`.media` は画像を枠付きで置く。
`.split` の右側に入れると「左に説明、右に画面」になる。

```html
<div class="split split--narrow">
  <div class="body">左に説明。</div>
  <img class="media" src="screenshot.png" alt="">
</div>
```

画像は `slides.html` と同じディレクトリに置いて相対パスで参照する。
撮影時にローカルファイルとして読まれる。

## 全面に画像を敷く

スクリーンショットや写真を主役にする1枚。
下から地の色へグラデーションがかかるので、その上の文字が読める。

```html
<section class="slide slide--bleed" id="...">
  <img class="bleed__img" src="hero.png" alt="">
  <div class="bleed__body">
    <h2>画像の上に置く見出し</h2>
    <p class="lead">補足はここ。</p>
  </div>
</section>
```

**画像の中の文字は動画では読めない。**
全面画像は「雰囲気」か「一目で分かる図」に限り、細かい UI のスクショを全面に置かない。
それを見せたいなら `.split` の中で大きめに置き、ナレーションで指し示す。

## 組み合わせの例

モディファイアは重ねられる。

```html
<!-- 中央寄せの数字だけの1枚 -->
<section class="slide slide--center slide--middle" id="06-impact">
  <div class="slide__label">効果</div>
  <div class="metrics">…</div>
</section>

<!-- 実物を大きく、左右を入れ替えた具体例 -->
<div class="split split--wide split--flip">…</div>
```

## 新しいレイアウトを起こす

ここまでで足りないときだけ足す。
**構造側（`/* === THEME:START === */` より上）に書き、色は必ず `var(--...)` 経由にする。**
直に色を書くとテーマを差し替えても変わらない。

寸法は既存の体系に乗せる。
見出しは `var(--h2)`、本文 32〜40px、補足 28〜32px。
この3段階から外れると、そのスライドだけ浮く。

**1本の動画で使うレイアウトは3〜4種類まで。**
種類が増えるほど画面が落ち着かなくなる。
多くの部品が用意されているのは、題材ごとに適した3〜4種類が違うからであって、1本に全部入れるためではない。
