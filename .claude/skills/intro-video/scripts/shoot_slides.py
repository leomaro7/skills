#!/usr/bin/env python3
"""スライド HTML を 1 枚ずつ PNG に書き出す。

HTML 内の `<section class="slide" id="...">` を 1 枚として扱い、id をファイル名
にする。ナレーション台本側の id と突き合わせるので、id は両者で一致させること。

  python shoot_slides.py slides.html --outdir build/frames
"""
import argparse
import sys
from pathlib import Path


def die(msg: str) -> "NoReturn":  # noqa: F821
    print(f"[shoot] エラー: {msg}", file=sys.stderr)
    sys.exit(1)


def launch(p, width: int, height: int):
    """まず同梱 Chromium、無ければ OS の Chrome / Edge を使う。

    `playwright install` を済ませていない環境でも動くようにしておくと、
    スキルが「まず依存を入れてください」で止まらずに済む。
    """
    attempts = [
        ("chromium (bundled)", {}),
        ("Google Chrome", {"channel": "chrome"}),
        ("Microsoft Edge", {"channel": "msedge"}),
    ]
    errors = []
    for label, kwargs in attempts:
        try:
            return p.chromium.launch(**kwargs)
        except Exception as e:  # noqa: BLE001
            errors.append(f"  - {label}: {str(e).splitlines()[0]}")
    die("ブラウザを起動できませんでした。`python -m playwright install chromium` を実行するか、"
        "Chrome / Edge をインストールしてください。\n" + "\n".join(errors))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("html", type=Path)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        die("playwright が入っていません。`pip install playwright` を実行してください。")

    if not args.html.exists():
        die(f"{args.html} が見つかりません。")
    args.outdir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = launch(p, args.width, args.height)
        page = browser.new_page(
            viewport={"width": args.width, "height": args.height},
            device_scale_factor=1)
        page.goto(args.html.resolve().as_uri())
        page.wait_for_load_state("networkidle")
        # Web フォント読み込み中に撮ると別のフォントで写るので待つ。
        page.evaluate("() => document.fonts.ready")
        page.wait_for_timeout(300)

        sections = page.query_selector_all("section.slide")
        if not sections:
            die('<section class="slide"> が 1 つも見つかりません。'
                "テンプレートの構造を崩していないか確認してください。")

        ids = []
        for i, section in enumerate(sections, 1):
            sid = section.get_attribute("id") or f"slide-{i:02d}"
            if sid in ids:
                die(f'id が重複しています: "{sid}"。スライドの id は一意にしてください。')
            ids.append(sid)
            section.screenshot(path=str(args.outdir / f"{sid}.png"))
            print(f"[shoot] {sid}.png")
        browser.close()

    print(f"[shoot] {len(ids)} 枚を {args.outdir} に書き出しました。")


if __name__ == "__main__":
    main()
