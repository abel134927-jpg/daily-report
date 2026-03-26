#!/usr/bin/env python3
"""每日電腦硬體新聞整理機器人 - 使用 Claude AI 整理後發送至 LINE Messaging API"""

import os
import json
import calendar
import feedparser
import requests
from datetime import datetime, timedelta, timezone
import anthropic

# ==================== RSS 來源 ====================
# 硬體媒體（GPU / CPU / 其他硬體）
HARDWARE_FEEDS = [
    ("Tom's Hardware",  "https://www.tomshardware.com/feeds/all"),
    ("TechPowerUp",     "https://www.techpowerup.com/rss/news.xml"),
    ("Videocardz",      "https://videocardz.com/feed"),
    ("Wccftech",        "https://wccftech.com/feed/"),
    ("The Verge",       "https://www.theverge.com/rss/index.xml"),
]

# 中文科技媒體（筆電 / 硬體 / 開箱）
CN_TECH_FEEDS = [
    ("IT之家",      "https://www.ithome.com/rss/"),
    ("快科技",      "https://news.mydrivers.com/rss/"),
    ("中關村在線",  "https://news.zol.com.cn/rss.xml"),
    ("太平洋電腦",  "https://news.pconline.com.cn/rss/"),
    ("什麼值得買",  "https://www.smzdm.com/feed/"),
]

# 中文社群媒體（透過 RSSHub 公開實例）
# RSSHub 文件：https://docs.rsshub.app/
CN_SOCIAL_FEEDS = [
    # 微博關鍵字搜尋
    ("微博-機械革命",   "https://rsshub.app/weibo/search/weibo?q=機械革命"),
    ("微博-拯救者",     "https://rsshub.app/weibo/search/weibo?q=拯救者筆記本"),
    ("微博-ROG",        "https://rsshub.app/weibo/search/weibo?q=ROG筆電"),
    ("微博-外星人",     "https://rsshub.app/weibo/search/weibo?q=外星人筆記本"),
    # 知乎搜尋
    ("知乎-機械革命",   "https://rsshub.app/zhihu/search?query=機械革命筆記本"),
    ("知乎-拯救者",     "https://rsshub.app/zhihu/search?query=拯救者筆記本"),
    # B站搜尋（影片標題有開箱/評測資訊）
    ("B站-機械革命",    "https://rsshub.app/bilibili/search/video?keyword=機械革命筆電"),
    ("B站-拯救者",      "https://rsshub.app/bilibili/search/video?keyword=拯救者筆電評測"),
    ("B站-ROG",         "https://rsshub.app/bilibili/search/video?keyword=ROG筆電評測"),
]

ALL_FEEDS = HARDWARE_FEEDS + CN_TECH_FEEDS + CN_SOCIAL_FEEDS

# ==================== 關鍵字過濾 ====================
# 大陸筆電品牌（只追蹤這些）
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
    "华为笔记本", "matebook", "huawei laptop",
    "荣耀笔记本", "magicbook", "honor laptop",
    "thinkpad", "联想拯救者", "ideapad", "lenovo yoga",
    "微星笔记本", "msi laptop",
    "华硕笔记本", "vivobook", "zenbook",
    "宏碁", "acer predator", "acer nitro",
]

# GPU / CPU / 其他硬體關鍵字（不限品牌地區）
OTHER_HW_KEYWORDS = [
    # GPU
    "gpu", "graphics card", "rtx 5", "rtx 4", "rtx 3", "geforce",
    "radeon", "rx 9", "rx 8", "rx 7", "arc ", "intel arc",
    "顯卡", "显卡", "video card",
    # CPU
    "ryzen", "core ultra", "core i9", "core i7", "core i5",
    "snapdragon x", "cpu", "processor", "處理器", "处理器",
    # 其他硬體
    "motherboard", "主板", "主機板", "ddr5", "ddr4",
    "ssd", "nvme", "psu", "power supply", "monitor", "顯示器", "显示器",
]

ALL_KEYWORDS = LAPTOP_CN_KEYWORDS + OTHER_HW_KEYWORDS


def fetch_news(hours: int = 24) -> list[dict]:
    """從所有 RSS 來源抓取過去 N 小時的相關新聞"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    articles = []

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
                link    = entry.get("link", "")

                text = (title + " " + summary).lower()
                if any(kw.lower() in text for kw in ALL_KEYWORDS):
                    articles.append({
                        "source":  source_name,
                        "title":   title,
                        "summary": summary,
                        "link":    link,
                        "date":    pub_date.strftime("%m-%d %H:%M UTC") if pub_date else "未知",
                    })

        except Exception as e:
            print(f"[警告] 無法讀取 {source_name}: {e}")

    # 去重（同標題）
    seen, unique = set(), []
    for a in articles:
        key = a["title"][:60]
        if key not in seen:
            seen.add(key)
            unique.append(a)

    return unique


def summarize_with_claude(articles: list[dict]) -> str:
    """將原始新聞送給 Claude，整理成 LINE 純文字格式"""
    client = anthropic.Anthropic()

    tz_tw = timezone(timedelta(hours=8))
    today = datetime.now(tz_tw).strftime("%Y年%-m月%-d日")

    raw = "\n\n".join([
        f"[{a['source']} | {a['date']}]\n標題：{a['title']}\n摘要：{a['summary']}\n連結：{a['link']}"
        for a in articles[:60]
    ])

    prompt = f"""你是一位專業的「筆記本與電腦硬體每日新聞整理專家」。

以下是今日自動抓取的新聞原始資料，請整理成繁體中文每日摘要，輸出給 LINE 訊息使用（純文字，不要用 Markdown 語法如 ** 或 ###）。

【筆記本電腦規則 - 非常重要】
只整理以下大陸品牌的筆電新聞，其他品牌（HP、Dell 一般款、蘋果等）一律忽略：
機械革命、拯救者（Legion）、ROG 玩家國度、外星人（Alienware）、
神舟、雷神、機械師、火影、炫龍、
小米/紅米、華為/榮耀、聯想（ThinkPad/IdeaPad/Yoga）、
微星（MSI）、華碩（ROG/VivoBook/ZenBook）、宏碁（Predator/Nitro）

【其他硬體規則】
顯卡（NVIDIA、AMD、Intel Arc）：有價格變動請標明「漲/跌」幅度與地區
CPU（Intel、AMD）：有價格變動請標明「漲/跌」幅度與地區
其他重要硬體：主機板、記憶體、SSD、電源、顯示器、散熱

【新聞原始資料】
{raw}

【輸出格式（純文字，繁體中文，用 emoji 分隔區塊）】

📅 今日日期：{today}
────────────────────
🔥 今日重點新聞（最多3則，標註原因）
1.
2.
3.
════════════════════
📌 大陸筆電新聞（只限上述品牌）
• 標題
  摘要：（1-2句）
  來源：（平台名稱）
  連結：（完整網址）

════════════════════
📌 顯卡新聞與價格
• 標題
  摘要：（1-2句）
  連結：（完整網址）

════════════════════
📌 CPU新聞與價格
• 標題
  摘要：（1-2句）
  連結：（完整網址）

════════════════════
📌 其他電腦硬體新聞
（若無重大消息請寫：今日無重大消息）
────────────────────
💡 額外提醒：一句趨勢或購買建議

注意：只使用上方提供的原始新聞，連結必須完整保留，無相關新聞的分類請寫「今日無重大消息」。"""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


def send_line_message(text: str, channel_token: str, user_id: str):
    """使用 LINE Messaging API 推送訊息（自動切割超過 4800 字元的長文）"""
    url     = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {channel_token}",
        "Content-Type": "application/json",
    }
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
    for i, chunk in enumerate(chunks):
        prefix = f"[{i+1}/{total}]\n" if total > 1 else ""
        body = {
            "to": user_id,
            "messages": [{"type": "text", "text": prefix + chunk}],
        }
        resp = requests.post(url, headers=headers, data=json.dumps(body))
        if resp.status_code == 200:
            print(f"[OK] LINE sent {i+1}/{total}")
        else:
            print(f"[FAIL] LINE error ({resp.status_code}): {resp.text}")
            raise RuntimeError("LINE Messaging API send failed")


def main():
    print("=" * 50)
    print("Fetching hardware news...")
    articles = fetch_news(hours=24)
    print(f"Found {len(articles)} relevant articles")

    tz_tw = timezone(timedelta(hours=8))
    today = datetime.now(tz_tw).strftime("%Y年%-m月%-d日")

    if not articles:
        digest = (
            f"📅 今日日期：{today}\n"
            "────────────────────\n"
            "⚠️ 今日未從 RSS 找到相關硬體新聞。\n"
            "可能原因：RSS 來源暫時無法存取，或今日新聞較少。\n"
            "請手動查看 IT之家 / 快科技 確認。"
        )
    else:
        print("Summarizing with Claude...")
        digest = summarize_with_claude(articles)
        print("Done")

    print("Sending to LINE...")
    send_line_message(
        text          = digest,
        channel_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"],
        user_id       = os.environ["LINE_USER_ID"],
    )
    print("Complete!")
    print("=" * 50)


if __name__ == "__main__":
    main()
