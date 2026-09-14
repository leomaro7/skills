#!/usr/bin/env python3
"""スライド HTML のテーマを差し替える。

  python apply_theme.py slides.html --theme dark
  python apply_theme.py --list

テンプレートは「構造」と「テーマ」に分かれていて、テーマ側が色・書体・余白・角の
丸みなどを持つ。内容を書いたあとでも差し替えられるので、同じ台本のまま見た目だけ
変えて比べられる。

ブランド色を1色だけ当てたいときは --accent を渡す（テーマの差し色を上書きする）。
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
THEMES = HERE.parent / "assets" / "themes"
START, END = "/* === THEME:START === */", "/* === THEME:END === */"


def die(msg: str) -> "NoReturn":  # noqa: F821
    print(f"[theme] エラー: {msg}", file=sys.stderr)
    sys.exit(1)


def available() -> list[str]:
    return sorted(p.stem for p in THEMES.glob("*.css"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slides", type=Path, nargs="?", help="スライド HTML")
    ap.add_argument("--theme", help=f"テーマ名（{', '.join(available())}）")
    ap.add_argument("--accent", help="差し色だけを上書きする（例: #0b6bcb）")
    ap.add_argument("--list", action="store_true", help="テーマの一覧と説明を表示する")
    args = ap.parse_args()

    if args.list or not args.slides:
        print("使えるテーマ:\n")
        for name in available():
            first = (THEMES / f"{name}.css").read_text(encoding="utf-8").splitlines()[0]
            desc = first.split("—", 1)[1].strip().rstrip("*/ ") if "—" in first else ""
            print(f"  {name:<11} {desc}")
        print("\n  python apply_theme.py slides.html --theme <名前>")
        return

    if not args.theme and not args.accent:
        die("--theme か --accent のどちらかを指定してください。")
    if not args.slides.exists():
        die(f"{args.slides} が見つかりません。")

    html = args.slides.read_text(encoding="utf-8")
    if START not in html or END not in html:
        die(f"{args.slides} にテーマの差し替え位置（{START}）がありません。"
            "assets/template.html から作り直したスライドでのみ使えます。")

    if args.theme:
        css_path = THEMES / f"{args.theme}.css"
        if not css_path.exists():
            die(f'テーマ "{args.theme}" はありません。使えるのは: {", ".join(available())}')
        block = css_path.read_text(encoding="utf-8").strip()
    else:
        block = html.split(START, 1)[1].split(END, 1)[0].strip()

    if args.accent:
        if not re.fullmatch(r"#[0-9a-fA-F]{3,8}", args.accent):
            die(f'差し色は #rrggbb 形式で指定してください（受け取った値: "{args.accent}"）')
        new, n = re.subn(r"(--accent:\s*)[^;]+;", rf"\g<1>{args.accent};", block, count=1)
        if not n:
            die("テーマに --accent の定義が見つかりませんでした。")
        block = new
        # 強調の下線もテーマの差し色に追従させないと、そこだけ元の色が残る。
        block = re.sub(r"box-shadow:\s*inset 0 -0\.1\dem 0 rgba\([^)]*\)",
                       f"box-shadow: inset 0 -0.13em 0 {args.accent}33", block)

    shutil.copyfile(args.slides, args.slides.with_suffix(".html.bak"))
    head, rest = html.split(START, 1)
    _, tail = rest.split(END, 1)
    args.slides.write_text(f"{head}{START}\n{block}\n{END}{tail}", encoding="utf-8")

    label = args.theme or "（テーマは据え置き）"
    extra = f" / 差し色 {args.accent}" if args.accent else ""
    print(f"[theme] {args.slides} を {label}{extra} に変更しました。")
    print(f"[theme] 変更前は {args.slides.with_suffix('.html.bak')} に残しています。")
    print("[theme] 撮り直し: build_video.py ... --skip-narrate")


if __name__ == "__main__":
    main()
