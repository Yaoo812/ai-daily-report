# -*- coding: utf-8 -*-
"""
读取 report_data.json，生成竖版长图日报。
用法:
    PYTHONIOENCODING=utf-8 python gen_image.py
输出: AI日报_<日期>.png
"""
import sys, os, json
from PIL import Image, ImageDraw, ImageFont

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

OUT_DIR = "output"  # 日报输出目录（相对仓库根目录，便携）
os.makedirs(OUT_DIR, exist_ok=True)

with open(os.path.join(OUT_DIR, "report_data.json"), encoding="utf-8") as f:
    DATA = json.load(f)
DATE = DATA["date"]  # "2026-10-24"
SOURCES = DATA["sources"]
HIGHLIGHTS = DATA.get("highlights")

DUP_MAP = {}
for s in SOURCES:
    for a in s["articles"]:
        tag = a.get("dup")
        if tag and tag not in DUP_MAP:
            DUP_MAP[tag] = chr(ord("a") + len(DUP_MAP))

# ---------- 尺寸与字体 ----------
W = 1080
MARGIN = 48
CONTENT_W = W - 2 * MARGIN
FONT_DIR = "C:/Windows/Fonts/"
f_title   = ImageFont.truetype(FONT_DIR + "msyhbd.ttc", 64)
f_sub     = ImageFont.truetype(FONT_DIR + "msyh.ttc", 30)
f_meta    = ImageFont.truetype(FONT_DIR + "msyh.ttc", 26)
f_section = ImageFont.truetype(FONT_DIR + "msyhbd.ttc", 38)
f_note    = ImageFont.truetype(FONT_DIR + "msyh.ttc", 26)
f_time    = ImageFont.truetype(FONT_DIR + "msyhbd.ttc", 28)
f_item    = ImageFont.truetype(FONT_DIR + "msyh.ttc", 29)
f_sum     = ImageFont.truetype(FONT_DIR + "msyh.ttc", 25)
f_hl_theme= ImageFont.truetype(FONT_DIR + "msyhbd.ttc", 30)
f_footer  = ImageFont.truetype(FONT_DIR + "msyh.ttc", 24)

BG       = (246, 247, 249)
CARD_BG  = (255, 255, 255)
INK      = (31, 41, 55)
MUTED    = (107, 114, 128)
SUM_COLOR= (90, 98, 112)
NAVY_TOP = (24, 34, 58)
NAVY_BOT = (46, 62, 112)
HL_ACCENT = "#DB2777"
NOTE_BG  = (255, 246, 237)
NOTE_INK = (124, 45, 18)

def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

_dummy = ImageDraw.Draw(Image.new("RGB", (10, 10)))
def text_w(s, f): return _dummy.textlength(s, font=f)

def wrap(text, font, max_w):
    lines, cur = [], ""
    for ch in text:
        if text_w(cur + ch, font) <= max_w:
            cur += ch
        else:
            if cur:
                lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines

def grad_rect(draw, x0, y0, x1, y1, c_top, c_bot):
    h = y1 - y0
    for i in range(h):
        t = i / max(h - 1, 1)
        c = tuple(int(c_top[k] + (c_bot[k] - c_top[k]) * t) for k in range(3))
        draw.line([(x0, y0 + i), (x1, y0 + i)], fill=c)

def cn_date(s):
    y, m, d = s.split("-")
    return f"{int(m)} 月 {int(d)} 日"

# ---------- 排版常量 ----------
CARD_PAD = 26
TIME_W = 92
GAP = 18
title_max_w = CONTENT_W - 2 * CARD_PAD - TIME_W - GAP
TITLE_LH = 42
SUM_LH = 33
HL_THEME_LH = 40
CARD_TOP = 18
TITLE_SUM_GAP = 6
CARD_BOT = 16

DUP_PREFIX = "多源报道"
f_dup = ImageFont.truetype(FONT_DIR + "msyh.ttc", 22)
DUP_BADGE_W = int(text_w(DUP_PREFIX + "a", f_dup)) + 18
DUP_BADGE_H = 30
DUP_BADGE_FILL = (237, 233, 254)
DUP_BADGE_INK = (109, 40, 217)

def prep(a):
    tw = title_max_w - (DUP_BADGE_W + 12) if a.get("dup") else title_max_w
    return wrap(a["title"], f_item, tw), wrap(a["summary"], f_sum, tw)

def card_h(tl, sl):
    return CARD_TOP + len(tl) * TITLE_LH + TITLE_SUM_GAP + len(sl) * SUM_LH + CARD_BOT

def prep_hl(h):
    tl = wrap(h["theme"], f_hl_theme, CONTENT_W - 2 * CARD_PAD)
    pl = []
    for p in h["points"]:
        pl.extend(wrap("· " + p, f_sum, CONTENT_W - 2 * CARD_PAD))
    return tl, pl

def hl_card_h(tl, pl):
    return CARD_TOP + len(tl) * HL_THEME_LH + TITLE_SUM_GAP + len(pl) * SUM_LH + CARD_BOT

# 预排版
prep_sources = []
for s in SOURCES:
    prep_sources.append((s, [(a, prep(a)) for a in s["articles"]]))

prep_highlights = [(h, prep_hl(h)) for h in (HIGHLIGHTS or [])]

def items_height(plist):
    return sum(card_h(*pp) + 12 for _, pp in plist)

def note_block(s):
    txt = f"{s['name']}在 {cn_date(DATE)} 全天未发布文章，以下为该来源最近更新（{cn_date(s['date'])}）的内容。"
    lines = wrap(txt, f_note, CONTENT_W - 2 * CARD_PAD)
    return lines, len(lines) * 38 + 24

# ---------- 计算总高度 ----------
header_h = 210
meta_h = 92
section_h = 76
footer_h = 90
total_h = header_h + meta_h
if prep_highlights:
    total_h += 40 + section_h + 24 + sum(hl_card_h(*pp) + 12 for _, pp in prep_highlights)
for s, plist in prep_sources:
    total_h += 40 + section_h + 24 + items_height(plist) + 8
    if s["is_fallback"]:
        _, nh = note_block(s)
        total_h += 14 + nh + 18 + 46
total_h += 20 + footer_h

img = Image.new("RGB", (W, total_h), BG)
draw = ImageDraw.Draw(img)

# ---------- 头部 ----------
grad_rect(draw, 0, 0, W, header_h, NAVY_TOP, NAVY_BOT)
draw.ellipse([W - 260, -80, W - 60, 120], fill=(80, 100, 160))
draw.ellipse([W - 320, 40, W - 200, 160], fill=(60, 78, 130))
draw.text((MARGIN, 48), "AI 行业日报", font=f_title, fill=(255, 255, 255))
draw.text((MARGIN, 138), f"{DATE}（昨日）", font=f_sub, fill=(190, 200, 225))

meta_y = header_h
draw.rectangle([0, meta_y, W, meta_y + meta_h], fill=(236, 238, 243))
draw.text((MARGIN, meta_y + 30),
          f"数据来源：量子位 · 机器之心      抓取时间：{DATA.get('generated_at','')}",
          font=f_meta, fill=MUTED)

y = meta_y + meta_h

def section_header(yy, accent, title):
    draw.rectangle([MARGIN, yy, MARGIN + 8, yy + 40], fill=accent)
    draw.text((MARGIN + 24, yy - 4), title, font=f_section, fill=INK)
    return yy + 40

def draw_items(yy, plist, accent):
    for a, (tl, sl) in plist:
        bh = card_h(tl, sl)
        draw.rounded_rectangle([MARGIN, yy, W - MARGIN, yy + bh], radius=12, fill=CARD_BG)
        draw.rounded_rectangle([MARGIN, yy, MARGIN + 5, yy + bh], radius=3, fill=accent)
        ty = yy + CARD_TOP
        draw.text((MARGIN + CARD_PAD, ty + 2), a["time"], font=f_time, fill=accent)
        if a.get("dup"):
            badge = DUP_PREFIX + DUP_MAP[a["dup"]]
            bx = W - MARGIN - CARD_PAD - DUP_BADGE_W
            by = ty + 2
            draw.rounded_rectangle([bx, by, bx + DUP_BADGE_W, by + DUP_BADGE_H],
                                   radius=15, fill=DUP_BADGE_FILL)
            bw = text_w(badge, f_dup)
            draw.text((bx + (DUP_BADGE_W - bw) // 2, by + 4), badge, font=f_dup, fill=DUP_BADGE_INK)
        tx = MARGIN + CARD_PAD + TIME_W + GAP
        for ln in tl:
            draw.text((tx, ty), ln, font=f_item, fill=INK)
            ty += TITLE_LH
        ty += TITLE_SUM_GAP
        for ln in sl:
            draw.text((tx, ty), ln, font=f_sum, fill=SUM_COLOR)
            ty += SUM_LH
        yy += bh + 12
    return yy

def draw_highlights(yy):
    yy += 40
    yy = section_header(yy, hex_rgb(HL_ACCENT), "今日看点")
    yy += 24
    for h, (tl, pl) in prep_highlights:
        bh = hl_card_h(tl, pl)
        draw.rounded_rectangle([MARGIN, yy, W - MARGIN, yy + bh], radius=12, fill=CARD_BG)
        draw.rounded_rectangle([MARGIN, yy, MARGIN + 5, yy + bh], radius=3, fill=hex_rgb(HL_ACCENT))
        ty = yy + CARD_TOP
        for ln in tl:
            draw.text((MARGIN + CARD_PAD, ty), ln, font=f_hl_theme, fill=hex_rgb(HL_ACCENT))
            ty += HL_THEME_LH
        ty += TITLE_SUM_GAP
        for ln in pl:
            draw.text((MARGIN + CARD_PAD, ty), ln, font=f_sum, fill=SUM_COLOR)
            ty += SUM_LH
        yy += bh + 12
    return yy

if prep_highlights:
    y = draw_highlights(y)

for s, plist in prep_sources:
    accent = hex_rgb(s["accent"])
    y += 40
    head = f"{s['name']} · {cn_date(s['date'])} · 共 {len(s['articles'])} 篇" if not s["is_fallback"] \
        else f"{s['name']} · {cn_date(DATE)} · 无更新"
    y = section_header(y, accent, head)
    y += 24
    if s["is_fallback"]:
        lines, nh = note_block(s)
        y += 14
        draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + nh], radius=12, fill=NOTE_BG)
        draw.rounded_rectangle([MARGIN, y, MARGIN + 5, y + nh], radius=3, fill=accent)
        ny = y + 14
        draw.text((MARGIN + CARD_PAD, ny), "⚠ 提醒", font=f_time, fill=accent)
        for ln in lines:
            draw.text((MARGIN + CARD_PAD, ny + 38), ln, font=f_note, fill=NOTE_INK)
            ny += 38
        y += nh + 18
        draw.text((MARGIN + 24, y - 2), f"最近参考（{cn_date(s['date'])} · 共 {len(s['articles'])} 篇）",
                  font=f_note, fill=MUTED)
        y += 46
    y = draw_items(y, plist, accent)

draw.rectangle([0, total_h - footer_h, W, total_h], fill=(236, 238, 243))
draw.text((MARGIN, total_h - footer_h + 30), "日报 · zitong 整理", font=f_footer, fill=MUTED)

out = os.path.join(OUT_DIR, f"AI日报_{DATE}.png")
img.save(out)
print("saved:", out, "size:", img.size)
