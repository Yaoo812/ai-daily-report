# -*- coding: utf-8 -*-
"""
抓取量子位(qbitai)与机器之心(jiqizhixin)的指定日期文章，生成日报数据 + Markdown。
用法:
    PYTHONIOENCODING=utf-8 python fetch_report.py [YYYY-MM-DD]
日期可省略，默认抓"昨日"(北京时间 UTC+8)。
输出: report_data.json, AI日报_<日期>.md
"""
import sys, os, json, re, html, gzip, subprocess, urllib.request, datetime, argparse

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"}
BJ = datetime.timezone(datetime.timedelta(hours=8))
OUT_DIR = "output"  # 日报输出目录（相对仓库根目录，便携）
os.makedirs(OUT_DIR, exist_ok=True)


def http_json(url):
    req = urllib.request.Request(url, headers=HDR)
    return json.load(urllib.request.urlopen(req, timeout=30))


def strip_html(t):
    return html.unescape(re.sub(r"<[^>]+>", "", t or ""))


def summarize(text, n=80):
    t = re.sub(r"\s+", " ", text or "").strip()
    if not t:
        return ""
    if len(t) <= n:
        return t
    seg = t[:n]
    for p in "。！？；":
        idx = seg.rfind(p)
        if idx > n * 0.4:
            return seg[: idx + 1]
    return seg + "…"


# ---------------- 跨来源重复检测 ----------------
def _norm_title(t):
    t = (t or "").lower()
    t = re.sub(r"^刚刚[，,]\s*", "", t)
    t = re.sub(r"^刚[，,]\s*", "", t)
    t = re.sub(r"[^一-龥a-z0-9]+", "", t)
    return t


def _bigrams(s):
    return {s[i:i + 2] for i in range(len(s) - 1)}


def detect_duplicates(payload, threshold=0.28):
    """跨来源检测同一新闻的重复报道，给文章标 dup 字段（同组相同值）。"""
    flat = [(s["key"], a) for s in payload["sources"] for a in s["articles"]]
    norm = [_norm_title(a["title"]) for _, a in flat]
    gid = 0
    for i in range(len(flat)):
        for j in range(i + 1, len(flat)):
            if flat[i][0] == flat[j][0]:
                continue
            ni, nj = norm[i], norm[j]
            if len(ni) < 4 or len(nj) < 4:
                continue
            bi, bj = _bigrams(ni), _bigrams(nj)
            if not bi or not bj:
                continue
            if len(bi & bj) / len(bi | bj) >= threshold:
                ai, aj = flat[i][1], flat[j][1]
                tag = ai.get("dup") or aj.get("dup")
                if not tag:
                    gid += 1
                    tag = f"dup-{gid}"
                ai["dup"] = tag
                aj["dup"] = tag


def dup_letters(sources):
    """按出现顺序给每个 dup 分组分配字母 a、b、c…，返回 {tag: letter}。"""
    mapping = {}
    for s in sources:
        for a in s["articles"]:
            tag = a.get("dup")
            if tag and tag not in mapping:
                mapping[tag] = chr(ord("a") + len(mapping))
    return mapping


def fmt_day(d):
    return f"{d.year} 月 {d.month} 日"


def clean_qbitai_lead(text):
    # 正文首段通常带 byline："作者 发自 凹非寺 量子位 | 公众号 QbitAI"（可能有空格/子品牌如 ROBO），且被换行分隔
    t = re.sub(r"\s+", " ", text or "").strip()
    t = re.sub(r"^.*?公众号\s*\S+", "", t).strip()          # 删到 "公众号 <账号>" 为止
    t = re.sub(r"^[^，。！？、\s]{1,24}\s+发自\s+\S+", "", t).strip()  # 无"公众号"时退而删 "作者 发自 地点"
    t = re.sub(r"^[，。！？、；：\s“”\"「」‘’'…·]+", "", t).strip()
    return t


# ---------------- 量子位 ----------------
def fetch_qbitai(day):
    after = day - datetime.timedelta(days=1)
    before = day + datetime.timedelta(days=1)
    url = (
        "https://www.qbitai.com/wp-json/wp/v2/posts?per_page=100&orderby=date&order=desc"
        f"&after={after.isoformat()}T00:00:00&before={before.isoformat()}T00:00:00"
    )
    posts = http_json(url)
    out = []
    for p in posts:
        d = p["date"][:10]  # 'date' 是北京时间
        if d != day.isoformat():
            continue
        title = strip_html(p["title"]["rendered"])
        if "未发布" in title:  # 跳过未发布/测试稿
            continue
        content = strip_html(p.get("content", {}).get("rendered", ""))
        out.append({
            "time": p["date"][11:16],
            "title": title,
            "summary": summarize(clean_qbitai_lead(content)),
            "url": p["link"],
        })
    return out


# ---------------- 机器之心 ----------------
JQ_EDITORS = ("Neo|Panda|Red Panda|机器之心|ScienceAI|泽南|张倩|牛来|克雷西|栗子|"
              "乾明|崔万铎|行早|小舟|蛋酱|冷猫|陈陈|Clio|陈彦杉|杨文|杜伟")


def clean_jq_content(c):
    # 列表接口返回纯文本、单篇接口返回 HTML，统一先剥标签再清洗
    c = re.sub(r"<[^>]+>", "", c or "")
    c = html.unescape(c).replace("｜", "丨").replace("|", "丨")
    c = re.sub(r"\s+", " ", c).strip()
    c = re.sub(r"^作者[丨:：][^丨]*[丨]?", "", c)
    c = re.sub(r"^编辑[丨:：](?:" + JQ_EDITORS + r")(?:[、,，]\s*(?:" + JQ_EDITORS + r"))*", "", c)
    c = re.sub(r"^编辑[丨:：][&,、，]?", "", c)  # & 等乱码兜底
    c = re.sub(r"^本文作者[^。]*。", "", c)
    c = re.sub(r"^[，。！？、；：\s“”\"「」‘’'…·]+", "", c).strip()
    return c


def curl_json(url):
    # 单篇接口对 urllib 有 WAF 拦截（返回 JS 挑战页），curl 能通过
    out = subprocess.run(["curl", "-s", "-A", "Mozilla/5.0", url, "--max-time", "25"],
                         capture_output=True)
    return json.loads(out.stdout.decode("utf-8"))


def get_sitemap_slugs(day):
    req = urllib.request.Request("https://www.jiqizhixin.com/shared/sitemap.xml.gz", headers=HDR)
    raw = urllib.request.urlopen(req, timeout=30).read()
    xml = gzip.decompress(raw).decode("utf-8", "ignore")
    prefix = day.isoformat()
    return sorted(set(re.findall(rf"articles/({prefix}(?:-\d+)?)", xml)))


def fetch_jiqizhixin(day):
    prefix = day.isoformat().replace("-", "/")  # publishedAt 形如 "2026/10/24 23:05"
    out = []
    # 1) 列表接口（只回最近 20 篇，可能被当天新文章挤出）
    data = http_json("https://www.jiqizhixin.com/api/article_library/articles.json?sort=time&page=1&per=20")
    for a in data.get("articles", []):
        if a["publishedAt"].startswith(prefix):
            out.append({
                "time": a["publishedAt"].split(" ")[1][:5],
                "title": a["title"],
                "summary": summarize(clean_jq_content(a.get("content", ""))),
                "url": f"https://www.jiqizhixin.com/articles/{a['slug']}",
            })
    # 2) 用 sitemap 补齐列表接口漏掉的（20 篇上限）
    try:
        slugs = get_sitemap_slugs(day)
        got = {a["url"].rsplit("/", 1)[-1] for a in out}
        for slug in slugs:
            if slug in got:
                continue
            try:
                d = curl_json(f"https://www.jiqizhixin.com/api/article_library/articles/{slug}")
                pub = d.get("published_at", "")
                tm = pub.split(" ")[1][:5] if " " in pub else ""
                out.append({
                    "time": tm,
                    "title": d.get("title", ""),
                    "summary": summarize(clean_jq_content(d.get("content", ""))),
                    "url": f"https://www.jiqizhixin.com/articles/{slug}",
                })
            except Exception:
                pass
    except Exception:
        pass
    out.sort(key=lambda x: x["time"], reverse=True)
    return out


# ---------------- 主流程 ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date", nargs="?", help="目标日期 YYYY-MM-DD，默认昨日(北京时间)")
    ap.add_argument("--render-only", action="store_true",
                    help="不抓取，仅读取 report_data.json 重写 Markdown")
    args = ap.parse_args()

    if args.render_only:
        with open(os.path.join(OUT_DIR, "report_data.json"), encoding="utf-8") as f:
            payload = json.load(f)
        write_markdown(payload)
        print("已根据 report_data.json 重写 Markdown（含今日看点）")
        return

    if args.date:
        target = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        target = datetime.datetime.now(BJ).date() - datetime.timedelta(days=1)

    sources = []
    for key, label, accent, fetch in [
        ("jiqizhixin", "机器之心", "#2563EB", fetch_jiqizhixin),
        ("qbitai", "量子位", "#EA580C", fetch_qbitai),
    ]:
        arts = fetch(target)
        is_fallback = False
        day = target
        if not arts:
            is_fallback = True
            for back in range(1, 8):  # 最多回退 7 天找最近更新
                prev = target - datetime.timedelta(days=back)
                arts = fetch(prev)
                if arts:
                    day = prev
                    break
        sources.append({
            "key": key, "name": label, "accent": accent,
            "date": day.isoformat(), "is_fallback": is_fallback,
            "articles": arts,
        })
        print(f"[{label}] {day.isoformat()}{' (前一日参考)' if is_fallback else ''}: {len(arts)} 篇")

    now_bj = datetime.datetime.now(BJ).strftime("%Y-%m-%d %H:%M")
    payload = {"date": target.isoformat(), "generated_at": now_bj, "sources": sources}
    detect_duplicates(payload)
    with open(os.path.join(OUT_DIR, "report_data.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    write_markdown(payload)
    print("\n已写入 report_data.json 与 AI日报_%s.md" % target.isoformat())
    print("提示：可在 report_data.json 里润色 summary 字段，再运行 gen_image.py 生成图片。")


def write_markdown(payload):
    lines = [f"# AI 行业日报 · {payload['date']}", "",
             f"> 抓取时间：{payload['generated_at']}（北京时间）", ""]
    dup_map = dup_letters(payload["sources"])
    if dup_map:
        lines.append("> 🔁 = 该新闻被多个来源共同报道（同组字母相同）")
        lines.append("")
    highlights = payload.get("highlights")
    if highlights:
        lines.append("## 今日看点")
        lines.append("")
        for h in highlights:
            lines.append(f"**{h['theme']}**")
            for p in h["points"]:
                lines.append(f"- {p}")
            lines.append("")
    for s in payload["sources"]:
        lines.append(f"## {s['name']} — {len(s['articles'])} 篇")
        if s["is_fallback"]:
            lines.append(f"> ⚠️ {s['name']} 当日无更新，以下为 {s['date']} 的最近文章。")
        lines.append("")
        lines.append("| 时间 | 标题 |")
        lines.append("|------|------|")
        for a in s["articles"]:
            dup = f"　🔁 多源报道{dup_map[a['dup']]}" if a.get("dup") else ""
            lines.append(f"| {a['time']} | [{a['title']}]({a['url']}){dup} |")
        lines.append("")
    with open(os.path.join(OUT_DIR, f"AI日报_{payload['date']}.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
