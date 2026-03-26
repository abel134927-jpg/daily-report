#!/usr/bin/env python3
"""每日 AI 新聞整理機器人 - 側重 AI Coding 與具身智能，DeepSeek 整理後發送至 LINE"""

import os
import re
import json
import calendar
import feedparser
import requests
from datetime import datetime, timedelta, timezone
from openai import OpenAI

# ==================== RSS 來源 ====================
AI_FEEDS = [
    # 英文科技媒體
    ("TechCrunch AI",   "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("VentureBeat AI",  "https://venturebeat.com/category/ai/feed/"),
    ("The Verge AI",    "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml"),
    ("Ars Technica",    "https://feeds.arstechnica.com/arstechnica/technology-lab"),
    ("Wired AI",        "https://www.wired.com/feed/tag/artificial-intelligence/latest/rss"),
    # Reddit（透過 RSSHub）
    ("r/MachineLearning",   "https://rsshub.app/reddit/r/MachineLearning"),
    ("r/LocalLLaMA",        "https://rsshub.app/reddit/r/LocalLLaMA"),
    ("r/robotics",          "https://rsshub.app/reddit/r/robotics"),
    ("r/singularity",       "https://rsshub.app/reddit/r/singularity"),
    # 中文來源
    ("IT之家-AI",   "https://www.ithome.com/rss/"),
    ("快科技-AI",   "https://news.mydrivers.com/rss/"),
    ("知乎-AI",     "https://rsshub.app/zhihu/search?query=AI人工智能"),
]

# ==================== 關鍵字分類 ====================
# AI Coding 相關
AI_CODING_KEYWORDS = [
    "cursor", "devin", "aider", "swe-agent", "swe agent",
    "github copilot", "copilot", "codeium", "tabnine", "replit",
    "code generation", "codegen", "ai coding", "ai code",
    "claude code", "coding agent", "programming agent",
    "devops ai", "ai developer", "code llm", "code model",
    "windsurf", "bolt.new", "v0.dev", "lovable",
]

# 具身智能 / 機器人 AI
EMBODIED_KEYWORDS = [
    "robot", "robotics", "humanoid", "embodied ai", "embodied intelligence",
    "optimus", "tesla bot", "boston dynamics", "spot", "atlas",
    "figure robot", "1x robot", "agility robotics", "unitree",
    "deepmind robot", "google robot", "physical ai",
    "manipulation", "locomotion", "dexterous",
    "具身智能", "機器人", "人形機器人",
]

# 通用 AI（補充用，最多 2 則）
GENERAL_AI_KEYWORDS = [
    "llm", "gpt-5", "gpt-4", "claude", "gemini", "openai", "anthropic",
    "mistral", "llama", "ai model", "foundation model", "multimodal",
    "transformer", "diffusion", "agi", "large language",
    "人工智能", "大模型", "大語言模型",
]

ALL_AI_KEYWORDS = AI_CODING_KEYWORDS + EMBODIED_KEYWORDS + GENERAL_AI_KEYWORDS


def categorize_ai(article: dict) -> str:
    text = (article["title"] + " " + article["summary"]).lower()
    if any(kw.lower() in text for kw in AI_CODING_KEYWORDS):
        return "AI_CODING"
    if any(kw.lower() in text for kw in EMBODIED_KEYWORDS):
        return "EMBODIED"
    return "GENERAL_AI"


def fetch_ai_news(hours: int = 24) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    articles = []

    for source_name, url in AI_FEEDS:
        try:
            feed = feedparser.parse(url, request_headers={
                "User-Agent": "Mozilla/5.0 (compatible; AINewsBot/1.0)"
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
                summary = entry.get("summary", entry.get("description", ""))[:500].strip()

                text = (title + " " + summary).lower()
                if any(kw.lower() in text for kw in ALL_AI_KEYWORDS):
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
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'來源[：:][^\n]*\n', '', text)
    text = re.sub(r'連結[：:][^\n]*\n', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def summarize_ai_with_deepseek(articles: list[dict]) -> str:
    client = OpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com",
    )

    tz_tw = timezone(timedelta(hours=8))
    today = datetime.now(tz_tw).strftime("%Y年%-m月%-d日")

    # Python 預先分類
    coding_lines, embodied_lines, general_lines = [], [], []
    for a in articles[:60]:
        entry = f"[{a['source']} | {a['date']}]\n標題：{a['title']}\n摘要：{a['summary']}"
        cat = categorize_ai(a)
        if cat == "AI_CODING":
            coding_lines.append(entry)
        elif cat == "EMBODIED":
            embodied_lines.append(entry)
        else:
            general_lines.append(entry)

    coding_raw   = "\n\n".join(coding_lines)   or "（今日無 AI Coding 相關新聞）"
    embodied_raw = "\n\n".join(embodied_lines) or "（今日無具身智能相關新聞）"
    general_raw  = "\n\n".join(general_lines[:10])  or "（今日無其他 AI 新聞）"

    prompt = f"""你是一位專業的 AI 領域每日新聞精選專家，側重「AI Coding」與「具身智能」兩個方向。
請整理成繁體中文摘要發送至 LINE（純文字，絕對不得包含任何網址或連結）。

【篩選規則】
✅ 優先：AI Coding（程式碼生成、開發工具、Agent、Cursor/Devin/Aider 等）
✅ 優先：具身智能（機器人、人形機器人、Figure/Optimus/Boston Dynamics 等）
✅ 補充：其他高價值 AI 動態（最多 2 則）
❌ 排除：純宣傳廣告、重複舊聞、無實質內容的報導

=== AI Coding 新聞 ===
{coding_raw}

=== 具身智能 / 機器人 AI 新聞 ===
{embodied_raw}

=== 其他 AI 新聞（補充用）===
{general_raw}

【輸出格式，嚴格遵守，不得輸出任何 http 網址】

AI 每日精選 - {today}
────────────────────
🔥 今日 AI 重點（3-5 則）

1. 標題
   摘要：（1-2句說明發生什麼）
   重要原因：（對 AI coding 或具身智能的影響）

2. 標題
   摘要：
   重要原因：

（依此類推，共 3-5 則）
────────────────────
💡 今日小結：（1-2句，點出明顯趨勢或長期追蹤訊號，若無可省略）"""

    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
    )

    result = resp.choices[0].message.content
    return strip_urls(result)


def send_line_message(text: str, channel_token: str, targets: list[str]):
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
    print("Fetching AI news...")
    articles = fetch_ai_news(hours=24)
    print(f"Found {len(articles)} AI articles")

    tz_tw = timezone(timedelta(hours=8))
    today = datetime.now(tz_tw).strftime("%Y年%-m月%-d日")

    if not articles:
        digest = (
            f"AI 每日精選 - {today}\n"
            "────────────────────\n"
            "⚠️ 今日未找到相關 AI 新聞，請手動查看 TechCrunch / VentureBeat 確認。"
        )
    else:
        print("Summarizing AI news with DeepSeek...")
        digest = summarize_ai_with_deepseek(articles)
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
