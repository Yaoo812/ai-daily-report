---
name: ai-daily-report
description: 抓取量子位(qbitai)与机器之心(jiqizhixin)的每日文章，生成 AI 行业日报（Markdown 文字版 + 竖版长图）。当用户说"生成日报""爬取量子位/机器之心文章""AI 日报""昨天有哪些 AI 新闻"时使用。
---

# AI 行业日报（量子位 + 机器之心）

抓取两个国内 AI 媒体的"昨日"文章，输出一份带摘要的日报，包含 Markdown 文字版和一张可分享的竖版长图。

## 输出物

- `AI日报_<日期>.md` — 文字版（含链接、作者、摘要）
- `AI日报_<日期>.png` — 图片版长图（1080px 宽，含每篇摘要）
- `report_data.json` — 中间数据（摘要可在此手工润色后再生成图片）

## 执行步骤

1. **抓取数据**（本目录 `scripts/fetch_report.py`）：
   ```bash
   PYTHONIOENCODING=utf-8 python scripts/fetch_report.py 2026-10-24
   ```
   日期参数可省略，默认抓"昨日"（北京时间 UTC+8）。脚本会写入 `report_data.json` 和 Markdown，并自动跨来源检测同题新闻（见「多源重复报道标记」）。

2. **（可选）润色摘要**：机器之心正文开头有「编辑｜名字」与正文无分隔符粘连，自动清洗可能不完美，可打开 `report_data.json` 逐条改 `summary` 字段。

3. **归纳「今日看点」**：由 Claude 根据标题+摘要聚类出 3–5 个主题，写入 `report_data.json` 顶层 `highlights` 字段（结构 `[{"theme": "...", "points": ["...", ...]}]`）。这是 LLM 归纳，脚本不做规则聚类。

4. **重写 Markdown + 生成图片**：
   ```bash
   PYTHONIOENCODING=utf-8 python scripts/fetch_report.py --render-only
   PYTHONIOENCODING=utf-8 python scripts/gen_image.py
   ```
   `--render-only` 只重读 `report_data.json` 重写 Markdown（不抓取），`gen_image.py` 生成含「今日看点」区块的长图。两者都会渲染 `highlights` 与各篇的 `dup` 重复标记（字段缺失则自动跳过）。

## 多源重复报道标记

两个来源常在同一天报道同一新闻（如 Claude 订阅调整、DeepSeek 开源）。抓取脚本内置 `detect_duplicates()`，用「标题归一化 + 字符 bigram Jaccard 相似度（阈值 0.28）」**跨来源**自动比对，命中后给两篇文章写相同的 `dup` 字段。

- **数据**：每篇文章可含 `"dup": "<分组标签>"`，同组值相同（标签文字任意，仅用于人工辨识）。渲染层只看该字段是否存在，不看值。
- **渲染**：Markdown 里该条目标题后加 `🔁 多源报道a`（字母按组出现顺序分配，同组相同），报告顶部加图例说明；长图里该卡片右上角画紫色「多源报道a」徽章。
- **人工兜底**：`detect_duplicates` 只在完整抓取（`fetch_report.py [日期]`）时运行，`--render-only` 不会重新检测、也不会覆盖已有 `dup`。自动检测若漏检/误判，直接改 `report_data.json` 里的 `dup` 字段即可（删掉该字段即取消标记）。

## 两个数据源的真实接口（关键，别用 HTML 解析）

### 量子位 qbitai.com（WordPress）

- **接口**：`https://www.qbitai.com/wp-json/wp/v2/posts?per_page=100&orderby=date&order=asc&after=<D-1>T00:00:00&before=<D+1>T00:00:00`
- `date` 字段是**北京时间**（`date_gmt` 才是 UTC，两者差 8 小时）；`after`/`before` 按 `date` 比较。
- 摘要用 `excerpt.rendered`（干净的导语）；没有则回退到 `content.rendered` 去 HTML 标签。
- 文章 URL：`p['link']`（形如 `https://www.qbitai.com/2026/10/505083.html`）。

### 机器之心 jiqizhixin.com（Rails + React SPA）

- **接口**：`https://www.jiqizhixin.com/api/article_library/articles.json?sort=time&page=1&per=20`
- ⚠️ 该接口**固定只返回最近 20 篇**：`page`/`offset`/`per` 均被忽略（`per=100` 仍只回 20 篇）。所以"昨日"必须落在最近 20 篇内 —— 机器之心每天约 11–15 篇，正常够用；若要更早日期需另想办法（sitemap 兜底）。
- 字段：`title`、`slug`、`publishedAt`（形如 `"2026/10/24 23:05"`）、`content`、`author`、`tagList`。
- 文章 URL：`https://www.jiqizhixin.com/articles/<slug>`（slug 形如 `2026-10-24-11`，日期就在 slug 里）。
- 首页/文章库页是 JS 渲染的空壳（body 里只有 React 挂载点），解析 HTML 拿不到列表。

## 必须注意的坑

1. **WebFetch 被域名拦截**：`www.qbitai.com` / `www.jiqizhixin.com` 走 WebFetch 会报 "Unable to verify domain"。必须用 `curl` 或 Python `urllib` 直连。
2. **Windows Python 读不到 Git Bash 的 `/tmp`**：`python -c "open('/tmp/x')"` 会 FileNotFound（Windows Python 把 `/tmp` 当 `C:\tmp`）。要么用 `curl | python`（stdin），要么写**相对路径**（两者 CWD 一致）。
3. **控制台 GBK 报错**：`UnicodeEncodeError: 'gbk' codec can't encode ...`。所有 python 命令前加 `PYTHONIOENCODING=utf-8`，或脚本内 `sys.stdout.reconfigure(encoding='utf-8')`。
4. **RSS 日期会过期**：qbitai 的 `/feed` pubDate 是缓存快照，可能比真实发布时间旧。**以文章页/WP API 的 `date` 为准**。文章页里 `2026-10-25 00:22:25` 那种是 WP-Super-Cache 的缓存注释时间，**不是**发布时间——真正的发布时间是 `<span class="date">YYYY-MM-DD</span>` + `<span class="time">HH:MM:SS</span>`。
5. **"昨日"按北京时间算**：服务器 HTTP 头 `Date` 是 GMT，北京时间 = +8 小时。判断"现在几点/昨日是哪天"要以北京时间（UTC+8）为准，别直接用 GMT。
6. **中文字体**：Windows 上用 `C:/Windows/Fonts/msyh.ttc`（微软雅黑）、`msyhbd.ttc`（加粗），PIL 直接 `ImageFont.truetype` 即可。
7. **机器之心「编辑｜名字」粘连**：正文 `content` 开头形如 `编辑｜Panda如果只能用一行…`，编辑名与正文之间无分隔符，`｜`(U+FF5C) 与 `丨`(U+4E28) 是不同字符，正则清理易失败。脚本做了尽力清洗，仍建议第 2 步人工润色。

## 若某来源当日停更

量子位偶有整天停更（如周末）。脚本会：目标日无文章 → 自动抓**前一日**作为参考，并在数据里标 `is_fallback: true`；图片里该来源会显示"无更新"橙色提醒条 + "最近参考（前一日）"。

## 扩展更多来源

数据源是脚本里两个 `fetch_xxx(date)` 函数，返回统一的文章结构 `[{time, title, summary, url}]`。新增来源只需：加一个 `fetch_新站(date)`、在 `SOURCES` 里登记（含名称、中文标签、主题色）、把数据写进 `report_data.json` 的 `sources[]`。图片脚本按 `sources[]` 顺序渲染。

文章结构里可再带可选字段 `dup`（跨来源重复标记，见「多源重复报道标记」）。新增来源后 `detect_duplicates()` 会自动把它纳入跨来源比对，无需额外改动。
