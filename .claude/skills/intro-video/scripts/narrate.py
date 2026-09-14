#!/usr/bin/env python3
"""ナレーション台本(JSON)から、スライド1枚につき1本の WAV を生成する。

音声合成は OS 標準の機能だけを使う（macOS: say / Windows: System.Speech /
Linux: espeak-ng）。API キーもネットワークも要らないので、環境差でスキルが
止まらないことを優先している。

  python narrate.py narration.json --outdir build/audio
"""
import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def die(msg: str) -> "NoReturn":  # noqa: F821
    print(f"[narrate] エラー: {msg}", file=sys.stderr)
    sys.exit(1)


def _write_temp_text(text: str) -> Path:
    fd = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
    fd.write(text)
    fd.close()
    return Path(fd.name)


def synth_macos(text: str, out_wav: Path, voice: str | None, speed: float) -> None:
    # say の -r は words per minute。日本語話者 Kyoko の既定はおよそ 180。
    rate = max(90, min(400, int(round(180 * speed))))
    txt = _write_temp_text(text)
    try:
        cmd = ["say", "-v", voice or "Kyoko", "-r", str(rate),
               "-o", str(out_wav),
               "--file-format=WAVE", "--data-format=LEI16@24000",
               "-f", str(txt)]
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            die(f"say が失敗しました。指定した音声が存在しない可能性があります"
                f"（`say -v '?'` で一覧を確認）。\n{proc.stderr.strip()}")
    finally:
        txt.unlink(missing_ok=True)


PS_SCRIPT = r'''
$ErrorActionPreference = "Stop"
# 呼び出し側は UTF-8 で復号するので、出力側も UTF-8 に揃える。
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Speech
$text = [System.IO.File]::ReadAllText($env:NARRATE_TEXT_FILE, [System.Text.Encoding]::UTF8)
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$want = $env:NARRATE_VOICE
$selected = $null
if ($want) {
  $selected = $synth.GetInstalledVoices() |
    Where-Object { $_.VoiceInfo.Name -like "*$want*" } | Select-Object -First 1
}
if (-not $selected) {
  $selected = $synth.GetInstalledVoices() |
    Where-Object { $_.VoiceInfo.Culture.Name -eq "ja-JP" } | Select-Object -First 1
}
if ($selected) {
  $synth.SelectVoice($selected.VoiceInfo.Name)
} else {
  Write-Host "[narrate] 警告: 日本語音声が見つかりません。既定の音声で合成します。"
  Write-Host "[narrate] 設定 > 時刻と言語 > 音声認識 で日本語の音声パックを追加してください。"
}
$synth.Rate = [int]$env:NARRATE_RATE
$synth.SetOutputToWaveFile($env:NARRATE_OUT)
$synth.Speak($text)
$synth.Dispose()
'''


def synth_windows(text: str, out_wav: Path, voice: str | None, speed: float) -> None:
    # System.Speech の Rate は -10..10（0 が等速）。speed 倍率を素朴に写像する。
    rate = max(-10, min(10, int(round((speed - 1.0) * 10))))
    txt = _write_temp_text(text)
    fd, ps1_path = tempfile.mkstemp(suffix=".ps1")
    os.close(fd)          # 開いたままだと Windows で削除に失敗する
    ps1 = Path(ps1_path)
    # PowerShell 5.1 は BOM の無い .ps1 を ANSI（日本語環境では cp932）として読む。
    # UTF-8 のまま渡すとスクリプト内の日本語が化けるので BOM 付きで書く。
    ps1.write_text(PS_SCRIPT, encoding="utf-8-sig")
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        die("powershell が見つかりません。Windows 標準の PowerShell が必要です。")
    env = {
        "NARRATE_TEXT_FILE": str(txt),
        "NARRATE_OUT": str(out_wav.resolve()),
        "NARRATE_VOICE": voice or "",
        "NARRATE_RATE": str(rate),
    }
    merged = {**os.environ, **env}
    try:
        proc = subprocess.run(
            [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1)],
            capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=merged)
        if proc.stdout.strip():
            print(proc.stdout.strip())
        if proc.returncode != 0:
            die(f"PowerShell の音声合成が失敗しました。\n{proc.stderr.strip()}")
    finally:
        txt.unlink(missing_ok=True)
        ps1.unlink(missing_ok=True)


def synth_linux(text: str, out_wav: Path, voice: str | None, speed: float) -> None:
    if not shutil.which("espeak-ng"):
        die("Linux では espeak-ng が必要です（例: apt install espeak-ng）。"
            "日本語の品質は低いので、可能なら macOS / Windows で実行してください。")
    txt = _write_temp_text(text)
    try:
        wpm = max(80, min(300, int(round(150 * speed))))
        proc = subprocess.run(
            ["espeak-ng", "-v", voice or "ja", "-s", str(wpm),
             "-w", str(out_wav), "-f", str(txt)],
            capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            die(f"espeak-ng が失敗しました。\n{proc.stderr.strip()}")
    finally:
        txt.unlink(missing_ok=True)


def synth_neural(text: str, out_wav: Path, voice: str | None, speed: float) -> None:
    """Microsoft Edge の読み上げ用ニューラル音声で合成する（要ネットワーク）。

    OS 標準の音声合成には自然さの上限があり、「機械的に聞こえる」という印象は
    台本をどう書いても消せない。人が話しているように聞かせたい場合はこちらを使う。
    ただし台本のテキストは Microsoft のエンドポイントに送られるので、社外に出せ
    ない素材では使えない。その判断は呼び出し側でする。
    """
    voice = voice or "ja-JP-NanamiNeural"
    rate = f"{int(round((speed - 1.0) * 100)):+d}%"
    txt = _write_temp_text(text)
    mp3 = out_wav.with_suffix(".mp3")

    # CLI を優先する。pipx / venv / pip のどれで入れても動くようにしておくと、
    # PEP 668 で system pip が塞がれている環境でも詰まらない。
    cli = shutil.which("edge-tts")
    try:
        if cli:
            cmd = [cli, "-f", str(txt), "-v", voice, "--rate", rate,
                   "--write-media", str(mp3)]
        else:
            try:
                import edge_tts  # noqa: F401
            except ImportError:
                die("ニューラル音声には edge-tts が必要です。\n"
                    "  pipx install edge-tts   （推奨。PEP 668 の環境でも入る）\n"
                    "  または python -m venv .venv && .venv/bin/pip install edge-tts")
            cmd = [sys.executable, "-m", "edge_tts", "-f", str(txt), "-v", voice,
                   "--rate", rate, "--write-media", str(mp3)]
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        if proc.returncode != 0 or not mp3.exists() or mp3.stat().st_size < 512:
            die("ニューラル音声の生成に失敗しました。ネットワーク接続と音声名を確認してください"
                f"（`edge-tts --list-voices` で一覧）。\n{(proc.stderr or '').strip()}")
        # 以降の処理を OS 標準側と揃えるため WAV に変換する。
        conv = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(mp3), "-ar", "24000", "-ac", "1",
             str(out_wav)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        if conv.returncode != 0:
            die(f"音声の変換に失敗しました。\n{conv.stderr.strip()}")
    finally:
        txt.unlink(missing_ok=True)
        mp3.unlink(missing_ok=True)


PIPER_DEFAULT_MODEL = "ja_JA-hi_fi_captain-medium"


def _piper_dir() -> Path:
    d = Path(os.environ.get("INTRO_VIDEO_PIPER_DIR",
                            Path.home() / ".cache" / "intro-video" / "piper"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def synth_local(text: str, out_wav: Path, voice: str | None, speed: float) -> None:
    """piper でローカル合成する。台本は一切ネットワークに出ない。

    OS 標準の音声より自然で、かつ素材を外部に送らずに済む。機密性のある資料を
    扱うならこれが既定の選択になる。初回だけ音声モデル（約80MB）の取得に通信が
    要るが、そのあとは完全にオフラインで動く。
    """
    model = voice or PIPER_DEFAULT_MODEL
    data_dir = _piper_dir()
    if not (data_dir / f"{model}.onnx").exists():
        print(f"[narrate] 音声モデル {model} を取得します（初回のみ・約80MB）")
        dl = subprocess.run(
            [sys.executable, "-m", "piper.download_voices", model,
             "--data-dir", str(data_dir)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        if dl.returncode != 0 or not (data_dir / f"{model}.onnx").exists():
            die(f"音声モデル {model} を取得できませんでした。モデル名を確認してください"
                f"（`python -m piper.download_voices` で一覧）。\n{dl.stderr.strip()[-400:]}")

    cli = shutil.which("piper")
    base = [cli] if cli else [sys.executable, "-m", "piper"]
    # piper の length-scale は「音素の長さ」なので、速度倍率とは逆向きになる。
    cmd = base + ["--model", model, "--data-dir", str(data_dir),
                  "--length-scale", f"{1.0 / speed:.3f}",
                  "--output-file", str(out_wav)]
    proc = subprocess.run(cmd, input=text, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    if proc.returncode != 0 or not out_wav.exists():
        hint = ""
        if "pyopenjtalk" in (proc.stderr or ""):
            hint = ("\n日本語の音素化には pyopenjtalk が必要です: pip install pyopenjtalk"
                    "\nWindows では PyPI にホイールが無くソースビルドになります"
                    "（MSVC Build Tools と CMake が必要）。"
                    "ビルドできない環境では --engine voicevox を使ってください。")
        elif not cli:
            hint = "\npiper が入っていません: pip install piper-tts pyopenjtalk"
        die(f"ローカル合成に失敗しました。{hint}\n{(proc.stderr or '').strip()[-400:]}")


def synth_voicevox(text: str, out_wav: Path, voice: str | None, speed: float) -> None:
    """起動中の VOICEVOX エンジンで合成する。台本はローカルホストから出ない。

    日本語に特化している分、piper より自然に聞こえる。VOICEVOX アプリ（または
    voicevox_engine）を起動しておく必要がある。話者ごとに利用条件（クレジット
    表記など）が決められているので、公開する動画に使う場合は確認すること。
    """
    import json as _json
    import urllib.error
    import urllib.parse
    import urllib.request

    base = os.environ.get("VOICEVOX_URL", "http://127.0.0.1:50021").rstrip("/")

    def api(path: str, data: bytes | None = None, ctype: str | None = None):
        req = urllib.request.Request(f"{base}{path}", data=data, method="POST" if data is not None else "GET")
        if ctype:
            req.add_header("Content-Type", ctype)
        return urllib.request.urlopen(req, timeout=60)

    if not voice:
        try:
            speakers = _json.loads(api("/speakers").read())
        except Exception:  # noqa: BLE001
            die(f"VOICEVOX エンジンに接続できません（{base}）。VOICEVOX を起動してください。")
        lines = [f"    {st['id']:>3}  {sp['name']} / {st['name']}"
                 for sp in speakers for st in sp["styles"]]
        die("--voice に VOICEVOX の話者IDを指定してください。利用できる話者:\n"
            + "\n".join(lines[:60]))

    try:
        q = _json.loads(api(f"/audio_query?{urllib.parse.urlencode({'text': text, 'speaker': voice})}",
                            data=b"").read())
        q["speedScale"] = speed
        wav = api(f"/synthesis?{urllib.parse.urlencode({'speaker': voice})}",
                  data=_json.dumps(q).encode("utf-8"), ctype="application/json").read()
    except urllib.error.URLError as e:
        die(f"VOICEVOX エンジンに接続できません（{base}）。VOICEVOX を起動してください。\n{e}")
    except Exception as e:  # noqa: BLE001
        die(f"VOICEVOX での合成に失敗しました: {e}")
    out_wav.write_bytes(wav)


SYNTHS = {"Darwin": synth_macos, "Windows": synth_windows, "Linux": synth_linux}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("narration", type=Path, help="ナレーション台本 JSON")
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--engine", choices=("os", "local", "voicevox", "neural"), default="os",
                    help="os: OS標準（既定・オフライン・機械的）／ "
                         "local: piper のローカルニューラル音声（オフライン）／ "
                         "voicevox: 起動中の VOICEVOX（オフライン・日本語特化）／ "
                         "neural: Edge のニューラル音声（台本を外部に送信する）")
    ap.add_argument("--voice", default=None,
                    help="音声名（os: Kyoko / Haruka など、neural: ja-JP-NanamiNeural / "
                         "ja-JP-KeitaNeural）。既定は各エンジンの日本語音声")
    ap.add_argument("--speed", type=float, default=1.0,
                    help="読み上げ速度の倍率。既定 1.0（0.9 でゆっくり）")
    args = ap.parse_args()

    picked = {"neural": synth_neural, "local": synth_local, "voicevox": synth_voicevox}
    if args.engine in picked:
        synth = picked[args.engine]
    else:
        synth = SYNTHS.get(platform.system())
        if synth is None:
            die(f"未対応のプラットフォームです: {platform.system()}。"
                "--engine neural なら OS を問わず使えます。")

    try:
        slides = json.loads(args.narration.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        die(f"{args.narration} が JSON として読めません: {e}")
    if not isinstance(slides, list) or not slides:
        die("台本 JSON は [{\"id\": ..., \"narration\": ...}, ...] の配列である必要があります。")

    args.outdir.mkdir(parents=True, exist_ok=True)
    for i, slide in enumerate(slides, 1):
        sid = slide.get("id")
        text = (slide.get("narration") or "").strip()
        if not sid:
            die(f"{i} 番目のスライドに id がありません。")
        if not text:
            die(f"スライド {sid} の narration が空です。無音のスライドは作れません。")
        out = args.outdir / f"{sid}.wav"
        synth(text, out, args.voice, args.speed)
        if not out.exists() or out.stat().st_size < 1024:
            die(f"スライド {sid} の音声生成に失敗しました（出力が空）。")
        print(f"[narrate] {sid}.wav ({len(text)}文字)")

    print(f"[narrate] {len(slides)} 本の音声を {args.outdir} に生成しました。")


if __name__ == "__main__":
    main()
