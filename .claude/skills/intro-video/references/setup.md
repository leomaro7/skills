# 環境要件と、詰まったときの対処

## 必要なもの

| 用途 | 要件 | 導入 |
|---|---|---|
| 動画の結合 | `ffmpeg` / `ffprobe` | macOS: `brew install ffmpeg`<br>Windows: `winget install Gyan.FFmpeg` |
| スライドの撮影 | Python の `playwright` | `pip install playwright`（ブラウザは後述） |
| 音声合成（既定） | OS 標準機能のみ | 追加インストール不要 |
| 音声合成（ローカルニューラル） | `piper-tts` + `pyopenjtalk` | `pip install piper-tts pyopenjtalk`（任意） |
| 音声合成（VOICEVOX） | VOICEVOX エンジン | アプリを起動しておく（任意） |
| 音声合成（Edge） | `edge-tts` | `pipx install edge-tts`（任意） |

既定の構成ではネットワークも API キーも要らない。外部サービスに素材を送らないので、社内資料をそのまま素材にできる。音声エンジンに `neural` を選んだ場合だけ、台本が外部に送信される（下記）。

## ブラウザ

`shoot_slides.py` は次の順に起動を試すので、どれか一つあればよい。

1. Playwright 同梱の Chromium（`python -m playwright install chromium` で導入）
2. インストール済みの Google Chrome
3. インストール済みの Microsoft Edge（Windows なら標準で入っている）

つまり Windows では、`pip install playwright` だけで Edge を使って撮影できる。

## Windows で動くか

macOS と Windows の両方を前提に作ってあるが、**開発と検証は macOS で行っている。** Windows 固有の経路（PowerShell での音声合成など）は実機での確認が済んでいない。下表の「要ビルド」「未検証」は、最初に使うときに詰まる可能性がある箇所。

| 機能 | Windows | 備考 |
|---|---|---|
| スライド撮影 | ○ | 標準搭載の Edge を使うので `pip install playwright` だけでよい |
| 動画の結合 | ○ | `winget install Gyan.FFmpeg`。導入後はシェルを開き直す |
| テーマ・配置・図 | ○ | HTML と CSS だけなので OS に依存しない |
| `check_narration.py` / `apply_theme.py` | ○ | 純粋な Python |
| `--engine os` | △ | 日本語の音声パックを追加する必要がある（後述） |
| `--engine local`（piper） | △ | **`pyopenjtalk` に Windows ホイールが無く、ソースビルドに MSVC Build Tools と CMake が要る** |
| `--engine voicevox` | ○（未検証） | インストーラで入る。ビルド不要 |
| `--engine neural`（edge-tts） | ○ | `pipx install edge-tts` |

**Windows で「オフラインのまま自然な声」を使うなら、`local` ではなく `voicevox` を選ぶ。** piper 側は `pyopenjtalk` のビルドで詰まりやすく、そこを越えられる環境でなければ勧められない（macOS と Linux ではホイールが無くても標準の開発ツールでビルドが通る）。

## 音声エンジン

4つある。**選ぶ基準の第一は声の good/bad ではなく、台本を外部に送ってよいかどうか。**

| | 台本の送信先 | 準備 | 読み上げ速度 |
|---|---|---|---|
| `os`（既定） | なし | 不要 | 約6.2文字/秒 |
| `local` | なし（初回のモデル取得のみ） | `pip install piper-tts pyopenjtalk` | 約6.2文字/秒 |
| `voicevox` | なし（localhost のみ） | VOICEVOX を起動 | 話者による |
| `neural` | **Microsoft** | `pipx install edge-tts` | 約5.2文字/秒 |

### `--engine os`（既定）

OS にもとから入っている音声合成を使う。ネットワーク不要で、台本が端末の外に出ない。

| OS | 使う仕組み | 既定の日本語音声 |
|---|---|---|
| macOS | `say` コマンド | Kyoko |
| Windows | PowerShell の `System.Speech` | Haruka（日本語音声パックが必要） |
| Linux | `espeak-ng` | 品質が低いので非推奨 |

### `--engine local`

piper（VITS ベースのローカル推論）で合成する。**OS 標準より自然で、かつ台本が端末から出ない。** 機密性のある資料を扱うなら、まずこれを検討する。

```bash
pip install piper-tts pyopenjtalk
python scripts/build_video.py ... --engine local
```

**Windows では `pyopenjtalk` のインストールにソースビルドが要る**（PyPI にホイールが無い）。MSVC Build Tools と CMake が入っていない環境では失敗するので、その場合は `voicevox` を使う。

日本語モデル（既定 `ja_JA-hi_fi_captain-medium`、約80MB）は初回に自動で取得する。**そこだけ通信するが、以降は完全にオフラインで動く。** モデルの置き場所は `INTRO_VIDEO_PIPER_DIR` で変えられる（既定 `~/.cache/intro-video/piper`）。

`pyopenjtalk` は日本語の音素化に必須で、これが無いと合成が失敗する。ビルド時に C++ をコンパイルするので、初回のインストールに少し時間がかかる。

利用できるモデルは `python -m piper.download_voices` で一覧できる。日本語のモデルは今のところ多くない。

### `--engine voicevox`

起動中の VOICEVOX エンジンに HTTP で合成させる。**日本語に特化している分、最も自然に聞こえる。** 台本は localhost から出ない。

```bash
# VOICEVOX アプリ（または voicevox_engine）を起動しておく
python scripts/build_video.py ... --engine voicevox --voice 3
```

`--voice` には話者 ID（数値）を渡す。省略すると、起動中のエンジンから利用できる話者の一覧を表示して止まるので、そこから選ぶ。接続先は `VOICEVOX_URL` で変えられる（既定 `http://127.0.0.1:50021`）。

**話者ごとに利用条件が定められている**（クレジット表記の要否、商用利用の可否など）。社外に公開する動画に使う場合は、VOICEVOX 公式および各話者の規約を確認すること。

### `--engine neural`

Microsoft Edge の読み上げ用ニューラル音声を使う。日本語は `ja-JP-NanamiNeural`（女性・既定）と `ja-JP-KeitaNeural`（男性）。

```bash
pipx install edge-tts        # PEP 668 で system pip が塞がれている環境でも入る
python scripts/build_video.py ... --engine neural --voice ja-JP-KeitaNeural
```

**台本が `speech.platform.bing.com` に送信される。** これは Edge ブラウザが内部的に使っているエンドポイントで、Azure の正規契約経路ではない。データの取り扱いが契約で担保されず、Microsoft 側の仕様変更で予告なく止まる可能性もある。**社外に出せない素材では使わない。** 業務で恒常的に使うなら、Azure Speech の正規契約に載せ替えるほうが筋が通る。

### 音声を変える

音声を変えたいときは `--voice` で指定する。利用できる音声の一覧は次で確認できる。

```bash
# macOS
say -v '?'

# Windows (PowerShell)
Add-Type -AssemblyName System.Speech
(New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices() |
  ForEach-Object { $_.VoiceInfo.Name + "  " + $_.VoiceInfo.Culture.Name }
```

### Windows で日本語音声が見つからないと言われる

`System.Speech` は SAPI5 の「Desktop」音声しか見えないため、日本語の音声パックが入っていないと既定の英語音声で合成される（その旨の警告が出る）。**設定 → 時刻と言語 → 言語と地域 → 日本語 → 言語のオプション → 音声認識** から音声を追加する。

追加できない環境では、英語音声のまま日本語を読ませても意味が通らない。その場合は台本をローマ字化するのではなく、**音声なしのスライド資料として PNG だけ使う**ほうが実用的なので、そう提案する。

## つまずきやすい箇所

### 「スライドと台本の id が一致していません」で止まる

意図した失敗。id がずれたまま進むと、無音のスライドや台本の抜けた動画が**エラーなしで**出来上がってしまうため、結合前に止めている。メッセージにどちらの側に何が足りないかが出るので、`slides.html` の `id` 属性か `narration.json` の `id` を合わせる。

### 音声が途中で切れる / 最後まで喋らない

台本に制御文字や極端に長い一文が入っていないか確認する。それでも切れる場合は、そのスライドの台本を二つに分けてスライドも分割する。

### スライドの文字が想定と違うフォントで写る

`assets/template.html` の `--font` は macOS（ヒラギノ）と Windows（游ゴシック / メイリオ）の両方をカバーしているが、いずれも無い環境ではシステムフォントにフォールバックする。レイアウト崩れが起きたら `build/frames/*.png` を見て、フォントサイズを調整する。

### 動画が長すぎる

ビルドの最後に4分超の警告が出る。`build/timeline.json` を開き、`duration` が突出しているスライドから削る。全体を均等に削るより、長い1枚を分割または削除するほうが効く。

## 生成物を作り直す

```bash
# 台本だけ直した（スライドは撮り直さない）
python scripts/build_video.py --slides slides.html --narration narration.json \
    --outdir build --skip-shoot

# スライドだけ直した（音声は作り直さない）
python scripts/build_video.py --slides slides.html --narration narration.json \
    --outdir build --skip-narrate
```

## 調整できるもの

| オプション | 既定 | 用途 |
|---|---|---|
| `--speed` | 1.0 | 読み上げ速度の倍率。0.9 でゆっくり |
| `--lead` | 0.35 | スライド切り替えから発話開始までの間（秒） |
| `--tail` | 0.9 | 発話終了から次のスライドまでの間（秒） |
| `--voice` | OS の日本語音声 | 音声名 |
| `--lufs` | -16 | 音量の正規化目標。結合時に全体を通して EBU R128 で揃える。音声合成の出力はそのままだと他の動画より小さいため既定で有効 |
| `--engine` | os | `os` / `local` / `voicevox` / `neural`。上記を参照 |
| `--fps` | 30 | フレームレート |
| `--width` / `--height` | 1920 / 1080 | 解像度 |
