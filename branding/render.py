"""branding/ の HTML から docs/assets/ の OGP 画像とアイコンを生成する。

    python3 branding/render.py

文字と色は memo.config.json から読む（site_name・description・公開 URL と、"branding" の項目）。
設定を変えたらこれを実行し、できた画像をコミットして push する（og.png が変わると build が og:image の ?v= を更新する）。

要: playwright（と chromium: `python3 -m playwright install chromium`）、Pillow、
    フォント Noto Sans CJK JP / DejaVu Sans Mono（Ubuntu なら fonts-noto-cjk・fonts-dejavu-core）
memo.py 本体とは違い、こちらは標準ライブラリだけでは動かない（画像を作るときだけ使う）。
"""
import html
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ImportError as e:
    sys.exit(f"render.py に必要なパッケージがありません（{e.name}）。\n"
             "  pip install playwright pillow\n  python3 -m playwright install chromium")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
from memolib.config import ASSETS, branding, darken  # noqa: E402  設定の読み込みと置き場所・色の計算は memolib に任せる

# テーマごとの色。アクセント色はここに入らず、下の palette() で足す（dark は branding.accent、light は accent_light。ページと同じ色）
THEMES = {
    "dark": {"desk": "#0a0e14", "paper": "#111823", "rule": "#1e2d3d", "shadow": "#00000080",
             "text": "#cdd9e5", "muted": "#7d8b9d", "pen-ring": "#7d8b9d", "pen-grip": "#cdd9e5"},
    "light": {"desk": "#e6ebf1", "paper": "#ffffff", "rule": "#dde5ee", "shadow": "#1a2a3a33",
              "text": "#243042", "muted": "#6b7a8c", "pen-ring": "#8a97a8", "pen-grip": "#4a5868"},
}


def palette(b: dict) -> str:
    """CSS 変数の並び（style 属性に入れる）。"""
    accent = b["accent"] if b["theme"] == "dark" else b["accent_light"]
    colors = {**THEMES[b["theme"]], "margin": accent, "ink": accent, "pen-hi": accent, "pen": darken(accent, 0.8)}
    colors["holebg"] = colors["desk"]
    return ";".join(f"--{k}:{v}" for k, v in colors.items())


def mark_size(mark: str, small: bool) -> str:
    """アイコンの文字の大きさ。文字数が多いほど小さく、全角は半角 2 文字ぶんとして数える。"""
    width = sum(2 if ord(ch) > 0x2E7F else 1 for ch in mark) or 1
    base = 640 if small else 400
    return f"{round(base * min(1, 1.6 / width))}px"


# 画像に使うフォント（無いと別のフォントで描かれ、見た目が崩れる）
FONTS = ("Noto Sans CJK JP", "DejaVu Sans Mono")


def missing_fonts() -> list:
    """fc-list で見つからないフォント。fc-list が無い環境（macOS など）では確かめない。"""
    if not shutil.which("fc-list"):
        return []
    try:
        out = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    return [f for f in FONTS if f not in out]


def main():
    missing = missing_fonts()
    if missing:
        print(f"警告: フォントが見つかりません: {', '.join(missing)}（別のフォントで描かれます。"
              "Ubuntu なら apt install fonts-noto-cjk fonts-dejavu-core）", file=sys.stderr)
    b = branding()
    css = palette(b)
    esc = lambda s: html.escape(s, quote=True)  # noqa: E731
    og_tpl = (HERE / "og.html").read_text(encoding="utf-8")
    icon_tpl = (HERE / "icon.html").read_text(encoding="utf-8")
    tmp = HERE / "_tmp.html"
    shots = {}
    try:
        with sync_playwright() as p:
            try:
                br = p.chromium.launch()
            except PlaywrightError as e:
                sys.exit("chromium を起動できません。`python3 -m playwright install chromium` を実行してください"
                         f"（Linux で依存ライブラリが無いときは `python3 -m playwright install-deps chromium`）。\n{e}")
            pg = br.new_page(viewport={"width": 1200, "height": 630})
            tmp.write_text(og_tpl.replace("__VARS", css).replace("__TITLE", esc(b["title"]))
                           .replace("__TAGLINE", esc(b["tagline"])).replace("__URL", esc(b["url"])), encoding="utf-8")
            pg.goto(tmp.as_uri()); pg.wait_for_timeout(300)
            pg.screenshot(path=str(ASSETS / "og.png"))

            pg.set_viewport_size({"width": 1024, "height": 1024})
            for key, cls, holes in (("full", "", 5), ("small", "small t", 3)):
                tmp.write_text(icon_tpl.replace("__VARS", css).replace("__CLS", cls)
                               .replace("__HOLES", "<i></i>" * holes).replace("__MARK", esc(b["mark"]))
                               .replace("__MSIZE", mark_size(b["mark"], key == "small")), encoding="utf-8")
                pg.goto(tmp.as_uri()); pg.wait_for_timeout(200)
                out = HERE / f"_icon-{key}.png"
                pg.screenshot(path=str(out), omit_background=True)
                shots[key] = out
            br.close()

        full = Image.open(shots["full"]).convert("RGB")      # iOS は透過不可
        small = Image.open(shots["small"]).convert("RGBA")   # ファビコンは簡略・透過
        full.resize((180, 180), Image.LANCZOS).save(ASSETS / "apple-touch-icon.png")
        full.resize((192, 192), Image.LANCZOS).save(ASSETS / "icon-192.png")
        small.resize((32, 32), Image.LANCZOS).save(ASSETS / "icon-32.png")
        small.resize((48, 48), Image.LANCZOS).save(ASSETS / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    finally:
        for f in [tmp, *shots.values()]:
            if f.exists():
                os.remove(f)
    print(f"title={b['title']!r} mark={b['mark']!r} theme={b['theme']} accent={b['accent']} accent_light={b['accent_light']}")
    print("updated: og.png, apple-touch-icon.png, icon-192.png, icon-32.png, favicon.ico")


if __name__ == "__main__":
    main()
