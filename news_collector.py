#!/usr/bin/env python3
"""每日電腦硬體新聞整理機器人 - DeepSeek AI 整理後發送至 LINE Messaging API"""

import os
import re
import json
import calendar
import feedparser
import requests
from datetime import datetime, timedelta, timezone
from openai import OpenAI

# ==================== RSS 來源 ====================
HARDWARE_FEEDS = [
    ("Tom's Hardware",  "https://www.tomshardware.com/feeds/all"),
    ("TechPowerUp",     "https://www.techpowerup.com/rss/news.xml"),
    ("Videocardz",      "https://videocardz.com/feed"),
    ("Wccftech",        "https://wccftech.com/feed/"),
    ("The Verge",       "https://www.theverge.com/rss/index.xml"),
]

CN_TECH_FEEDS = [
    ("IT之家",      "https://www.ithome.com/rss/"),
    ("快科技",      "https://news.mydrivers.com/rss/"),
    ("中關村在線",  "https://news.zol.com.cn/rss.xml"),
    ("太平洋電腦",  "https://news.pconline.com.cn/rss/"),
    ("什麼值得買",  "https://www.smzdm.com/feed/"),
]

CN_SOCIAL_FEEDS = [
    ("微博-機械革命",   "https://rsshub.app/weibo/search/weibo?q=機械革命"),
    ("微博-拯救者",     "https://rsshub.app/weibo/search/weibo?q=拯救者筆記本"),
    ("微博-ROG",        "https://rsshub.app/weibo/search/weibo?q=ROG筆電"),
    ("微博-外星人",     "https://rsshub.app/weibo/search/weibo?q=外星人筆記本"),
    ("知乎-機械革命",   "https://rsshub.app/zhihu/search?query=機械革命筆記本"),
    ("知乎-拯救者",     "https://rsshub.app/zhihu/search?query=拯救者筆記本"),
    ("B站-機械革命",    "https://rsshub.app/bilibili/search/video?keyword=機械革命筆電"),
    ("B站-拯救者",      "https://rsshub.app/bilibili/search/video?keyword=拯救者筆電評測"),
    ("B站-ROG",         "https://rsshub.app/bilibili/search/video?keyword=ROG筆電評測"),
]

ALL_FEEDS = HARDWARE_FEEDS + CN_TECH_FEEDS + CN_SOCIAL_FEEDS

# ==================== 關鍵字分類 ====================
# 大陸筆電品牌（只有命中這裡才算筆電新聞）
LAPTOP_CN_KEYWORDS = [
    "機械革命", "mechrev",
    "拯救者", "legion",
    "rog", "玩家國度",
    "外星人", "alienware",
    "神舟", "hasee",
    "雷神", "thunderobot",
    "機械師", "machenike",
    "火影",
    "炫龍",
    "小米筆記本", "mi notebook", "redmi book", "小米電腦",
    "matebook", "华为笔记本", "huawei laptop",
    "magicbook", "荣耀笔记本", "honor laptop",
    "thinkpad", "聯想拯救者", "联想拯救者", "ideapad", "lenovo yoga",
    "微星笔记本", "msi laptop",
    "华硕笔记本", "vivobook", "zenbook",
    "acer predator", "acer nitro", "宏碁掠奪者",
]

# GPU / CPU / 其他硬體關鍵字
OTHER_HW_KEYWORDS = [
    "gpu", "graphics card", "rtx 5", "rtx 4", "rtx 3", "geforce",
    "radeon", "rx 9", "rx 8", "rx 7", "arc ", "intel arc",
    "顯卡", "显卡", "video card",
    "ryzen", "core ultra", "core i9", "core i7", "core i5",
    "snapdragon x", "cpu", "processor", "處理器", "处理器",
    "motherboard", "主板", "主機板", "ddr5", "ddr4",
    "ssd", "nvme", "psu", "power supply", "monitor", "顯示器", "显示器",
]


def categorize(article: dict) -> str:
    """Python 層先分類，避免 AI 誤判"""
    text = (article["title"] + " " + article["summary"]).lower()
    if any(kw.lower() in text for kw in LAPTOP_CN_KEYWORDS):
        return "LAPTOP_CN"
    if any(kw.lower() in text for kw in OTHER_HW_KEYWORDS):
        return "HARDWARE"
    return "HARDWARE"


def fetch_news(hours: int = 24) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    articles = []
    all_keywords = LAPTOP_CN_KEYWORDS + OTHER_HW_KEYWORDS

    for source_name, url in ALL_FEEDS:
        try:
            feed = feedparser.parse(url, request_headers={
                "User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"
            })
            for entry in feed.entries[:30]:
                pub_date = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub_date = datetime.fromtimestamp(
                        calendar.timegm(entry.published_parsed), tz=timezone.utc
                    )
                if pub_date and pub_date < cutoff:
                    continue

                title   = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", ""))[:400].strip()

                text = (title + " " + summary).lower()
                if any(kw.lower() in text for kw in all_keywords):
                    articles.append({
                        "source":  source_name,
                        "title":   title,
                        "summary": summary,
                        "date":    pub_date.strftime("%m-%d %H:%M UTC") if pub_date else "未知",
                    })
        except Exception as e:
            print(f"[WARN] {source_name}: {e}")

    seen, unique = set(), []
    for a in articles:
        key = a["title"][:60]
        if key not in seen:
            seen.add(key)
            unique.append(a)

    return unique


def strip_urls(text: str) -> str:
    """移除輸出中所有網址（防止 AI 自行加上連結）"""
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'連結[：:]\s*\n', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def summarize_with_deepseek(articles: list[dict]) -> str:
    client = OpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com",
    )

    tz_tw = timezone(timedelta(hours=8))
    today = datetime.now(tz_tw).strftime("%Y年%-m月%-d日")

    # Python 預先分類，讓 AI 直接對應分類整理
    laptop_lines, hardware_lines = [], []
    for a in articles[:60]:
        entry = f"[{a['source']} | {a['date']}]\n標題：{a['title']}\n摘要：{a['summary']}"
        if categorize(a) == "LAPTOP_CN":
            laptop_lines.append(entry)
        else:
            hardware_lines.append(entry)

    laptop_raw   = "\n\n".join(laptop_lines)   or "（今日無大陸筆電品牌新聞）"
    hardware_raw = "\n\n".join(hardware_lines) or "（今日無相關硬體新聞）"

    prompt = f"""你是一位專業的電腦硬體每日新聞整理專家，請整理成繁體中文摘要發送至 LINE（純文字，不得包含任何網址或連結）。

【篩選規則 - 嚴格執行】
以下類型的新聞才能放入輸出，其餘一律忽略：
✅ 筆電：新品發布、規格公布、評測、上市日期、售價、降價/漲價
✅ 顯卡：新品發布、價格變動、上市、效能測試
✅ CPU：新品發布、價格變動、上市、跑分
✅ 其他硬體：重大新品或明顯降價
❌ 排除：復古/古董電腦、太空/科學、遊戲玩法故事、軟體、非硬體產品新聞

=== 大陸筆電品牌新聞（只整理這些，不得加入其他品牌）===
{laptop_raw}

=== 顯卡 / CPU / 其他硬體新聞 ===
{hardware_raw}

【輸出格式，嚴格遵守，不得輸出任何 http 網址】

📅 今日日期：{today}
────────────────────
🔥 今日重點新聞（最多3則，標註原因）
1.
2.
3.
════════════════════
📌 大陸筆電新聞
• 標題
  摘要：（1-2句，不附連結）

════════════════════
📌 顯卡新聞與價格
• 標題
  摘要：（1-2句，有價格變動請標明漲/跌與地區）

════════════════════
📌 CPU新聞與價格
• 標題
  摘要：（1-2句，有價格變動請標明漲/跌與地區）

════════════════════
📌 其他電腦硬體新聞
（若無重大消息請寫：今日無重大消息）
────────────────────
💡 額外提醒：一句趨勢或購買建議"""

    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
    )

    result = resp.choices[0].message.content
    return strip_urls(result)


def send_line_message(text: str, channel_token: str, targets: list[str]):
    """發送訊息到多個目標（個人 User ID 或群組 Group ID）"""
    url     = "https://api.line.me/v2/bot/message/push"
    headers = {"Authorization": f"Bearer {channel_token}", "Content-Type": "application/json"}
    max_len = 4800

    lines, chunks, current = text.split("\n"), [], ""
    for line in lines:
        if len(current) + len(line) + 1 > max_len:
            if current.strip():
                chunks.append(current.strip())
            current = line + "\n"
        else:
            current += line + "\n"
    if current.strip():
        chunks.append(current.strip())

    total = len(chunks)
    for target in targets:
        for i, chunk in enumerate(chunks):
            prefix = f"[{i+1}/{total}]\n" if total > 1 else ""
            body = {"to": target, "messages": [{"type": "text", "text": prefix + chunk}]}
            resp = requests.post(url, headers=headers, data=json.dumps(body))
            if resp.status_code == 200:
                print(f"[OK] {target[:8]}... sent {i+1}/{total}")
            else:
                print(f"[FAIL] {target[:8]}... error ({resp.status_code}): {resp.text}")


def main():
    print("=" * 50)
    print("Fetching hardware news...")
    articles = fetch_news(hours=24)
    print(f"Found {len(articles)} articles")

    tz_tw = timezone(timedelta(hours=8))
    today = datetime.now(tz_tw).strftime("%Y年%-m月%-d日")

    if not articles:
        digest = (
            f"📅 今日日期：{today}\n"
            "────────────────────\n"
            "⚠️ 今日未找到相關硬體新聞，請手動查看 IT之家 / 快科技 確認。"
        )
    else:
        print("Summarizing with DeepSeek...")
        digest = summarize_with_deepseek(articles)
        print("Done")

    print("Sending to LINE...")
    targets = [os.environ["LINE_USER_ID"], os.environ["LINE_GROUP_ID"]]
    send_line_message(
        text          = digest,
        channel_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"],
        targets       = targets,
    )
    print("Complete!")
    print("=" * 50)


if __name__ == "__main__":
    main()
