#!/usr/bin/env python3
"""スライド HTML とナレーション台本から、音声付き mp4 を組み立てる。

  python build_video.py --slides slides.html --narration narration.json \
      --outdir build --out intro.mp4

撮影(shoot_slides.py) → 音声合成(narrate.py) → ffmpeg での結合、を一度に流す。
途中成果物（PNG / WAV）は outdir に残すので、台本だけ直して --skip-shoot で
作り直す、といった部分的なやり直しができる。

結合は 1 回の ffmpeg で行い、各スライドの尺はその音声の長さから決め打ちする。
以前はスライドごとに mp4 を作って連結していたが、-shortest が画像ループを正確に
切らないため映像が音声より長くなり、連結するとズレが累積して終盤で音声が先行し
きってしまう（最後が無音になる）という不具合があった。尺を明示することでこの
クラスの不具合がまとめて消える。
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def die(msg: str) -> "NoReturn":  # noqa: F821
    print(f"[build] エラー: {msg}", file=sys.stderr)
    sys.exit(1)


def run(cmd: list[str], what: str) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or proc.stdout).strip().splitlines()[-15:])
        die(f"{what} に失敗しました。\n{tail}")


def ffprobe_duration(path: Path) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        die(f"{path} の長さを取得できませんでした。")
    return float(proc.stdout.strip())


def apply_brief(ap: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """brief.json の決定を反映し、そこで決めた方針に反するビルドを止める。

    ブリーフは「着手前にユーザーと確認したこと」の記録なので、ここを単なる既定値の
    置き場にせず、約束を守らせる場所にしている。特に external_ok は、台本を外部の
    サービスに送ってよいかという判断で、後から覆ると取り返しがつかない。
    """
    if not args.brief:
        if args.engine == "neural":
            print("[build] 注意: --engine neural は台本を Microsoft に送信します。"
                  "素材を外部に出してよいか確認済みであることを前提に続行します。")
        return
    try:
        brief = json.loads(args.brief.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        die(f"{args.brief} を読めません: {e}")

    given = {a.dest for a in ap._actions
             if any(o in sys.argv for o in a.option_strings)}
    for key in ("engine", "voice", "speed"):
        if key in brief and key not in given:
            setattr(args, key, brief[key])

    external_ok = brief.get("external_ok")
    if args.engine == "neural":
        if external_ok is None:
            die("--engine neural を使うには、ブリーフに external_ok を書いてください。"
                "台本が Microsoft に送信されるので、素材を外部に出してよいかの判断が要ります。")
        if external_ok is False:
            die("ブリーフで external_ok が false になっています。"
                "台本を外部に送れないので --engine neural は使えません。\n"
                "  macOS / Linux: --engine local   Windows: --engine voicevox   "
                "どちらも不可なら --engine os")
    print(f"[build] ブリーフ: {args.brief}（engine={args.engine}"
          f"{', external_ok=' + str(external_ok) if external_ok is not None else ''}）")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--brief", type=Path, default=None,
                    help="着手前に確定させたブリーフ（brief.json）。engine・voice・speed の"
                         "既定値をここから読む。個別のオプションを渡せばそちらが優先される")
    ap.add_argument("--slides", type=Path, default=None,
                    help="スライド HTML（--frames を使う場合は不要）")
    ap.add_argument("--frames", type=Path, default=None,
                    help="外部で作ったスライド画像のディレクトリ。Canva・Keynote・"
                         "PowerPoint・Figma などから書き出した PNG/JPG をそのまま使う")
    ap.add_argument("--pad-color", default="#faf9f7",
                    help="画像の比率が出力と違うときに余白を埋める色")
    ap.add_argument("--narration", type=Path, required=True, help="ナレーション台本 JSON")
    ap.add_argument("--outdir", type=Path, default=Path("build"))
    ap.add_argument("--out", type=Path, default=None, help="出力 mp4（既定: <outdir>/intro.mp4）")
    ap.add_argument("--engine", choices=("os", "local", "voicevox", "neural"), default="os",
                    help="os: OS標準（既定・オフライン）／ local: piper（オフライン）／ "
                         "voicevox: 起動中の VOICEVOX（オフライン）／ "
                         "neural: Edge（台本を外部に送信する）")
    ap.add_argument("--voice", default=None)
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--lead", type=float, default=0.35, help="各スライドの発話前の間（秒）")
    ap.add_argument("--tail", type=float, default=0.9, help="各スライドの発話後の間（秒）")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--lufs", type=float, default=-16.0,
                    help="音量の正規化目標（LUFS）。既定 -16")
    ap.add_argument("--skip-shoot", action="store_true", help="PNG を作り直さない")
    ap.add_argument("--skip-narrate", action="store_true", help="WAV を作り直さない")
    args = ap.parse_args()

    apply_brief(ap, args)

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            die(f"{tool} が見つかりません。macOS: `brew install ffmpeg` / "
                "Windows: `winget install Gyan.FFmpeg` で導入してください。")

    if not args.slides and not args.frames:
        die("--slides（スライド HTML）か --frames（スライド画像のディレクトリ）の"
            "どちらかが必要です。")

    outdir = args.outdir
    frames, audio = outdir / "frames", outdir / "audio"
    if args.frames:
        # 外部ツールで作ったスライドを使う。撮影は不要になる。
        frames = args.frames
        args.skip_shoot = True
    out_mp4 = args.out or (outdir / "intro.mp4")
    outdir.mkdir(parents=True, exist_ok=True)

    try:
        slides = json.loads(args.narration.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        die(f"{args.narration} を読めません: {e}")

    py = sys.executable
    if not args.skip_shoot and args.slides:
        run([py, str(HERE / "shoot_slides.py"), str(args.slides), "--outdir", str(frames),
             "--width", str(args.width), "--height", str(args.height)], "スライドの撮影")
    if not args.skip_narrate:
        cmd = [py, str(HERE / "narrate.py"), str(args.narration),
               "--outdir", str(audio), "--speed", str(args.speed), "--engine", args.engine]
        if args.voice:
            cmd += ["--voice", args.voice]
        run(cmd, "音声合成")

    # スライド画像と台本の突き合わせ。ずれたまま進むと無音や黒画面の動画が
    # エラーなしで出来上がってしまうので、結合前に必ず止める。
    exts = (".png", ".jpg", ".jpeg")

    def natural_key(path: Path):
        # 単純な文字列順だと "Slide 10" が "Slide 2" より前に来る。外部ツールの
        # 書き出しは連番名が多いので、数字は数値として比較する。
        return [int(t) if t.isdigit() else t.lower()
                for t in re.split(r"(\d+)", path.name)]

    pool = sorted((p for p in frames.glob("*") if p.suffix.lower() in exts),
                  key=natural_key)
    by_id = {p.stem: p for p in pool}

    frame_of: dict[str, Path] = {}
    if all(s["id"] in by_id for s in slides):
        frame_of = {s["id"]: by_id[s["id"]] for s in slides}
        orphan = set(by_id) - {s["id"] for s in slides}
        if orphan and not args.frames:
            die("スライドと台本の id が一致していません。\n" + "\n".join(
                f'  - スライドにある "{sid}" が台本に無い（ナレーション未執筆）'
                for sid in sorted(orphan)))
    elif args.frames and len(pool) == len(slides):
        # 外部ツールの書き出しはファイル名が連番のことが多い。枚数が一致していれば
        # 名前順に台本と対応づける（どの画像がどのスライドになったかは表示する）。
        frame_of = {s["id"]: p for s, p in zip(slides, pool)}
        print("[build] 画像を名前順で台本に対応づけます:")
        for s, p in zip(slides, pool):
            print(f"        {p.name}  →  {s['id']}")
    else:
        lines = [f'  - スライド "{s["id"]}" に対応する画像が無い'
                 for s in slides if s["id"] not in by_id]
        if args.frames:
            lines.append(f"  - 画像 {len(pool)} 枚 / 台本 {len(slides)} 枚。"
                         "枚数を合わせるか、画像のファイル名を台本の id にする")
        die("スライド画像と台本が対応していません。\n" + "\n".join(lines))

    missing = [f'  - スライド "{s["id"]}" の WAV が無い'
               for s in slides if not (audio / f"{s['id']}.wav").exists()]
    if missing:
        die("音声が足りません。\n" + "\n".join(missing))

    # --- 各スライドの尺を音声から確定する ---
    n = len(slides)
    durs, timeline, cursor = [], [], 0.0
    for slide in slides:
        sid = slide["id"]
        speech = ffprobe_duration(audio / f"{sid}.wav")
        seg = round(args.lead + speech + args.tail, 3)
        durs.append(seg)
        timeline.append({"id": sid, "start": round(cursor, 3), "duration": seg,
                         "speech": round(speech, 3), "narration": slide.get("narration", "")})
        cursor += seg
        print(f"[build] {sid}: {seg:.1f}s（発話 {speech:.1f}s）")

    # --- 1回の ffmpeg で組み立てる ---
    # 入力 0..n-1 が静止画（尺を -t で固定）、n..2n-1 がそのスライドの音声。
    inputs: list[str] = []
    for i, slide in enumerate(slides):
        inputs += ["-loop", "1", "-framerate", str(args.fps), "-t", f"{durs[i]:.3f}",
                   "-i", str(frame_of[slide["id"]])]
    for slide in slides:
        inputs += ["-i", str(audio / f"{slide['id']}.wav")]

    delay = int(round(args.lead * 1000))
    filt: list[str] = []
    for i in range(n):
        # concat は全入力の解像度が揃っていることを要求する。外部ツールの書き出しは
        # 比率も解像度もまちまちなので、はみ出さないよう縮めてから余白で埋める。
        filt.append(
            f"[{i}:v]scale={args.width}:{args.height}:force_original_aspect_ratio=decrease,"
            f"pad={args.width}:{args.height}:(ow-iw)/2:(oh-ih)/2:color={args.pad_color},"
            f"fps={args.fps},format=yuv420p,setsar=1[v{i}]")
        # 発話の前に lead、後ろに tail の無音を足し、スライドの尺ちょうどに揃える。
        filt.append(
            f"[{n + i}:a]adelay={delay}|{delay},apad=whole_dur={durs[i]:.3f},"
            f"atrim=0:{durs[i]:.3f},aresample=48000,"
            f"aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}]")
    filt.append("".join(f"[v{i}][a{i}]" for i in range(n)) +
                f"concat=n={n}:v=1:a=1[vcat][acat]")
    # 音声合成の出力はそのままだと他の動画より明らかに小さい。スライド単位ではなく
    # 通しの音声に対して正規化しないと、台本の長短で枚ごとに音量が揺れる。
    filt.append(f"[acat]loudnorm=I={args.lufs}:TP=-1.5:LRA=11[aout]")

    print("[build] 結合中...")
    # フィルタはファイル経由で渡す。枚数が増えても Windows のコマンドライン長
    # 制限（32767文字）に当たらず、引用符の扱いの環境差も無くなる。
    filt_file = outdir / "filter.txt"
    filt_file.write_text(";".join(filt), encoding="utf-8")
    run(["ffmpeg", "-y"] + inputs + ["-filter_complex_script", str(filt_file),
         "-map", "[vcat]", "-map", "[aout]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-movflags", "+faststart", str(out_mp4)], "動画の結合")

    (outdir / "timeline.json").write_text(
        json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")

    # 映像と音声の長さが揃っているかを確認する。ここがずれていると、再生時に
    # 「途中で音が切れる」形で表面化する。
    v = ffprobe_duration(out_mp4)
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
         "stream=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(out_mp4)],
        capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    a = float(proc.stdout.strip()) if proc.stdout.strip() else 0.0
    if abs(v - a) > 0.5:
        print(f"[build] 警告: 映像 {v:.1f}s と音声 {a:.1f}s の長さが揃っていません。")

    total = round(cursor, 1)
    print(f"\n[build] 完成: {out_mp4}  （{n}枚 / {total:.0f}秒 = "
          f"{int(total // 60)}分{int(total % 60):02d}秒 / 音声 {a:.0f}秒）")
    print(f"[build] 各スライドの開始時刻は {outdir / 'timeline.json'} にあります。")
    if total > 240:
        print("[build] 注意: 4分を超えています。紹介動画としては長いので、"
              "スライドを削るか台本を刈り込むことを検討してください。")


if __name__ == "__main__":
    main()
