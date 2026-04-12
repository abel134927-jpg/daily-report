#!/usr/bin/env python3
"""由外部 Cron 服務執行，透過 GitHub API 觸發 workflow_dispatch。
比 GitHub Actions 的 schedule 更可靠，確保每天準時發送。
觸發 daily_report.yml → commit push → workflow_run 自動接著跑 daily_news.yml"""

import os
import sys
import requests

REPO     = "abel134927-jpg/daily-report"
WORKFLOW = "daily_report.yml"   # 觸發財經早報；完成後 workflow_run 自動觸發新聞推送
TOKEN    = os.environ["GITHUB_PAT"]

url = f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW}/dispatches"
resp = requests.post(
    url,
    headers={
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    },
    json={"ref": "main"},
    timeout=15,
)

if resp.status_code == 204:
    print("OK: workflow_dispatch triggered successfully")
else:
    print(f"FAIL: {resp.status_code} {resp.text}")
    sys.exit(1)
