"""置き場所・公開 URL・日付など、リポジトリ全体で共有する設定。

置き場所（src/・dist/ やテンプレートの場所）を知っているのはこのモジュールだけ。
src/ は原本（手で書く HTML と共通ファイル）だけを置く場所で、build は src/ を読むだけで書き換えない。
build の出力（公開するサイト一式）は dist/ に書き出す（.gitignore 済み。Actions が dist ブランチにデプロイする）。
サイトごとに変わる値（サイト名・リポジトリ・ブランチ・タイムゾーンなど）は
リポジトリ直下の memo.config.json に書き、ここで読み込む。コードやスキルに直接書かない。
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # scripts/memolib/ の 2 つ上
CONFIG_FILE = ROOT / "memo.config.json"
SRC = ROOT / "src"  # 原本の置き場所（build は読むだけ）
DIST = ROOT / "dist"  # build の出力。公開するサイト一式（GitHub Pages は dist ブランチから公開）
INDEX = SRC / "index.html"
SETTINGS_PAGE = SRC / "settings.html"  # 管理者がアクセント色を試して、固定する手順へ進むページ
ROADMAP_PAGE = SRC / "roadmap.html"  # 書いたメモ・これから書くテーマのチェックリスト（memos.json で自動でチェック）
# メモではない特別なページ（一覧に載せない・メモ名に使えない）。一覧データは memos.json から読み込む
SPECIAL_PAGES = (INDEX, SETTINGS_PAGE, ROADMAP_PAGE)
SPECIAL_NAMES = {p.name for p in SPECIAL_PAGES}
# 使うかどうかを memo.config.json で選ぶページ（{ファイル名: 設定の項目}）。オフのときは build が dist/ に出さず、
# ほかのページの data-memo-if="項目" の付いた要素（リンクなど）も取り除く
OPTIONAL_PAGES = {ROADMAP_PAGE.name: "roadmap"}

# memo.config.json の項目と、書かれていないときの値
DEFAULTS: dict = {
    "site_name": "MEMO",          # <title>・OGP・llms.txt の見出しなどに使うサイト名
    "description": "",            # トップページの説明（index.html と OGP）
    "llms_description": "",       # llms.txt の冒頭の説明
    "repository": "",             # GitHub の owner/name。公開 URL の既定値とリンクに使う
    "branch": "main",             # push 先のブランチ（スキルは `memo.py config branch` で読む）
    "deploy_branch": "dist",      # build の出力（dist/）をデプロイするブランチ。GitHub Pages の公開元にする
    "utc_offset_hours": 0,        # 「今日」を決めるタイムゾーン（日本なら 9）
    "branding": {},               # アクセント色と、アイコン・OGP 画像の文字・色。項目は BRANDING_DEFAULTS
    "roadmap": False,             # ロードマップ（src/roadmap.html）を公開して、トップページからリンクするか（オプション）
}

# memo.config.json の "branding" の項目。空文字は「ほかの設定から決める」
BRANDING_DEFAULTS: dict = {
    "title": "",        # OGP 画像の大きな文字（空なら site_name）
    "tagline": "",      # OGP 画像の説明文（空なら description）
    "url": "",          # OGP 画像に小さく出す URL（空なら公開 URL のホスト名とパス）
    "mark": "",         # アイコンの文字（1〜2 文字。空なら title の先頭 1 文字）
    "accent": "#00d4ff",  # アクセント色（ダークモードのページと dark の画像）。#rgb か #rrggbb
    "accent_light": "",   # ライトモードのページと light の画像のアクセント色（空なら accent を白地で読める濃さまで暗くする）
    "theme": "dark",    # 画像のテーマ。dark か light
}
THEMES = ("dark", "light")
HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}){1,2}$")


# 文字列の項目と、空を許さないもの
STRING_KEYS = ("site_name", "description", "llms_description", "repository", "branch", "deploy_branch")
BOOL_KEYS = ("roadmap",)
REQUIRED_STRINGS = ("site_name", "branch", "deploy_branch")
BRANDING_STRING_KEYS = ("title", "tagline", "url", "mark", "accent", "accent_light", "theme")


def _type_name(value) -> str:
    return {str: "文字列", bool: "true/false", int: "数値", float: "数値", list: "配列", dict: "オブジェクト",
            type(None): "null"}.get(type(value), type(value).__name__)


def load_config(path: Path = CONFIG_FILE) -> dict:
    """memo.config.json を読み、書き間違いがあれば直す場所が分かるメッセージで止める。"""
    name = path.name

    def fail(msg: str):
        raise SystemExit(f"{name}: {msg}")

    if not path.is_file():
        data = {}
    else:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            fail("UTF-8 で保存してください")
        except json.JSONDecodeError as e:
            fail(f"JSON の書き方が正しくありません（{e.lineno} 行 {e.colno} 文字目: {e.msg}）。"
                 "カンマの過不足・閉じ括弧・\"\" の囲み忘れがないか確認してください")
    if not isinstance(data, dict):
        fail("全体を { ... }（オブジェクト）で書いてください")
    unknown = sorted(set(data) - set(DEFAULTS))
    if unknown:
        fail(f"知らない項目があります: {', '.join(unknown)}（使える項目: {', '.join(DEFAULTS)}）")
    for key in STRING_KEYS:
        if key in data and not isinstance(data[key], str):
            fail(f"{key} は文字列（\"...\"）で書いてください（いまは{_type_name(data[key])}）")
    for key in BOOL_KEYS:
        if key in data and not isinstance(data[key], bool):
            fail(f"{key} は true か false で書いてください（いまは{_type_name(data[key])}）")
    for key in REQUIRED_STRINGS:
        if key in data and not data[key].strip():
            fail(f"{key} を空にはできません（書かなければ既定値 {DEFAULTS[key]!r} になります）")
    for key in ("branch", "deploy_branch"):
        if key in data and re.search(r"\s", data[key]):
            fail(f"{key} に空白は使えません: {data[key]!r}")
    if data.get("deploy_branch", DEFAULTS["deploy_branch"]) == data.get("branch", DEFAULTS["branch"]):
        fail("deploy_branch は branch と別のブランチにしてください（原本と build の出力を分けるため）")
    if "utc_offset_hours" in data:
        tz = data["utc_offset_hours"]
        if isinstance(tz, bool) or not isinstance(tz, (int, float)):
            fail(f"utc_offset_hours は数値で書いてください（例: 9。いまは{_type_name(tz)}）")
        if not -24 < tz < 24:
            fail(f"utc_offset_hours は -24 より大きく 24 より小さい数です（日本なら 9）: {tz}")

    brand = data.get("branding", {})
    if not isinstance(brand, dict):
        fail("branding はオブジェクト（{...}）で書いてください")
    unknown = sorted(set(brand) - set(BRANDING_DEFAULTS))
    if unknown:
        fail(f"branding に知らない項目があります: {', '.join(unknown)}（使える項目: {', '.join(BRANDING_DEFAULTS)}）")
    for key in BRANDING_STRING_KEYS:
        if key in brand and not isinstance(brand[key], str):
            fail(f"branding.{key} は文字列（\"...\"）で書いてください（いまは{_type_name(brand[key])}）")
    brand = {**BRANDING_DEFAULTS, **brand}
    for key in ("accent", "accent_light"):
        value = brand[key]
        if (value or key == "accent") and not HEX_RE.match(value):
            fail(f"branding.{key} は #rgb か #rrggbb で書いてください: {value!r}")
    if brand["theme"] not in THEMES:
        fail(f"branding.theme は {' / '.join(THEMES)} のどちらかです: {brand['theme']!r}")
    return {**DEFAULTS, **data, "branding": brand}


def read_text(path: Path) -> str:
    """メモや取り込む HTML を読む。UTF-8 で読めなければ、どのファイルかを示して止める。"""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        try:
            shown = path.resolve().relative_to(ROOT)
        except ValueError:
            shown = path
        raise SystemExit(f"{shown}: UTF-8 で読めません（{e.start} バイト目）。"
                         "UTF-8 で保存し直してください（Shift_JIS などは不可）") from None


CONFIG = load_config()
SITE_NAME: str = CONFIG["site_name"]
REPOSITORY: str = CONFIG["repository"]
BRANCH: str = CONFIG["branch"]
# 「今日」は設定のタイムゾーンで決める（実行環境の時計が UTC でも日付がずれないように）
TZ = dt.timezone(dt.timedelta(hours=CONFIG["utc_offset_hours"]))


# テンプレートのままの repository（書き換え忘れを build で警告する）
PLACEHOLDER_REPOSITORIES = {"repo/sample", "owner/repo"}


def repository_warning(repository: str = REPOSITORY) -> str:
    """repository が未設定・テンプレートのままなら警告文、問題なければ空文字。"""
    repo = repository.strip()
    if not repo:
        why = "が空です"
    elif repo.count("/") != 1 or not all(repo.split("/")):
        why = f"（{repo}）が owner/name の形ではありません"
    elif repo.lower() in PLACEHOLDER_REPOSITORIES:
        why = f"がテンプレートの値（{repo}）のままです"
    else:
        return ""
    return (f"警告: {CONFIG_FILE.name} の repository {why}。"
            "入口スキルの clone 先・トップページのリンク・公開 URL が正しくなりません。"
            "自分のリポジトリ（owner/name）に書き換えてください")


def set_accent(accent: str, accent_light: str = "", path: Path = CONFIG_FILE) -> dict:
    """memo.config.json の branding.accent・accent_light だけを書き換える（ほかの項目と並び順はそのまま）。
    accent_light が空なら項目を消し、accent から自動で決めさせる。
    書き換えた結果が設定として正しくなければ、ファイルを元に戻して止める。返り値は読み直した設定。"""
    original = path.read_text(encoding="utf-8") if path.is_file() else None
    data = json.loads(original) if original else {}
    if not isinstance(data, dict):
        raise SystemExit(f"{path.name}: 全体を {{ ... }}（オブジェクト）で書いてください")
    brand = data.get("branding")
    brand = dict(brand) if isinstance(brand, dict) else {}
    brand["accent"] = accent.strip()
    if accent_light.strip():
        brand["accent_light"] = accent_light.strip()
    else:
        brand.pop("accent_light", None)
    data["branding"] = brand
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        return load_config(path)
    except SystemExit:
        if original is None:
            path.unlink()
        else:
            path.write_text(original, encoding="utf-8")
        raise


def page_enabled(name: str, cfg: dict | None = None) -> bool:
    """そのページを公開するか。オプションのページ（OPTIONAL_PAGES）は memo.config.json の項目で決まり、ほかは常に公開する。"""
    key = OPTIONAL_PAGES.get(name)
    return True if key is None else bool((cfg or CONFIG)[key])


def today() -> str:
    return dt.datetime.now(TZ).date().isoformat()


def pages_url(repository: str) -> str:
    """GitHub Pages の既定の URL（独自ドメインがないとき）。"""
    if not repository or "/" not in repository:
        return ""
    owner, name = repository.split("/", 1)
    if name.lower() == f"{owner.lower()}.github.io":
        return f"https://{owner.lower()}.github.io/"
    return f"https://{owner.lower()}.github.io/{name}/"


def site_url() -> str:
    """公開 URL（末尾 /）。src/CNAME があればその独自ドメイン、なければ GitHub Pages の URL。"""
    cname = SRC / "CNAME"
    if cname.is_file():
        lines = cname.read_text(encoding="utf-8").strip().splitlines()
        if lines and lines[0].strip():
            return f"https://{lines[0].strip()}/"
    return pages_url(REPOSITORY)


SITE_URL = site_url()  # og:url / og:image の絶対 URL に使う


def hex6(color: str) -> str:
    """#rgb / #rrggbb を小文字の #rrggbb にそろえる。"""
    c = color.strip().lstrip("#")
    return "#" + ("".join(ch * 2 for ch in c) if len(c) == 3 else c).lower()


def darken(color: str, ratio: float) -> str:
    c = hex6(color)
    return "#" + "".join(f"{round(int(c[i:i + 2], 16) * ratio):02x}" for i in (1, 3, 5))


def contrast_on_white(color: str) -> float:
    """白（#ffffff）とのコントラスト比（WCAG の式）。"""
    c = hex6(color)

    def lin(v: int) -> float:
        x = v / 255
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(int(c[i:i + 2], 16)) for i in (1, 3, 5))
    return 1.05 / (0.2126 * r + 0.7152 * g + 0.0722 * b + 0.05)


def light_accent(accent: str, min_contrast: float = 4.5) -> str:
    """白地で文字として読める（コントラスト比 4.5 以上の）濃さまで accent を暗くする。"""
    ratio = 1.0
    while contrast_on_white(darken(accent, ratio)) < min_contrast and ratio > 0:
        ratio = round(ratio - 0.02, 2)
    return darken(accent, max(ratio, 0))


def accents(cfg: dict | None = None) -> tuple[str, str]:
    """ページに使うアクセント色（ライトモード, ダークモード）。"""
    b = (CONFIG if cfg is None else cfg)["branding"]
    dark = hex6(b["accent"])
    return (hex6(b["accent_light"]) if b["accent_light"] else light_accent(dark)), dark


def branding(cfg: dict | None = None, url: str | None = None) -> dict:
    """アイコン・OGP 画像に入れる値。branding の空欄をサイト名・説明・公開 URL で埋める。"""
    cfg = CONFIG if cfg is None else cfg
    url = SITE_URL if url is None else url
    b = dict(cfg["branding"])
    b["title"] = b["title"] or cfg["site_name"]
    b["tagline"] = b["tagline"] or cfg["description"]
    b["url"] = b["url"] or re.sub(r"^https?://|/$", "", url)
    b["mark"] = b["mark"] or b["title"][:1].upper()
    b["accent_light"], b["accent"] = accents(cfg)
    return b


def asset_version(name: str) -> str:
    """画像の中身から短いハッシュを作る。画像を差し替えると URL が変わり、
    Discord などの画像キャッシュが古いまま残るのを防ぐ。"""
    f = SRC / "assets" / name
    return hashlib.sha256(f.read_bytes()).hexdigest()[:8] if f.is_file() else ""


OG_VERSION = asset_version("og.png")
HEAD_BEGIN = "<!-- memo:head（scripts/memo.py が自動生成。手で編集しない） -->"
HEAD_END = "<!-- /memo:head -->"
HEAD_RE = re.compile(r"<!-- memo:head.*?<!-- /memo:head -->\n?", re.S)
TEMPLATE = ROOT / ".claude" / "skills" / "memo-style" / "template.html"
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

ASSETS = SRC / "assets"  # アイコン・OGP 画像の置き場所（branding/render.py が書き出す）
# claude.ai のアプリ側に置く入口スキル（build が memo.config.json から dist/ に生成する）
ENTRY_SKILL = DIST / "entry-skill" / "SKILL.md"
