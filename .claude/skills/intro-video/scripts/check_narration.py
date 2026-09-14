#!/usr/bin/env python3
"""台本をビルド前に検査する。

ビルドには数十秒かかり、ニューラル音声では毎回ネットワークに出る。尺の超過や
読みにくい文は文字数から先に分かるので、作る前に潰しておく。

  python check_narration.py narration.json --minutes 2.5 --engine neural
"""
import argparse
import json
import re
import sys
from pathlib import Path

# 実測値。同じ台本でもエンジンによって2割ほど尺が変わる。
# 実測値。voicevox は話者によって変わるので local と同じ目安を使う。
CPS = {"os": 6.2, "local": 6.2, "voicevox": 6.0, "neural": 5.2}
PAD_PER_SLIDE = 1.25          # build_video.py の lead + tail の既定
MAX_CHARS_PER_SLIDE = 150
MAX_CHARS_PER_SENTENCE = 60


def tail_expression(text: str) -> str:
    """最後の文の文末表現（句点の直前4文字）を返す。単調さの検出に使う。"""
    sentences = [x for x in re.split(r"[。！？]", text) if x.strip()]
    return sentences[-1][-4:] if sentences else ""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("narration", type=Path)
    ap.add_argument("--minutes", type=float, default=None,
                    help="目標の尺（分）。指定すると過不足を判定する")
    ap.add_argument("--engine", choices=("os", "local", "voicevox", "neural"), default="os")
    ap.add_argument("--brief", type=Path, default=None,
                    help="brief.json。minutes と engine の既定値をここから読む")
    args = ap.parse_args()

    # 尺の見積もりはエンジンによって2割変わる。ブリーフで決めた条件をそのまま
    # 使わないと、検査を通ったのにビルドすると尺が合わない、ということが起きる。
    if args.brief:
        try:
            brief = json.loads(args.brief.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"エラー: {args.brief} を読めません: {e}", file=sys.stderr)
            sys.exit(1)
        given = {o for a in ap._actions for o in a.option_strings if o in sys.argv}
        if "--minutes" not in given and "minutes" in brief:
            args.minutes = brief["minutes"]
        if "--engine" not in given and "engine" in brief:
            args.engine = brief["engine"]

    try:
        slides = json.loads(args.narration.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"エラー: {args.narration} を読めません: {e}", file=sys.stderr)
        sys.exit(1)

    cps = CPS[args.engine]
    problems, notes = [], []
    total_chars = total_sec = 0.0
    prev_tail = prev_prev_tail = None

    print(f"{'id':<16}{'文字':>6}{'推定':>8}   所見")
    print("-" * 62)
    for slide in slides:
        sid, text = slide.get("id", "?"), (slide.get("narration") or "").strip()
        if not text:
            problems.append(f'{sid}: narration が空。無音のスライドは作れない')
            continue
        n = len(text)
        sec = n / cps + PAD_PER_SLIDE
        total_chars += n
        total_sec += sec

        remarks = []
        if n > MAX_CHARS_PER_SLIDE:
            remarks.append(f"長い({n}字)")
            problems.append(f"{sid}: {n}文字。1枚が長すぎるのでスライドを分けるか削る")
        long_sents = [s for s in re.split(r"(?<=[。！？])", text)
                      if len(s.strip()) > MAX_CHARS_PER_SENTENCE]
        if long_sents:
            remarks.append(f"長文{len(long_sents)}")
            problems.append(f"{sid}: {len(long_sents)}文が{MAX_CHARS_PER_SENTENCE}字超。"
                            f"接続助詞で切る → 「{long_sents[0].strip()[:34]}…」")

        t = tail_expression(text)
        if t and t == prev_tail == prev_prev_tail:
            remarks.append("文末3連続")
            notes.append(f"{sid}: 文末「{t}」が3枚続く。通しで聞くと単調になる")
        prev_prev_tail, prev_tail = prev_tail, t

        print(f"{sid:<16}{n:>6}{sec:>7.1f}s   {'・'.join(remarks)}")

    print("-" * 62)
    mm, ss = int(total_sec // 60), int(total_sec % 60)
    print(f"{'合計':<16}{int(total_chars):>6}{total_sec:>7.1f}s   "
          f"{mm}分{ss:02d}秒 / {len(slides)}枚 （{args.engine}）")

    if args.minutes:
        target = args.minutes * 60
        diff = total_sec - target
        pct = diff / target * 100
        print(f"\n目標 {args.minutes}分 との差: {diff:+.0f}秒 ({pct:+.0f}%)")
        if abs(pct) > 15:
            verb = "削る" if diff > 0 else "足す"
            need = abs(diff) * cps
            problems.append(f"目標より{abs(diff):.0f}秒{'長い' if diff > 0 else '短い'}。"
                            f"台本を約{need:.0f}文字{verb}")

    if problems:
        print("\n■ 直したほうがよい")
        for p in problems:
            print(f"  - {p}")
    if notes:
        print("\n■ 気に留める")
        for x in notes:
            print(f"  - {x}")
    if not problems and not notes:
        print("\n問題は見つかりませんでした。")

    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
