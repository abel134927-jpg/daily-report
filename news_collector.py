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
# 英文來源：GPU/CPU 硬體規格與發布訊息為主
HARDWARE_FEEDS = [
    ("Tom's Hardware",  "https://www.tomshardware.com/feeds/all"),
    ("TechPowerUp",     "https://www.techpowerup.com/rss/news.xml"),
    ("Videocardz",      "https://videocardz.com/feed"),
]

# 大陸科技媒體：新品發布、價格行情
CN_TECH_FEEDS = [
    ("IT之家",      "https://www.ithome.com/rss/"),
    ("快科技",      "https://news.mydrivers.com/rss/"),
    ("中關村在線",  "https://news.zol.com.cn/rss.xml"),
    ("太平洋電腦",  "https://news.pconline.com.cn/rss/"),
    ("什麼值得買",  "https://www.smzdm.com/feed/"),
]

# 社群平台：口碑推薦、評測、性價比討論
CN_SOCIAL_FEEDS = [
    # 微博
    ("微博-顯卡",       "https://rsshub.app/weibo/search/weibo?q=顯卡降價"),
    ("微博-裝機",       "https://rsshub.app/weibo/search/weibo?q=裝機推薦"),
    ("微博-機械革命",   "https://rsshub.app/weibo/search/weibo?q=機械革命"),
    ("微博-拯救者",     "https://rsshub.app/weibo/search/weibo?q=拯救者筆記本"),
    # 知乎
    ("知乎-顯卡推薦",   "https://rsshub.app/zhihu/search?query=顯卡推薦2025"),
    ("知乎-裝機",       "https://rsshub.app/zhihu/search?query=裝機配置推薦"),
    ("知乎-筆電推薦",   "https://rsshub.app/zhihu/search?query=筆記本電腦推薦"),
    ("知乎-拯救者",     "https://rsshub.app/zhihu/search?query=拯救者筆記本"),
    # B站
    ("B站-裝機推薦",    "https://rsshub.app/bilibili/search/video?keyword=裝機推薦性價比"),
    ("B站-顯卡評測",    "https://rsshub.app/bilibili/search/video?keyword=顯卡評測值不值得買"),
    ("B站-筆電推薦",    "https://rsshub.app/bilibili/search/video?keyword=筆記本電腦推薦"),
    ("B站-機械革命",    "https://rsshub.app/bilibili/search/video?keyword=機械革命筆電評測"),
    ("B站-拯救者",      "https://rsshub.app/bilibili/search/video?keyword=拯救者筆電評測"),
    # 小紅書
    ("小紅書-筆電推薦", "https://rsshub.app/xiaohongshu/search/notes?keyword=筆記本推薦"),
    ("小紅書-裝機",     "https://rsshub.app/xiaohongshu/search/notes?keyword=裝機推薦"),
    ("小紅書-顯卡",     "https://rsshub.app/xiaohongshu/search/notes?keyword=顯卡推薦"),
]

ALL_FEEDS = CN_TECH_FEEDS + CN_SOCIAL_FEEDS  # 只保留中國來源

# ==================== 關鍵字分類 ====================
# 大陸筆電品牌（只有命中這裡才算筆電新聞）
LAPTOP_CN_KEYWORDS = [
    # 通用詞
    "筆記本", "笔记本", "筆電", "笔电", "輕薄本", "轻薄本",
    "遊戲本", "游戏本", "商務本", "商务本", "notebook", "laptop",
    # 品牌名
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

# GPU / CPU / 其他硬體關鍵字（DIY 市場 / 消費端視角）
OTHER_HW_KEYWORDS = [
    # 顯卡
    "gpu", "graphics card", "rtx 5", "rtx 4", "rtx 3", "geforce",
    "radeon", "rx 9", "rx 8", "rx 7", "arc ", "intel arc",
    "顯卡", "显卡", "video card",
    "dlss", "fsr", "xess",
    # CPU
    "ryzen", "core ultra", "core i9", "core i7", "core i5",
    "snapdragon x", "cpu", "processor", "處理器", "处理器",
    # 主機板 / 記憶體 / 儲存
    "motherboard", "主板", "主機板",
    "ddr5", "ddr4", "記憶體", "记忆体", "内存",
    "ssd", "nvme", "固態硬碟", "固态硬盘",
    # 電源 / 散熱 / 機箱
    "psu", "power supply", "電源", "电源",
    "散熱", "散热", "aio", "水冷", "風冷",
    "機箱", "机箱",
    # 螢幕
    "monitor", "顯示器", "显示器",
    # DIY / 裝機 / 推薦
    "裝機", "装机", "配置推薦", "配置推荐", "性價比", "性价比",
    "值不值得買", "顯卡推薦", "显卡推荐",
    # 價格行情
    "漲價", "涨价", "降價", "降价", "price cut", "price hike",
    "國補", "国补", "活動價", "促銷", "首發價",
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

    laptop_raw   = "\n\n".join(laptop_lines)   or "（今日無筆記本電腦相關新聞）"
    hardware_raw = "\n\n".join(hardware_lines) or "（今日無顯卡/CPU/配件相關新聞）"

    prompt = f"""你是一位服務 DIY 裝機玩家和個人消費者的電腦硬體每日情報整理員。
受眾是台灣/大陸的普通消費者，在意的是：實際購買價格、新品規格值不值得買、現在什麼配置最划算、哪款筆電最多人推薦。
請整理成繁體中文摘要，發送至 LINE（純文字，不得包含任何網址或連結）。

【篩選規則 - 嚴格執行，其餘一律忽略】
✅ 筆電：新品發布含規格與售價、評測結論、降價促銷、性價比排行、推薦型號
✅ 顯卡：新品發布含價格、現貨行情漲跌、性價比推薦、評測結論
✅ CPU：新品發布含價格、行情漲跌、裝機推薦搭配
✅ DIY 配件：記憶體/SSD/電源等明顯漲降價、熱門推薦型號
✅ 裝機建議：各預算最推薦的配置（B站/知乎/小紅書口碑）
❌ 排除：企業財報、工廠產能、太空/科學、遊戲劇情、純軟體新聞、非消費端產品

【價格標示原則】
- 優先標示大陸市場人民幣（¥）現售價或活動價
- 有漲跌請標明漲/跌幅與幅度（例：漲幅約10%）
- 若有國補請加註（含國補後 ¥XXXX）

=== 筆記本電腦新聞 ===
{laptop_raw}

=== 顯卡 / CPU / DIY 配件新聞 ===
{hardware_raw}

【輸出格式，嚴格遵守，不得輸出任何 http 網址】

📅 今日日期：{today}
────────────────────
🔥 今日重點（最多3則，說明為何重要或影響購買決策）
1.
2.
3.
════════════════════
📌 筆記本電腦新聞
• 標題
  摘要：規格/價格/推薦結論，1-2句

════════════════════
📌 顯卡行情與新品
• 標題
  摘要：價格/漲跌/性價比結論，1-2句

════════════════════
📌 CPU 行情與新品
• 標題
  摘要：價格/漲跌/推薦搭配，1-2句

════════════════════
📌 DIY 配件 / 其他硬體
（記憶體、SSD、電源等；若無重大消息請寫：今日無重大消息）
────────────────────
💡 今日購買建議：一句話，現在適合買什麼、等什麼、避開什麼"""

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
