/**
 * 每日財經新聞 - Google Apps Script 雲端觸發器
 * ================================================
 * 跑在 Google 雲端，每天 07:00 台灣時間自動觸發 GitHub Actions。
 * 不需要自己的電腦開機，永久免費。
 *
 * 設定步驟（只需一次，約 5 分鐘）：
 * 1. 前往 https://script.google.com → 點「新增專案」
 * 2. 刪除預設程式碼，貼上這整個檔案的內容
 * 3. 點上方「專案名稱」(Untitled)，改名為「每日財經新聞觸發器」
 * 4. 設定 GitHub PAT（密碼）：
 *    - 左側齒輪「專案設定」→ 拉到底找「指令碼屬性」
 *    - 點「新增屬性」→ 屬性名稱填 GITHUB_PAT，值填你的 token (ghp_...)
 *    - 存儲
 * 5. 設定每日排程：
 *    - 左側時鐘圖示「觸發條件」→ 右下角「+ 新增觸發條件」
 *    - 選擇要執行的函式：triggerDailyNews
 *    - 選取活動來源：時間驅動
 *    - 選取時間型觸發條件類型：日計時器
 *    - 選取當天時間：上午 7 時至 8 時
 *    - 時區：(GMT+08:00) Asia/Taipei  ← 重要！
 *    - 儲存
 * 6. 完成！Google 每天 07:00~08:00 台灣時間自動觸發新聞推送
 *
 * 如何取得 GitHub PAT：
 *   GitHub → Settings → Developer settings → Personal access tokens
 *   → Tokens (classic) → Generate new token → 勾選 workflow 權限
 */

// ============================================================
// 主要觸發函式（排程器呼叫這個）
// ============================================================
function triggerDailyNews() {
  const props = PropertiesService.getScriptProperties();
  const pat   = props.getProperty('GITHUB_PAT');

  if (!pat) {
    throw new Error('找不到 GITHUB_PAT，請在「專案設定 → 指令碼屬性」中設定。');
  }

  const url = 'https://api.github.com/repos/abel134927-jpg/daily-report/actions/workflows/daily_report.yml/dispatches';

  const options = {
    method:             'post',
    contentType:        'application/json',
    headers: {
      'Authorization': 'Bearer ' + pat,
      'Accept':        'application/vnd.github.v3+json',
    },
    payload:            JSON.stringify({ ref: 'main' }),
    muteHttpExceptions: true,
  };

  const response = UrlFetchApp.fetch(url, options);
  const code     = response.getResponseCode();
  const now      = Utilities.formatDate(new Date(), 'Asia/Taipei', 'yyyy-MM-dd HH:mm:ss');

  if (code === 204) {
    Logger.log('[' + now + '] OK: GitHub Actions 觸發成功 → 財經早報開始生成，約 10 分鐘後 LINE 收到新聞');
  } else {
    const msg = '[' + now + '] FAIL: HTTP ' + code + ' - ' + response.getContentText();
    Logger.log(msg);
    throw new Error(msg);  // 讓 Google 發 email 通知你觸發失敗
  }
}

// ============================================================
// 測試用：手動執行確認設定是否正確
// ============================================================
function testTrigger() {
  Logger.log('=== 開始測試觸發 ===');
  triggerDailyNews();
  Logger.log('=== 測試完成 ===');
}
