# AI 行业日报（量子位 + 机器之心）

抓取 [量子位](https://www.qbitai.com) 与 [机器之心](https://www.jiqizhixin.com) 的"昨日"文章，自动生成一份带摘要的 AI 行业日报：

- **Markdown 文字版**：`AI日报_<日期>.md`
- **竖版长图**：`AI日报_<日期>.png`（1080px 宽，可直接分享）

## 功能特性

- 双源抓取（量子位 WordPress API + 机器之心 Rails API + sitemap 兜底）
- 自动清洗正文（去 byline、编辑署名粘连等）
- **跨来源重复报道检测**：标题归一化 + bigram Jaccard 相似度，自动标记同题新闻
- 「今日看点」区块：LLM 归纳热点主题，渲染进文字版与长图
- 某来源当日停更时自动回退前一日并标注

## 环境要求

- Python 3
- Pillow（`pip install pillow`）
- `curl`（机器之心单篇接口需用 curl 绕过 WAF）
- Windows 中文字体（`msyh.ttc` / `msyhbd.ttc`，长图用）

> 长图脚本目前硬编码使用 Windows 微软雅黑字体路径 `C:/Windows/Fonts/`，跨平台需自行替换字体路径。

## 使用

```bash
# 抓取昨日（默认），写入 report_data.json 与 Markdown
PYTHONIOENCODING=utf-8 python scripts/fetch_report.py

# 或指定日期
PYTHONIOENCODING=utf-8 python scripts/fetch_report.py 2026-10-24

# （可选）在 report_data.json 里润色 summary、增补 highlights 字段

# 重写 Markdown 并生成竖版长图
PYTHONIOENCODING=utf-8 python scripts/fetch_report.py --render-only
PYTHONIOENCODING=utf-8 python scripts/gen_image.py
```

## 目录结构

```
.
├── SKILL.md                 # Claude Code skill 定义（含数据源接口说明与踩坑记录）
├── scripts/
│   ├── fetch_report.py      # 抓取 + 去重 + 生成 Markdown
│   └── gen_image.py         # 读取 report_data.json 生成竖版长图
└── README.md
```

更多数据源接口细节、坑与扩展方法见 [`SKILL.md`](./SKILL.md)。
