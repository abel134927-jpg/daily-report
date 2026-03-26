# 每日電腦硬體新聞機器人

每天自動蒐集筆記本電腦、GPU、CPU 等硬體新聞，由 Claude AI 整理後透過 LINE Messaging API 推送到手機。

## 架構

```
RSS 來源（Tom's Hardware / TechPowerUp / Videocardz 等）
    ↓ feedparser 抓取 + 關鍵字過濾
Claude claude-opus-4-6 整理成繁體中文純文字摘要
    ↓
LINE Messaging API 推送到你的 LINE
```

---

## 部署步驟

### 步驟 1：建立 LINE Official Account 與 Messaging API

1. 前往 [LINE Developers Console](https://developers.line.biz/)，登入
2. 建立一個 **Provider**（若已有可跳過）
3. 點選「Create a new channel」→ 選 **Messaging API**
4. 填寫頻道名稱（例如：硬體新聞機器人），完成建立
5. 進入頻道設定頁 → **Messaging API** 分頁：
   - 找到「Channel access token」→ 點「Issue」產生 Token，複製備用
   - 在「Auto-reply messages」設定中，**關閉**自動回覆（避免干擾）

### 步驟 2：加機器人為好友並取得你的 User ID

1. 在頻道設定頁的 **Messaging API** 分頁，掃描 QR code 把機器人加為好友
2. 取得你的 LINE User ID（二選一）：

   **方法 A（推薦）**：設定 Webhook URL 接收一次後取得
   - 或使用以下快速方法：

   **方法 B（快速）**：在 LINE Developers Console → Basic Settings 分頁，
   最下方可以看到「Your user ID」，這就是你的 User ID（格式：`Uxxxxxxxxxx`）

### 步驟 3：建立 GitHub Repository 並推送

```bash
cd "D:/project/每日新聞"
git init
git add .
git commit -m "初始化硬體新聞機器人"
git remote add origin https://github.com/你的帳號/每日新聞.git
git push -u origin main
```

### 步驟 4：設定 GitHub Secrets

在 GitHub Repository 頁面：
**Settings → Secrets and variables → Actions → New repository secret**

新增以下三個 Secret：

| 名稱 | 填入內容 | 說明 |
|------|---------|------|
| `ANTHROPIC_API_KEY` | `sk-ant-xxxxxxxx` | Anthropic API Key |
| `LINE_CHANNEL_ACCESS_TOKEN` | `xxxxxx...` | LINE 頻道存取權杖 |
| `LINE_USER_ID` | `Uxxxxxxxxxx` | 你的 LINE User ID |

### 步驟 5：測試

推送後進入 **Actions** 頁面 → 「每日電腦硬體新聞」→ **Run workflow** 手動觸發，
確認 LINE 有收到訊息後即完成設定。

---

## 發送時間

預設每天台灣時間 **08:00** 發送。

如需修改，編輯 `.github/workflows/daily_news.yml` 的 cron：

```yaml
- cron: "0 0 * * *"   # UTC 00:00 = 台灣 08:00
- cron: "0 1 * * *"   # UTC 01:00 = 台灣 09:00
- cron: "30 23 * * *" # UTC 23:30 = 台灣 07:30
```

---

## 新聞來源

- Tom's Hardware
- TechPowerUp
- Videocardz
- Wccftech
- The Verge
- IT之家
- 快科技
- Laptop Mag
- NotebookCheck
