#!/usr/bin/env python3
"""把隐私政策 Markdown 渲染为可直接托管的静态 HTML（供 AGC「自定义隐私政策」URL 使用）。

输出：仓库根 ``docs/privacy-policy-zh.html`` / ``docs/privacy-policy-en.html``。
托管：在 GitHub 仓库 Settings → Pages 选择「Deploy from a branch / main / docs」后即可获得
``https://<owner>.github.io/<repo>/privacy-policy-zh.html`` 供 AGC 填写。

用法：python3 harmonyos/docs/release/tools/render-policy-html.py
"""
from __future__ import annotations

import html
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
OUT_DIR = os.path.join(REPO, "docs")

CSS = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { margin: 0; background: #f6f4ee; color: #23211d;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Segoe UI", sans-serif;
  line-height: 1.85; }
main { max-width: 860px; margin: 0 auto; padding: 40px 24px 72px; background: #fbfaf6; }
h1 { font-size: 30px; line-height: 1.35; margin: 8px 0 20px; }
h2 { font-size: 21px; margin: 36px 0 12px; padding-top: 10px; border-top: 1px solid #e6e1d6; }
h3 { font-size: 17px; margin: 24px 0 8px; }
p, li { font-size: 15px; }
ul, ol { padding-left: 24px; }
blockquote { margin: 14px 0; padding: 10px 16px; background: #f1ede3; border-left: 3px solid #c96442; color: #5b574f; }
blockquote p { margin: 4px 0; font-size: 13.5px; }
code { background: #efece3; padding: 1px 5px; border-radius: 4px; font-size: 13px; }
table { width: 100%; border-collapse: collapse; margin: 14px 0; font-size: 13px; }
th, td { border: 1px solid #e0dacd; padding: 7px 9px; text-align: left; vertical-align: top; }
th { background: #f1ede3; }
a { color: #b4542f; }
@media (prefers-color-scheme: dark) {
  body { background: #171613; color: #e8e4da; }
  main { background: #1e1d1a; }
  h2 { border-top-color: #33312c; }
  blockquote { background: #26241f; border-left-color: #d97757; color: #c9c4b8; }
  code { background: #2b2924; }
  th, td { border-color: #3a372f; }
  th { background: #26241f; }
  a { color: #e08a66; }
}
"""


def inline(text: str) -> str:
    """行内格式：**粗体**、`代码`、[文字](链接)、裸 URL。"""
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"(?<![=\"'>])(https?://[^\s<]+)", r'<a href="\1">\1</a>', text)
    return text


def render(md: str, title: str) -> str:
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    in_list = ""
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            if in_list:
                out.append(f"</{in_list}>")
                in_list = ""
            i += 1
            continue
        if stripped.startswith("```"):
            i += 1
            continue
        # 表格
        if stripped.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            if in_list:
                out.append(f"</{in_list}>")
                in_list = ""
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(cells)
                i += 1
            head, body = rows[0], rows[2:]
            out.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>")
            for row in body:
                out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>")
            out.append("</tbody></table>")
            continue
        # 标题
        m = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        if m:
            if in_list:
                out.append(f"</{in_list}>")
                in_list = ""
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            i += 1
            continue
        # 分隔线
        if re.match(r"^-{3,}$", stripped):
            if in_list:
                out.append(f"</{in_list}>")
                in_list = ""
            i += 1
            continue
        # 引用块
        if stripped.startswith(">"):
            if in_list:
                out.append(f"</{in_list}>")
                in_list = ""
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append("<blockquote>" + "".join(f"<p>{inline(b)}</p>" for b in buf if b) + "</blockquote>")
            continue
        # 无序列表
        m = re.match(r"^[-*]\s+(.*)$", stripped)
        if m:
            if in_list != "ul":
                if in_list:
                    out.append(f"</{in_list}>")
                out.append("<ul>")
                in_list = "ul"
            out.append(f"<li>{inline(m.group(1))}</li>")
            i += 1
            continue
        # 有序列表
        m = re.match(r"^\d+\.\s+(.*)$", stripped)
        if m:
            if in_list != "ol":
                if in_list:
                    out.append(f"</{in_list}>")
                out.append("<ol>")
                in_list = "ol"
            out.append(f"<li>{inline(m.group(1))}</li>")
            i += 1
            continue
        # 普通段落（合并连续行）
        if in_list:
            out.append(f"</{in_list}>")
            in_list = ""
        buf = [stripped]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^(#{1,3}\s|[-*]\s|\d+\.\s|>|\||-{3,})", lines[i].strip()):
            buf.append(lines[i].strip())
            i += 1
        out.append(f"<p>{inline(' '.join(buf))}</p>")
    if in_list:
        out.append(f"</{in_list}>")
    body = "\n".join(out)
    return f"""<!DOCTYPE html>
<html lang="{'zh-CN' if '隐私' in title else 'en'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{CSS}</style>
</head>
<body>
<main>
{body}
</main>
</body>
</html>
"""


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    for src_name, out_name, title in [
        ("privacy-policy-zh.md", "privacy-policy-zh.html", "GoGauge 隐私政策"),
        ("privacy-policy-en.md", "privacy-policy-en.html", "GoGauge Privacy Policy"),
    ]:
        src = os.path.join(REPO, "harmonyos", "docs", "release", src_name)
        with open(src, encoding="utf-8") as f:
            md = f.read()
        page = render(md, title)
        with open(os.path.join(OUT_DIR, out_name), "w", encoding="utf-8") as f:
            f.write(page)
        print("wrote", os.path.join(OUT_DIR, out_name))


if __name__ == "__main__":
    main()
