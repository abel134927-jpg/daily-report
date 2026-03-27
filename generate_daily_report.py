#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日宏觀資訊綜合早報 - Daily Macro Market Briefing Generator
資料來源：Yahoo Finance, CNN Fear & Greed Index, RSS Feeds
可選：設定 ANTHROPIC_API_KEY 環境變數以啟用 AI 中文新聞分析
"""

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import feedparser
import json
import os
import sys
import warnings
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings('ignore')

# ============================================================
# CONFIG
# ============================================================

REPORT_DIR = Path(__file__).parent / "reports"
REPORT_DIR.mkdir(exist_ok=True)

NOW        = datetime.now()
TODAY_STR  = NOW.strftime('%Y-%m-%d')
REPORT_TIME= NOW.strftime('%Y-%m-%d %H:%M')
YEAR_START = datetime(NOW.year, 1, 1)

# ============================================================
# TICKER DEFINITIONS
# ============================================================

ASIAN_INDICES = [
    ('^N225',    '日經225'),
    ('^TWII',    '台灣加權'),
    ('^HSI',     '香港恆生'),
    ('000001.SS','上證綜指'),
    ('399001.SZ','深證成指'),
    ('^KS11',    '韓國KOSPI'),
    ('^AXJO',    '澳洲ASX200'),
]
EMERGING_INDICES = [
    ('^BSESN',  '印度SENSEX'),
    ('^NSEI',   '印度NIFTY50'),
    ('^JKSE',   '印尼雅加達綜合'),
    ('^SET.BK', '泰國SET'),
    ('^KLSE',   '馬來西亞KLCI'),
    ('PSEI.PS', '菲律賓PSEi'),
]
EUROPEAN_INDICES = [
    ('^GDAXI',   '德國DAX'),
    ('^FTSE',    '英國FTSE100'),
    ('^FCHI',    '法國CAC40'),
    ('^STOXX50E','歐洲STOXX50'),
    ('^SSMI',    '瑞士SMI'),
]
US_INDICES = [
    ('^GSPC', 'S&P 500'),
    ('^IXIC', '納斯達克'),
    ('^DJI',  '道瓊斯'),
    ('^RUT',  '羅素2000'),
    ('^SOX',  '費城半導體'),
]
COMMODITIES = [
    ('GC=F', '黃金'),
    ('SI=F', '白銀'),
    ('CL=F', '原油(WTI)'),
    ('BZ=F', '布蘭特原油'),
    ('HG=F', '銅'),
    ('NG=F', '天然氣'),
]
FOREX = [
    ('DX-Y.NYB', '美元指數'),
    ('EURUSD=X', 'EUR/USD'),
    ('USDJPY=X', 'USD/JPY'),
    ('GBPUSD=X', 'GBP/USD'),
    ('CNY=X',    'USD/CNY'),
    ('TWD=X',    'USD/TWD'),
]
BONDS = [
    ('^IRX', '美國3月期',  0.25),
    ('^FVX', '美國5年期',  5),
    ('^TNX', '美國10年期', 10),
    ('^TYX', '美國30年期', 30),
]
CRYPTO = [
    ('BTC-USD',  'Bitcoin',  'BTC'),
    ('ETH-USD',  'Ethereum', 'ETH'),
    ('BNB-USD',  'BNB',      'BNB'),
    ('SOL-USD',  'Solana',   'SOL'),
    ('XRP-USD',  'XRP',      'XRP'),
    ('ADA-USD',  'Cardano',  'ADA'),
    ('DOGE-USD', 'Dogecoin', 'DOGE'),
]
COUNTRY_ETFS = [
    ('SPY','美國'), ('VGK','歐洲'), ('EWJ','日本'), ('FXI','中國/港股'),
    ('EWT','台灣'), ('EWY','韓國'), ('INDA','印度'), ('VWO','新興市場'),
    ('EIDO','印尼'), ('VNM','越南'), ('THD','泰國'), ('EWM','馬來西亞'),
    ('EPHE','菲律賓'), ('EWA','澳洲'),
]
SECTOR_ETFS = [
    ('XLK','資訊科技'), ('XLU','公用事業'), ('XLF','金融'), ('XLI','工業'),
    ('XLE','能源'), ('XLY','非必需消費'), ('XLC','通訊服務'), ('XLRE','房地產'),
    ('XLB','原材料'), ('XLV','醫療保健'), ('XLP','必需消費'),
]
BOND_ETFS = [
    ('SHY','1-3年國債'), ('IEI','3-7年國債'), ('IEF','7-10年國債'),
    ('TLH','10-20年國債'), ('TLT','20年+國債'), ('LQD','投資級債'),
    ('HYG','非投資等債'), ('EMB','新興債'), ('VWOB','新興美元債'), ('EMLC','新興本地債'),
]
US_WATCHLIST = [
    ('AAPL','Apple'), ('MSFT','Microsoft'), ('NVDA','NVIDIA'), ('AMD','AMD'),
    ('TSLA','Tesla'), ('AMZN','Amazon'), ('GOOGL','Alphabet'), ('META','Meta'),
    ('NFLX','Netflix'), ('ARM','Arm Holdings'), ('SMCI','Supermicro'),
    ('HPE','Hewlett Packard'), ('AVGO','Broadcom'), ('QCOM','Qualcomm'),
    ('MU','Micron'), ('INTC','Intel'), ('JPM','JPMorgan'), ('BAC','Bank of America'),
    ('GS','Goldman Sachs'), ('MS','Morgan Stanley'), ('XOM','ExxonMobil'),
    ('CVX','Chevron'), ('BA','Boeing'), ('LMT','Lockheed Martin'),
    ('JBLU','JetBlue'), ('DAL','Delta Air'), ('UAL','United Airlines'),
    ('LEN','Lennar'), ('DHI','D.R. Horton'), ('Z','Zillow'),
    ('PDD','PDD Holdings'), ('VRSN','Verisign'), ('PAYX','Paychex'),
    ('GNRC','Generac'), ('COIN','Coinbase'), ('LLY','Eli Lilly'),
    ('NEE','NextEra Energy'), ('SPCE','Virgin Galactic'),
]

# ============================================================
# UTILITY
# ============================================================

def fmt_flow(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return 'N/A'
    a = abs(v)
    if a >= 1e9:  return f'{v/1e8:+.1f}億'
    if a >= 1e8:  return f'{v/1e8:+.2f}億'
    if a >= 1e6:  return f'{v/1e4:+.0f}萬'
    if a >= 1e4:  return f'{v/1e4:+.1f}萬'
    return f'{v:+.0f}'

def css_cls(pct):
    if pct is None or (isinstance(pct, float) and np.isnan(pct)): return 'neu'
    return 'up' if pct > 0 else 'dn' if pct < 0 else 'neu'

def arrow(pct):
    if pct is None or (isinstance(pct, float) and np.isnan(pct)): return '—'
    if pct > 2:  return '▲▲'
    if pct > 0:  return '▲'
    if pct < -2: return '▼▼'
    if pct < 0:  return '▼'
    return '—'

def calc_daily_money_flow(df):
    """每日原始資金流量：MFM × Volume × Close。
    MFM > 0 表示當日收盤偏高位（買壓），< 0 表示偏低位（賣壓）。"""
    hl = (df['High'] - df['Low']).values
    close = df['Close'].values
    low   = df['Low'].values
    high  = df['High'].values
    vol   = df['Volume'].values
    mfm = np.where(hl > 0, ((close - low) - (high - close)) / hl, 0.0)
    return pd.Series(mfm * vol * close, index=df.index)

# ============================================================
# DATA FETCHING
# ============================================================

def bulk_download(symbols, days=400):
    result = {}
    if not symbols: return result
    start = (NOW - timedelta(days=days)).strftime('%Y-%m-%d')
    end   = NOW.strftime('%Y-%m-%d')
    try:
        raw = yf.download(symbols, start=start, end=end, interval='1d',
                          group_by='ticker', auto_adjust=True, progress=False, threads=True)
    except Exception as e:
        print(f'  [download error] {e}')
        return result

    single = (len(symbols) == 1)
    for sym in symbols:
        try:
            df = raw if single else raw[sym]
            df = df.dropna(how='all')
            if not df.empty:
                result[sym] = df
        except Exception:
            pass
    return result


def get_quote(sym, cache):
    df = cache.get(sym)
    if df is None or df.empty: return None
    try:
        close = df['Close'].dropna()
        if len(close) < 2: return None
        cur  = float(close.iloc[-1])
        prev = float(close.iloc[-2])
        chg  = cur - prev
        pct  = (chg / prev) * 100 if prev else 0
        ytd  = close[close.index >= YEAR_START]
        ytd_pct = ((cur / float(ytd.iloc[0])) - 1) * 100 if len(ytd) > 0 else 0.0
        return {'price': cur, 'prev': prev, 'chg': chg, 'pct': pct, 'ytd': ytd_pct}
    except Exception:
        return None


def calc_etf_flow(sym, cache):
    df = cache.get(sym)
    if df is None or df.empty: return None
    df = df[df['Close'].notna()].copy()
    if len(df) < 25: return None
    try:
        mf = calc_daily_money_flow(df)
        n  = len(mf)

        daily   = float(mf.iloc[-1])
        weekly  = float(mf.iloc[max(-5,  -n):].sum())
        monthly = float(mf.iloc[max(-21, -n):].sum())
        ytd_total = float(mf[mf.index >= YEAR_START].sum())

        return {'daily': daily, 'weekly': weekly, 'monthly': monthly, 'ytd': ytd_total}
    except Exception:
        return None


def fetch_fear_greed():
    try:
        r = requests.get(
            'https://production.dataviz.cnn.io/index/fearandgreed/graphdata',
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://edition.cnn.com/markets/fear-and-greed',
                'Origin': 'https://edition.cnn.com',
            },
            timeout=10)
        if r.status_code == 200:
            d = r.json()['fear_and_greed']
            def sr(k): v = d.get(k); return round(float(v), 1) if v is not None else None
            return {
                'score': sr('score'), 'rating': d.get('rating', ''),
                'prev': sr('previous_close'), 'week': sr('previous_1_week'),
                'month': sr('previous_1_month'), 'year': sr('previous_1_year'),
            }
    except Exception:
        pass
    return {'score': None, 'rating': '', 'prev': None, 'week': None, 'month': None, 'year': None}


# ============================================================
# NEWS MODULE
# ============================================================

RSS_FEEDS = [
    ('Reuters',     'https://feeds.reuters.com/reuters/businessNews'),
    ('MarketWatch', 'https://feeds.content.dowjones.io/public/rss/mw_marketpulse'),
    ('Yahoo Finance','https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EGSPC&region=US&lang=en-US'),
    ('Investing.com','https://www.investing.com/rss/news_301.rss'),
    ('CNBC',        'https://feeds.nbcnews.com/nbcnews/public/business'),
]

HIGH_KW = ['fed','fomc','interest rate','rate decision','gdp','inflation','cpi','pce',
           'trade war','tariff','war ','attack','default','recession','crash',
           'sanctions','nuclear','emergency','crisis','federal reserve']
MID_KW  = ['earnings','ipo','acquisition','merger','bankruptcy','layoff','jobs',
            'unemployment','housing','china','oil','opec','gold','bitcoin',
            'rate hike','rate cut','stimulus','budget','deficit','debt ceiling']
BULL_KW = ['rises','rally','rallies','surges','jumps','beats','exceeds','strong',
           'growth','record high','gains','upgrades','boosts','recovery','positive',
           'higher','increases','expanded','profits','outperforms']
BEAR_KW = ['falls','drops','plunges','misses','weak','decline','lower','concern',
           'worry','fears','cuts','losses','downgrades','recession','crash',
           'negative','decreases','contracts','layoffs','defaults','slumps']
GLOBAL_KW = ['china','europe','global','world','international','opec','imf',
              'g7','g20','japan','euro','uk ','asia','emerging market']

def classify_news(title, summary=''):
    text = (title + ' ' + summary).lower()
    impact = '高' if any(k in text for k in HIGH_KW) else \
             '中' if any(k in text for k in MID_KW)  else '低'
    bull = sum(1 for k in BULL_KW if k in text)
    bear = sum(1 for k in BEAR_KW if k in text)
    direction = '利多' if bull > bear else '利空' if bear > bull else '中性'
    scope = '全球' if any(k in text for k in GLOBAL_KW) else '美國'
    return {'impact': impact, 'direction': direction, 'scope': scope}


def _parse_yf_item(n):
    """Parse a yfinance news item (handles both old and new API structure)."""
    content = n.get('content', {}) or {}
    title   = content.get('title') or n.get('title', '')
    summary = content.get('summary') or n.get('summary', '')

    canonical = content.get('canonicalUrl') or {}
    link = canonical.get('url', '') if isinstance(canonical, dict) else n.get('link', '#')
    if not link: link = '#'

    provider = content.get('provider') or {}
    publisher = provider.get('displayName', 'Yahoo Finance') if isinstance(provider, dict) else \
                n.get('publisher', 'Yahoo Finance')

    pub_date = content.get('pubDate', '') or ''
    try:
        pub_time = datetime.strptime(pub_date, '%Y-%m-%dT%H:%M:%SZ').strftime('%m-%d %H:%M')
    except Exception:
        ts = n.get('providerPublishTime', 0)
        pub_time = datetime.fromtimestamp(ts).strftime('%m-%d %H:%M') if ts else ''

    return {'title': title, 'summary': summary[:300],
            'publisher': publisher, 'link': link, 'time': pub_time}


def fetch_news_yfinance():
    items, seen = [], set()
    for sym in ['^GSPC', '^IXIC', '^DJI', 'SPY', 'QQQ', 'GLD', 'USO', 'BTC-USD']:
        try:
            for n in (yf.Ticker(sym).news or [])[:5]:
                item = _parse_yf_item(n)
                if item['title'] and item['title'] not in seen:
                    seen.add(item['title'])
                    items.append(item)
        except Exception:
            pass
    return items


def fetch_news_rss():
    items, seen = [], set()
    for source, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in (feed.entries or [])[:6]:
                title = entry.get('title', '').strip()
                if not title or title in seen: continue
                seen.add(title)
                summary = entry.get('summary', entry.get('description', ''))
                # Strip HTML tags from summary
                import re
                summary = re.sub(r'<[^>]+>', ' ', summary).strip()[:300]
                link = entry.get('link', '#')
                pub  = entry.get('published', '')[:16]
                items.append({'title': title, 'summary': summary,
                               'publisher': source, 'link': link, 'time': pub})
        except Exception:
            pass
    return items


def translate_to_zh(text):
    """
    Translate English text to Traditional Chinese via free MyMemory API.
    Falls back to original text on failure.
    """
    if not text or not text.strip():
        return text
    try:
        r = requests.get(
            'https://api.mymemory.translated.net/get',
            params={'q': text[:480], 'langpair': 'en|zh-TW'},
            timeout=8,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        if r.status_code == 200:
            data = r.json()
            if data.get('responseStatus') == 200:
                translated = data['responseData']['translatedText']
                # MyMemory returns QUERY LENGTH LIMIT REACHED when exceeded
                if 'QUERY LENGTH LIMIT' not in translated:
                    return translated
    except Exception:
        pass
    return text


def summarize_with_claude(items, api_key):
    """
    Use Claude Haiku to generate Chinese title + summary + classification.
    Returns list of dicts or None if API unavailable/fails.
    """
    if not api_key:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        news_text = '\n'.join(
            f'{i+1}. 標題：{n["title"]}\n   摘要：{n["summary"][:200]}'
            for i, n in enumerate(items)
        )
        prompt = (
            '你是專業財經分析師。以下是英文財經新聞，請逐一處理，為每則新聞輸出：\n'
            '  - title：中文標題翻譯（20字以內，精準）\n'
            '  - summary：中文市場分析（30-45字，說明對市場的影響）\n'
            '  - impact：影響程度（高/中/低）\n'
            '  - direction：市場方向（利多/利空/中性）\n'
            '  - scope：影響範圍（美國/全球/亞洲）\n\n'
            f'新聞：\n{news_text}\n\n'
            '僅返回 JSON 陣列，格式：\n'
            '[{"title":"...","summary":"...","impact":"高","direction":"利多","scope":"全球"}, ...]'
        )
        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=2500,
            messages=[{'role': 'user', 'content': prompt}]
        )
        raw = msg.content[0].text.strip()
        # Extract JSON array even if there's surrounding text
        import re
        m = re.search(r'\[.*\]', raw, re.DOTALL)
        return json.loads(m.group() if m else raw)
    except Exception as e:
        print(f'    Claude API 錯誤：{e}')
        return None


def fetch_and_process_news():
    """Collect, deduplicate, classify, translate, and optionally AI-summarize news."""
    print('    抓取 Yahoo Finance 新聞...')
    yf_news = fetch_news_yfinance()
    print(f'    Yahoo Finance: {len(yf_news)} 則')

    print('    抓取 RSS 新聞源...')
    rss_news = fetch_news_rss()
    print(f'    RSS feeds: {len(rss_news)} 則')

    seen, all_items = set(), []
    for n in yf_news + rss_news:
        if n['title'] and n['title'] not in seen:
            seen.add(n['title'])
            all_items.append(n)

    # Rule-based classification
    for item in all_items:
        item.update(classify_news(item['title'], item.get('summary', '')))

    # Sort: high impact first
    impact_order = {'高': 0, '中': 1, '低': 2}
    all_items.sort(key=lambda x: (impact_order.get(x.get('impact', '低'), 2),
                                  -len(x.get('summary', ''))))
    all_items = all_items[:10]

    # Try Claude AI (high quality: Chinese title + analysis)
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    print('    嘗試 Claude AI 分析...')
    ai_results = summarize_with_claude(all_items, api_key)

    if ai_results:
        print(f'    [OK] Claude AI 完成（{len(ai_results)} 則）')
        for i, item in enumerate(all_items):
            if i < len(ai_results):
                cr = ai_results[i]
                item['zh_title']   = cr.get('title', '')
                item['zh_summary'] = cr.get('summary', '')
                item['impact']     = cr.get('impact', item['impact'])
                item['direction']  = cr.get('direction', item['direction'])
                item['scope']      = cr.get('scope', item['scope'])
    else:
        # Fallback: free translation via MyMemory
        print('    [OK] 使用免費翻譯引擎（MyMemory）...')
        for i, item in enumerate(all_items):
            print(f'      翻譯 {i+1}/{len(all_items)}: {item["title"][:40]}...')
            item['zh_title'] = translate_to_zh(item['title'])
            # Translate short summary if available
            if item.get('summary'):
                short_en = item['summary'][:150]
                item['zh_summary'] = translate_to_zh(short_en)

    return all_items


# ============================================================
# OTHER DATA
# ============================================================

def screen_hot_stocks(cache):
    buy_list, sell_list = [], []
    for sym, name in US_WATCHLIST:
        df = cache.get(sym)
        if df is None or df.empty or len(df) < 22: continue
        try:
            df2  = df[df['Close'].notna()]
            avg  = float(df2['Volume'].tail(21).iloc[:-1].mean())
            if avg == 0: continue
            vr   = float(df2['Volume'].iloc[-1]) / avg
            cur  = float(df2['Close'].iloc[-1])
            prev = float(df2['Close'].iloc[-2])
            pct  = (cur / prev - 1) * 100
            item = {'sym': sym, 'name': name, 'price': cur, 'pct': pct, 'vr': vr}
            if pct > 0 and vr >= 1.5:  buy_list.append(item)
            elif pct < 0 and vr >= 2.5: sell_list.append(item)
        except Exception: pass
    buy_list.sort(key=lambda x: x['pct'], reverse=True)
    sell_list.sort(key=lambda x: x['pct'])
    return buy_list[:6], sell_list[:6]


def determine_cycle(tnx_df, fvx_df, tip_df, ief_df):
    try:
        spread    = (tnx_df['Close'] - fvx_df['Close']).dropna()
        sma       = spread.rolling(20).mean().dropna()
        growth_up = bool(sma.iloc[-1] > sma.iloc[-10]) if len(sma) >= 10 else True
        ratio     = (tip_df['Close'] / ief_df['Close']).dropna()
        rma       = ratio.rolling(20).mean().dropna()
        infl_up   = bool(rma.iloc[-1] > rma.iloc[-10]) if len(rma) >= 10 else True
        table = {
            (True, True):   ('overheating', '過熱期'),
            (True, False):  ('recovery',    '復甦期'),
            (False, True):  ('stagflation', '滯脹期（Stagflation）'),
            (False, False): ('recession',   '衰退期'),
        }
        key, zh = table[(growth_up, infl_up)]
        return {'key': key, 'zh': zh, 'growth_up': growth_up, 'infl_up': infl_up,
                'spread': float(tnx_df['Close'].iloc[-1] - fvx_df['Close'].iloc[-1])}
    except Exception:
        return {'key': 'unknown', 'zh': '無法判斷',
                'growth_up': None, 'infl_up': None, 'spread': None}


# ============================================================
# COLLECT
# ============================================================

def collect():
    print('  [1/6] 下載主要市場數據...')
    main_syms = (
        [s for s,_ in ASIAN_INDICES] + [s for s,_ in EMERGING_INDICES] +
        [s for s,_ in EUROPEAN_INDICES] + [s for s,_ in US_INDICES] +
        [s for s,*_ in COMMODITIES] + [s for s,_ in FOREX] +
        [s for s,*_ in BONDS] + [s for s,*_ in CRYPTO] +
        ['TIP', 'IEF', '^VIX']
    )
    cache = bulk_download(main_syms, 400)

    print('  [2/6] 下載 ETF 資金流向數據...')
    cache.update(bulk_download([s for s,_ in COUNTRY_ETFS + SECTOR_ETFS + BOND_ETFS], 400))

    print('  [3/6] 下載熱門股票數據...')
    cache.update(bulk_download([s for s,_ in US_WATCHLIST], 60))

    print('  [4/6] 計算指標...')
    def q(s): return get_quote(s, cache)

    d = {
        'asian':    [{'sym':s,'name':n,**(q(s) or {})} for s,n in ASIAN_INDICES],
        'emerging': [{'sym':s,'name':n,**(q(s) or {})} for s,n in EMERGING_INDICES],
        'european': [{'sym':s,'name':n,**(q(s) or {})} for s,n in EUROPEAN_INDICES],
        'us':       [{'sym':s,'name':n,**(q(s) or {})} for s,n in US_INDICES],
        'commodities':[{'sym':s,'name':n,**(q(s) or {})} for s,n,*_ in COMMODITIES],
        'forex':    [{'sym':s,'name':n,**(q(s) or {})} for s,n in FOREX],
        'bonds':    [{'sym':s,'name':n,'yr':yr,**(q(s) or {})} for s,n,yr in BONDS],
        'crypto':   [{'sym':s,'name':n,'tick':t,**(q(s) or {})} for s,n,t in CRYPTO],
        'country_flows': [{'sym':s,'name':n,**(calc_etf_flow(s,cache) or {})} for s,n in COUNTRY_ETFS],
        'sector_flows':  [{'sym':s,'name':n,**(calc_etf_flow(s,cache) or {})} for s,n in SECTOR_ETFS],
        'bond_flows':    [{'sym':s,'name':n,**(calc_etf_flow(s,cache) or {})} for s,n in BOND_ETFS],
        'vix': q('^VIX'), 'tnx': q('^TNX'), 'fvx': q('^FVX'),
    }
    d['cycle'] = determine_cycle(
        cache.get('^TNX', pd.DataFrame()), cache.get('^FVX', pd.DataFrame()),
        cache.get('TIP',  pd.DataFrame()), cache.get('IEF',  pd.DataFrame()),
    )

    print('  [5/6] 抓取情緒指標與新聞...')
    d['fg'] = fetch_fear_greed()
    d['buy_stocks'], d['sell_stocks'] = screen_hot_stocks(cache)

    print('  [6/6] 處理新聞...')
    d['news'] = fetch_and_process_news()

    return d


# ============================================================
# HTML TEMPLATE
# ============================================================

PAGE_CSS = """
/* ===== RESET & BASE ===== */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'Segoe UI', 'Microsoft JhengHei', 'PingFang TC', 'Noto Sans TC', Arial, sans-serif;
  font-size: 11.5px;
  line-height: 1.5;
  color: #1e293b;
  background: #eef2f7;
}

/* ===== WRAPPER ===== */
.page {
  max-width: 960px;
  margin: 24px auto;
  background: #fff;
  box-shadow: 0 4px 24px rgba(0,0,0,.12);
  border-radius: 4px;
  overflow: hidden;
}

/* ===== MASTHEAD ===== */
.masthead {
  background: linear-gradient(135deg, #0a1628 0%, #0f2a4a 55%, #163460 100%);
  padding: 28px 36px 22px;
  color: #fff;
  position: relative;
}
.masthead::after {
  content: '';
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg, #f0b429, #e85d04, #f0b429);
}
.masthead-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.masthead-title h1 {
  font-size: 19px;
  font-weight: 700;
  letter-spacing: 3px;
  line-height: 1.3;
}
.masthead-title h2 {
  font-size: 11px;
  font-weight: 300;
  letter-spacing: 5px;
  opacity: .65;
  margin-top: 3px;
}
.masthead-date {
  text-align: right;
  font-size: 11px;
  opacity: .75;
  line-height: 1.8;
}
.masthead-meta {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid rgba(255,255,255,.15);
  font-size: 10.5px;
  opacity: .8;
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}

/* ===== SUMMARY TICKER ===== */
.ticker-bar {
  display: flex;
  background: #0f2a4a;
  border-bottom: 1px solid #1e3a5f;
  overflow: hidden;
}
.ticker-item {
  flex: 1;
  text-align: center;
  padding: 10px 8px;
  border-right: 1px solid #1e3a5f;
  color: #fff;
}
.ticker-item:last-child { border-right: none; }
.ticker-item .t-label { font-size: 9px; text-transform: uppercase; letter-spacing: 1px; opacity: .6; }
.ticker-item .t-price { font-size: 14px; font-weight: 700; margin: 2px 0; }
.ticker-item .t-chg   { font-size: 10px; }
.ticker-item.up  .t-price { color: #22c55e; }
.ticker-item.dn  .t-price { color: #ef4444; }
.ticker-item.neu .t-price { color: #f0b429; }
.ticker-item.up  .t-chg   { color: #86efac; }
.ticker-item.dn  .t-chg   { color: #fca5a5; }

/* ===== CONTENT BODY ===== */
.body-wrap { padding: 24px 32px; }

/* ===== SECTION ===== */
.sec { margin-bottom: 22px; }
.sec-hdr {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  padding-bottom: 7px;
  border-bottom: 2px solid #0f2a4a;
}
.sec-num {
  background: #0f2a4a;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  width: 22px; height: 22px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.sec-title {
  font-size: 13px;
  font-weight: 700;
  color: #0f2a4a;
  letter-spacing: .5px;
}
.sub-hdr {
  font-size: 11px;
  font-weight: 600;
  color: #475569;
  padding: 5px 0 4px;
  margin: 12px 0 5px;
  border-bottom: 1px solid #e2e8f0;
}

/* ===== TABLES ===== */
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
}
th {
  background: #1e293b;
  color: #e2e8f0;
  padding: 6px 10px;
  text-align: left;
  font-weight: 600;
  font-size: 10.5px;
  white-space: nowrap;
}
td {
  padding: 5px 10px;
  border-bottom: 1px solid #f1f5f9;
  vertical-align: middle;
}
tr:nth-child(even) td { background: #f8fafc; }
tr:hover td { background: #eff6ff; }
.num { text-align: right; font-family: 'Consolas', 'Courier New', monospace; white-space: nowrap; }
th.num { text-align: right; font-family: inherit; font-weight: 600; }
.sym { color: #94a3b8; font-family: 'Consolas', monospace; font-size: 10px; }
.trend { padding-left: 32px !important; text-align: center; }

/* ===== COLORS ===== */
.up  { color: #16a34a; font-weight: 600; }
.dn  { color: #dc2626; font-weight: 600; }
.neu { color: #94a3b8; }

/* ===== NEWS CARDS ===== */
.news-grid { display: flex; flex-direction: column; gap: 8px; }
.news-card {
  border: 1px solid #e2e8f0;
  border-left: 4px solid #94a3b8;
  border-radius: 0 6px 6px 0;
  padding: 10px 14px;
  background: #fff;
}
.news-card.h-high { border-left-color: #dc2626; }
.news-card.h-mid  { border-left-color: #f59e0b; }
.news-card.h-low  { border-left-color: #94a3b8; }

.news-badges {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}
.badge {
  display: inline-flex;
  align-items: center;
  padding: 1px 7px;
  border-radius: 10px;
  font-size: 10px;
  font-weight: 600;
  white-space: nowrap;
}
.badge-high { background: #fee2e2; color: #b91c1c; }
.badge-mid  { background: #fef3c7; color: #92400e; }
.badge-low  { background: #f1f5f9; color: #64748b; }
.badge-bull { background: #dcfce7; color: #166534; }
.badge-bear { background: #fee2e2; color: #b91c1c; }
.badge-neu  { background: #f1f5f9; color: #475569; }
.badge-scope{ background: #eff6ff; color: #1d4ed8; }

.news-title {
  font-size: 11.5px;
  font-weight: 600;
  color: #1e293b;
  line-height: 1.5;
  margin-bottom: 4px;
}
.news-title a { color: inherit; text-decoration: none; }
.news-title a:hover { color: #1d4ed8; }
.news-summary {
  font-size: 11px;
  color: #475569;
  line-height: 1.5;
  margin-bottom: 4px;
}
.news-en-ref {
  font-size: 10px;
  color: #94a3b8;
  margin-bottom: 3px;
  font-style: italic;
  line-height: 1.4;
}
.news-meta {
  font-size: 10px;
  color: #94a3b8;
}

/* ===== SENTIMENT ===== */
.sent-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 14px;
}
.sent-card {
  background: #0f2a4a;
  color: #fff;
  padding: 14px;
  border-radius: 6px;
  text-align: center;
}
.sent-card .sc-label { font-size: 9.5px; opacity: .6; text-transform: uppercase; letter-spacing: 1px; }
.sent-card .sc-val   { font-size: 22px; font-weight: 700; margin: 5px 0 2px; }
.sent-card .sc-sub   { font-size: 10px; opacity: .7; }

/* FEAR GREED BAR */
.fg-wrap {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 12px 16px;
  margin-bottom: 12px;
}
.fg-bar {
  height: 12px;
  border-radius: 6px;
  background: linear-gradient(to right, #dc2626 0%, #f59e0b 30%, #eab308 50%, #22c55e 75%, #15803d 100%);
  position: relative;
  margin: 8px 0 5px;
}
.fg-needle {
  position: absolute;
  width: 2px; height: 18px;
  top: -3px;
  background: #1e293b;
  border-radius: 1px;
  transform: translateX(-50%);
}
.fg-labels { display: flex; justify-content: space-between; font-size: 9.5px; color: #94a3b8; }

/* CYCLE */
.cycle-wrap { display: flex; gap: 20px; align-items: flex-start; }
.cycle-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 3px; flex-shrink: 0; }
.cycle-cell {
  padding: 12px 14px;
  text-align: center;
  font-size: 11px;
  background: #f1f5f9;
  color: #94a3b8;
  border-radius: 3px;
}
.cycle-cell.active {
  background: #0f2a4a;
  color: #fff;
  font-weight: 700;
}

/* ===== HOT STOCKS ===== */
.vol-chip {
  display: inline-block;
  background: #0f2a4a;
  color: #fff;
  font-size: 9.5px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 8px;
}

/* ===== TWO COL ===== */
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }

/* ===== FOOTER ===== */
.report-footer {
  background: #f8fafc;
  border-top: 2px solid #e2e8f0;
  padding: 16px 32px;
  font-size: 10px;
  color: #64748b;
  text-align: center;
  line-height: 1.8;
}
.report-footer .disclaimer {
  color: #dc2626;
  margin-top: 5px;
  font-weight: 500;
}

/* ===== PRINT BUTTON ===== */
.fab {
  position: fixed;
  bottom: 28px; right: 28px;
  background: #0f2a4a;
  color: #fff;
  border: none;
  padding: 13px 22px;
  border-radius: 50px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  box-shadow: 0 6px 20px rgba(0,0,0,.35);
  z-index: 999;
  transition: all .2s;
  display: flex; align-items: center; gap: 8px;
}
.fab:hover { background: #163460; transform: translateY(-2px); }

/* ===== PRINT ===== */
@media print {
  body   { background: #fff; font-size: 10px; }
  .fab   { display: none !important; }
  .page  { margin: 0; box-shadow: none; border-radius: 0; max-width: 100%; }
  .body-wrap { padding: 16px 20px; }

  /* Force colours to print */
  .masthead, .ticker-bar, .ticker-item, .sec-num, th,
  .sent-card, .cycle-cell.active, .vol-chip {
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
  .news-card.h-high, .news-card.h-mid, .news-card.h-low {
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
  .badge { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  tr:nth-child(even) td { -webkit-print-color-adjust: exact; print-color-adjust: exact; }

  /* Page layout */
  @page { margin: 1cm 1.2cm; size: A4; }
  .sec  { page-break-inside: auto; break-inside: auto; }
  .sec-hdr { page-break-after: avoid; break-after: avoid; }
  .news-card { page-break-inside: avoid; break-inside: avoid; }
  .sent-row { page-break-inside: avoid; break-inside: avoid; }
  .cycle-wrap { page-break-inside: avoid; break-inside: avoid; }
  .two-col { page-break-inside: auto; break-inside: auto; }
  tr { page-break-inside: avoid; break-inside: avoid; }

  /* Repeat table headers on page break */
  thead { display: table-header-group; }
}

@media (max-width: 760px) {
  .ticker-bar  { flex-wrap: wrap; }
  .two-col     { grid-template-columns: 1fr; }
  .sent-row    { grid-template-columns: repeat(2, 1fr); }
  .body-wrap   { padding: 14px 16px; }
}
"""


# ============================================================
# HTML HELPERS
# ============================================================

def fear_greed_gauge_svg(score, fg_zh, fg_color):
    import math
    cx, cy = 200, 162
    R_out, R_in = 142, 84

    segments = [
        (0,   25,  '#dc2626', ['極度', '恐懼']),
        (25,  45,  '#f97316', ['恐懼']),
        (45,  55,  '#eab308', ['中性']),
        (55,  75,  '#4ade80', ['貪婪']),
        (75, 100,  '#16a34a', ['極度', '貪婪']),
    ]

    def s2a(s): return math.radians(180 - s * 1.8)
    def pt(r, s): a = s2a(s); return cx + r*math.cos(a), cy - r*math.sin(a)

    # Arc segments
    paths = []
    for s1, s2, col, _ in segments:
        ox1,oy1 = pt(R_out, s1); ox2,oy2 = pt(R_out, s2)
        ix2,iy2 = pt(R_in,  s2); ix1,iy1 = pt(R_in,  s1)
        paths.append(
            f'<path d="M {ox1:.1f},{oy1:.1f} A {R_out},{R_out} 0 0,1 {ox2:.1f},{oy2:.1f} '
            f'L {ix2:.1f},{iy2:.1f} A {R_in},{R_in} 0 0,0 {ix1:.1f},{iy1:.1f} Z" '
            f'fill="{col}" stroke="#fff" stroke-width="2"/>'
        )

    # Zone labels inside ring
    R_mid = (R_out + R_in) // 2
    zone_lbls = []
    for s1, s2, _, lines in segments:
        s_mid = (s1 + s2) / 2
        mx, my = pt(R_mid, s_mid)
        if len(lines) == 2:
            zone_lbls.append(f'<text x="{mx:.1f}" y="{my-5.5:.1f}" text-anchor="middle" dominant-baseline="middle" font-size="9" fill="#fff" font-weight="700">{lines[0]}</text>')
            zone_lbls.append(f'<text x="{mx:.1f}" y="{my+5.5:.1f}" text-anchor="middle" dominant-baseline="middle" font-size="9" fill="#fff" font-weight="700">{lines[1]}</text>')
        else:
            zone_lbls.append(f'<text x="{mx:.1f}" y="{my:.1f}" text-anchor="middle" dominant-baseline="middle" font-size="9" fill="#fff" font-weight="700">{lines[0]}</text>')

    # Tick marks at segment boundaries
    ticks = []
    for s in [0, 25, 45, 55, 75, 100]:
        tx1, ty1 = pt(R_in - 2, s)
        tx2, ty2 = pt(R_out + 2, s)
        ticks.append(f'<line x1="{tx1:.1f}" y1="{ty1:.1f}" x2="{tx2:.1f}" y2="{ty2:.1f}" stroke="#fff" stroke-width="2.5"/>')

    # 兩端刻度 (0 和 100) 在弧線端點旁，y=cy 不會被截掉
    end_lbls = []
    for s_val, lbl, anch in [(0, '0', 'end'), (100, '100', 'start')]:
        lx, ly = pt(R_out + 18, s_val)
        end_lbls.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anch}" dominant-baseline="middle" font-size="10" fill="#94a3b8">{lbl}</text>')

    # Needle
    eff = score if score is not None else 50
    na = s2a(eff)
    nl = 120
    nx, ny = cx + nl*math.cos(na), cy - nl*math.sin(na)
    score_str = f'{score:.0f}' if score is not None else 'N/A'

    return (
        f'<svg viewBox="0 0 400 248" style="width:100%;max-width:360px;display:block;margin:0 auto">'
        f'{"".join(paths)}'
        f'{"".join(ticks)}'
        f'{"".join(zone_lbls)}'
        f'{"".join(end_lbls)}'
        f'<line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" stroke="#1e293b" stroke-width="4" stroke-linecap="round"/>'
        f'<circle cx="{cx}" cy="{cy}" r="11" fill="#1e293b"/>'
        f'<circle cx="{cx}" cy="{cy}" r="5" fill="#f0b429"/>'
        f'<text x="{cx}" y="{cy+40}" text-anchor="middle" font-size="30" font-weight="700" fill="{fg_color}">{score_str}</text>'
        f'<text x="{cx}" y="{cy+60}" text-anchor="middle" font-size="12" fill="#475569">{fg_zh}</text>'
        f'</svg>'
    )


def economic_cycle_gauge_svg(cyc):
    import math
    key  = cyc.get('key', 'unknown')
    zh   = cyc.get('zh', '未知')
    spr  = cyc.get('spread')
    spr_str = f'{spr:+.3f}' if spr is not None else 'N/A'
    g_up = cyc.get('growth_up')
    i_up = cyc.get('infl_up')
    g_dir = '↑ 上升' if g_up else '↓ 下降'
    i_dir = '↑ 上升' if i_up else '↓ 下降'

    cx, cy, r = 150, 140, 108

    def pt(radius, a_deg):
        a = math.radians(a_deg)
        return cx + radius * math.cos(a), cy - radius * math.sin(a)

    # 4 sectors: standard-math angles, sweep=0 (CCW in SVG = correct for each quadrant)
    sectors = [
        ('recovery',    0,   90,  '#22c55e', '復甦期',   45),
        ('overheating', 90,  180, '#f97316', '過熱期',  135),
        ('stagflation', 180, 270, '#f59e0b', '滯脹期',  225),
        ('recession',   270, 360, '#94a3b8', '衰退期',  315),
    ]

    elems = []
    elems.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#f1f5f9" stroke="#e2e8f0" stroke-width="1"/>')

    for s_key, a1, a2, col, lbl, mid_a in sectors:
        x1, y1 = pt(r, a1)
        x2, y2 = pt(r, a2)
        is_active = (s_key == key)
        op = '1' if is_active else '0.35'
        elems.append(
            f'<path d="M {cx},{cy} L {x1:.1f},{y1:.1f} A {r},{r} 0 0,0 {x2:.1f},{y2:.1f} Z" '
            f'fill="{col}" opacity="{op}"/>'
        )
        lx, ly = pt(r * 0.62, mid_a)
        fw = '800' if is_active else '500'
        fs = '11' if is_active else '10'
        elems.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" dominant-baseline="middle" font-size="{fs}" fill="#fff" font-weight="{fw}">{lbl}</text>')

    # Axis dividers
    elems.append(f'<line x1="{cx-r}" y1="{cy}" x2="{cx+r}" y2="{cy}" stroke="rgba(255,255,255,0.65)" stroke-width="2"/>')
    elems.append(f'<line x1="{cx}" y1="{cy-r}" x2="{cx}" y2="{cy+r}" stroke="rgba(255,255,255,0.65)" stroke-width="2"/>')

    # Axis labels
    elems.append(f'<text x="{cx+r+9}" y="{cy}" dominant-baseline="middle" font-size="9" fill="#64748b">成長↑</text>')
    elems.append(f'<text x="{cx-r-9}" y="{cy}" text-anchor="end" dominant-baseline="middle" font-size="9" fill="#64748b">成長↓</text>')
    elems.append(f'<text x="{cx}" y="{cy-r-10}" text-anchor="middle" font-size="9" fill="#64748b">通脹↑</text>')
    elems.append(f'<text x="{cx}" y="{cy+r+14}" text-anchor="middle" font-size="9" fill="#64748b">通脹↓</text>')

    # Needle
    angles = {'recovery': 45, 'overheating': 135, 'stagflation': 225, 'recession': 315}
    na  = math.radians(angles.get(key, 0))
    nl  = r * 0.83
    nx, ny = cx + nl * math.cos(na), cy - nl * math.sin(na)
    elems.append(f'<line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" stroke="#1e293b" stroke-width="3.5" stroke-linecap="round"/>')
    elems.append(f'<circle cx="{cx}" cy="{cy}" r="9" fill="#1e293b"/>')
    elems.append(f'<circle cx="{cx}" cy="{cy}" r="4" fill="#f0b429"/>')

    vbh = cy + r + 28   # 底部軸標籤下方留白
    svg = (
        f'<svg viewBox="0 0 300 {vbh}" style="width:100%;max-width:260px;display:block">'
        f'{"".join(elems)}'
        f'</svg>'
    )

    # 右側文字欄
    info = (
        f'<div style="flex:1;min-width:140px;padding-left:8px;font-size:11px;color:#475569;line-height:1.9">'
        f'<div style="font-size:14px;font-weight:700;color:#0f2a4a;margin-bottom:6px">{zh}</div>'
        f'<div>📈 成長方向：<b>{g_dir}</b></div>'
        f'<div>🌡 通脹方向：<b>{i_dir}</b></div>'
        f'<div style="margin-top:10px;padding:8px 10px;background:#fff;border:1px solid #e2e8f0;border-radius:6px">'
        f'<div style="font-size:9.5px;color:#94a3b8;letter-spacing:.5px">10Y-5Y 利差</div>'
        f'<div style="font-size:20px;font-weight:700;color:#0f2a4a;margin:2px 0">{spr_str}</div>'
        f'</div>'
        f'<div style="font-size:9px;color:#94a3b8;margin-top:8px;line-height:1.7">'
        f'判斷依據：<br>10Y-5Y利差 20日MA斜率<br>+ TIP/IEF比率 20日MA斜率'
        f'</div>'
        f'</div>'
    )

    return (
        f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">'
        f'<div style="flex:0 0 auto">{svg}</div>'
        f'{info}'
        f'</div>'
    )


def find(lst, sym):
    return next((x for x in lst if x.get('sym') == sym), {})

def ticker_card(label, val_str, pct):
    if pct is None: return f'<div class="ticker-item neu"><div class="t-label">{label}</div><div class="t-price">N/A</div><div class="t-chg">—</div></div>'
    c = css_cls(pct)
    s = '+' if pct > 0 else ''
    return f'<div class="ticker-item {c}"><div class="t-label">{label}</div><div class="t-price">{val_str}</div><div class="t-chg">{s}{pct:.2f}%</div></div>'

def index_row(item):
    p = item.get('price')
    if p is None: return f'<tr><td>{item["name"]}</td><td colspan="5" class="neu">N/A</td></tr>'
    c  = css_cls(item.get('pct', 0))
    yc = css_cls(item.get('ytd', 0))
    return (f'<tr><td>{item["name"]}</td>'
            f'<td class="num">{p:,.2f}</td>'
            f'<td class="num {c}">{item.get("chg",0):+,.2f}</td>'
            f'<td class="num {c}">{item.get("pct",0):+.2f}%</td>'
            f'<td class="{c} trend">{arrow(item.get("pct"))}</td>'
            f'<td class="num {yc}">{item.get("ytd",0):+.2f}%</td></tr>')

def flow_row(item):
    def td(v):
        if v is None: return '<td class="num neu">—</td>'
        c = 'up' if v > 0 else 'dn' if v < 0 else 'neu'
        return f'<td class="num {c}">{fmt_flow(v)}</td>'
    return (f'<tr><td>{item["name"]}</td><td class="sym">{item.get("sym","")}</td>'
            f'{td(item.get("daily"))}{td(item.get("weekly"))}'
            f'{td(item.get("monthly"))}{td(item.get("ytd"))}</tr>')

def hot_row(item, is_buy):
    c = 'up' if is_buy else 'dn'
    return (f'<tr><td>{item["name"]}</td><td class="sym">{item["sym"]}</td>'
            f'<td class="num">${item["price"]:.2f}</td>'
            f'<td class="num {c}">{item["pct"]:+.2f}%</td>'
            f'<td class="num"><span class="vol-chip">{item["vr"]:.1f}x</span></td></tr>')

def indices_block(subtitle, rows):
    trs = ''.join(index_row(r) for r in rows)
    return f'''<div class="sub-hdr">{subtitle}</div>
    <table>
      <thead><tr><th>指數</th><th class="num">收盤價</th><th class="num">漲跌</th><th class="num">漲跌幅</th><th class="trend">趨勢</th><th class="num">年初至今</th></tr></thead>
      <tbody>{trs}</tbody>
    </table>'''

FLOW_HDR = '<thead><tr><th>名稱</th><th>ETF</th><th class="num">當日</th><th class="num">近一週</th><th class="num">近一月</th><th class="num">年初至今</th></tr></thead>'

def news_card_html(item):
    impact    = item.get('impact', '低')
    direction = item.get('direction', '中性')
    scope     = item.get('scope', '美國')
    en_title  = item.get('title', '')
    zh_title  = item.get('zh_title', '')
    zh_summary= item.get('zh_summary', '')
    link      = item.get('link', '#')
    publisher = item.get('publisher', '')
    time_str  = item.get('time', '')

    card_cls = 'h-high' if impact == '高' else 'h-mid' if impact == '中' else 'h-low'
    imp_cls  = 'badge-high' if impact == '高' else 'badge-mid' if impact == '中' else 'badge-low'
    dir_cls  = 'badge-bull' if direction == '利多' else 'badge-bear' if direction == '利空' else 'badge-neu'

    # Primary headline: Chinese title (translated or AI)
    headline = zh_title if zh_title else en_title
    # Secondary line: Chinese summary; show English original in muted small text
    summary_html = ''
    if zh_summary:
        summary_html = f'<div class="news-summary">{zh_summary}</div>'
    # Always show English original as small reference
    en_ref = f'<div class="news-en-ref">{en_title}</div>'

    return f'''<div class="news-card {card_cls}">
  <div class="news-badges">
    <span class="badge {imp_cls}">{impact}影響</span>
    <span class="badge {dir_cls}">{direction}</span>
    <span class="badge badge-scope">{scope}</span>
  </div>
  <div class="news-title"><a href="{link}" target="_blank">{headline}</a></div>
  {summary_html}
  {en_ref}
  <div class="news-meta">{publisher}{" · " if publisher and time_str else ""}{time_str}</div>
</div>'''


# ============================================================
# GENERATE HTML
# ============================================================

def generate_html(d):
    sp5  = find(d['us'], '^GSPC')
    nsdq = find(d['us'], '^IXIC')
    dji  = find(d['us'], '^DJI')
    n225 = find(d['asian'], '^N225')
    twii = find(d['asian'], '^TWII')
    gold = find(d['commodities'], 'GC=F')
    oil  = find(d['commodities'], 'CL=F')
    dxy  = find(d['forex'], 'DX-Y.NYB')
    btc  = find(d['crypto'], 'BTC-USD')
    eth  = find(d['crypto'], 'ETH-USD')
    vix  = d.get('vix') or {}
    tnx  = d.get('tnx') or {}
    fg   = d.get('fg') or {}
    cyc  = d.get('cycle') or {}

    # --- Ticker bar ---
    ticker_html = ''.join([
        ticker_card('S&P 500', f'{sp5.get("price",0):,.0f}'  if sp5.get("price") else 'N/A', sp5.get('pct')),
        ticker_card('NASDAQ',  f'{nsdq.get("price",0):,.0f}' if nsdq.get("price") else 'N/A', nsdq.get('pct')),
        ticker_card('DOW',     f'{dji.get("price",0):,.0f}'  if dji.get("price") else 'N/A',  dji.get('pct')),
        ticker_card('日經225', f'{n225.get("price",0):,.0f}' if n225.get("price") else 'N/A', n225.get('pct')),
        ticker_card('黃金',    f'${gold.get("price",0):,.0f}'if gold.get("price") else 'N/A', gold.get('pct')),
        ticker_card('WTI原油', f'${oil.get("price",0):.2f}'  if oil.get("price") else 'N/A',  oil.get('pct')),
        ticker_card('DXY',     f'{dxy.get("price",0):.2f}'   if dxy.get("price") else 'N/A',  dxy.get('pct')),
        ticker_card('BTC',     f'${btc.get("price",0):,.0f}' if btc.get("price") else 'N/A',  btc.get('pct')),
    ])

    # --- Indices ---
    idx_html = (
        indices_block('亞洲市場', d['asian']) +
        indices_block('新興市場', d['emerging']) +
        indices_block('歐洲市場', d['european']) +
        indices_block('美國市場', d['us'])
    )

    # --- News ---
    news_items = d.get('news', [])
    if news_items:
        news_html = '<div class="news-grid">' + ''.join(news_card_html(n) for n in news_items) + '</div>'
        has_ai = any(n.get('zh_summary') for n in news_items) and os.environ.get('ANTHROPIC_API_KEY')
        has_tr = any(n.get('zh_title') for n in news_items)
        if has_ai:
            ai_note = ' <span style="font-size:9.5px;color:#22c55e;font-weight:600">● Claude AI 中文分析</span>'
        elif has_tr:
            ai_note = ' <span style="font-size:9.5px;color:#64748b">● 機器翻譯中文</span>'
        else:
            ai_note = ''
    else:
        news_html = '<p style="color:#94a3b8;padding:12px">暫無最新新聞</p>'
        ai_note = ''

    # --- Commodities ---
    comm_rows = ''
    for item in d['commodities']:
        p = item.get('price')
        if p is None: continue
        c = css_cls(item.get('pct', 0))
        comm_rows += (f'<tr><td>{item["name"]}</td><td class="num">${p:.2f}</td>'
                      f'<td class="num {c}">{item.get("chg",0):+.2f}</td>'
                      f'<td class="num {c}">{item.get("pct",0):+.2f}%</td>'
                      f'<td class="{c} trend">{arrow(item.get("pct"))}</td></tr>')

    # --- Forex ---
    fx_rows = ''
    for item in d['forex']:
        p = item.get('price')
        if p is None: continue
        c = css_cls(item.get('pct', 0))
        dec = 4 if p < 10 else 2
        fx_rows += (f'<tr><td>{item["name"]}</td><td class="num">{p:.{dec}f}</td>'
                    f'<td class="num {c}">{item.get("chg",0):+.{dec}f}</td>'
                    f'<td class="num {c}">{item.get("pct",0):+.2f}%</td>'
                    f'<td class="{c} trend">{arrow(item.get("pct"))}</td></tr>')

    # --- Bonds ---
    bond_rows = ''
    for item in d['bonds']:
        p = item.get('price')
        if p is None: continue
        c = css_cls(item.get('pct', 0))
        bond_rows += (f'<tr><td>{item["name"]}</td><td class="num">{p:.3f}%</td>'
                      f'<td class="num {c}">{item.get("chg",0):+.4f}</td>'
                      f'<td class="num {c}">{item.get("pct",0):+.2f}%</td>'
                      f'<td class="{c} trend">{arrow(item.get("pct"))}</td></tr>')

    # --- Sentiment ---
    fg_score  = fg.get('score')
    fg_rating = fg.get('rating', '')
    fg_zh = {'extreme fear':'極度恐懼','fear':'恐懼','neutral':'中性',
              'greed':'貪婪','extreme greed':'極度貪婪'}.get(fg_rating.lower(), fg_rating or 'N/A')
    fg_str   = str(fg_score) if fg_score is not None else 'N/A'
    fg_color = '#ef4444' if (fg_score or 50) < 30 else '#f59e0b' if (fg_score or 50) < 60 else '#22c55e'
    fg_pct   = f'{min(max(fg_score or 50, 0), 100)}%'

    vix_val   = vix.get('price')
    vix_str   = f'{vix_val:.2f}' if vix_val else 'N/A'
    vix_color = '#ef4444' if (vix_val or 0) > 25 else '#f59e0b' if (vix_val or 0) > 18 else '#22c55e'
    vix_label = '高波動' if (vix_val or 0) > 25 else '中波動' if (vix_val or 0) > 18 else '低波動'

    tnx_val = tnx.get('price')
    tnx_str = f'{tnx_val:.3f}%' if tnx_val else 'N/A'
    dxy_val = dxy.get('price')
    dxy_str = f'{dxy_val:.2f}' if dxy_val else 'N/A'
    spr_val = cyc.get('spread')
    spr_str = f'{spr_val:.3f}' if spr_val is not None else 'N/A'

    fg_hist_row = ''
    if fg_score is not None:
        fg_hist_row = (f'<tr><td>恐懼與貪婪</td>'
                       f'<td class="num">{fg_score}</td><td class="num">{fg.get("prev","—")}</td>'
                       f'<td class="num">{fg.get("week","—")}</td><td class="num">{fg.get("month","—")}</td>'
                       f'<td class="num">{fg.get("year","—")}</td></tr>')

    def cc(name, label):
        cls = 'active' if cyc.get('key') == name else ''
        return f'<div class="cycle-cell {cls}">{label}</div>'

    g_dir = '↑ 上升' if cyc.get('growth_up') else '↓ 下降'
    i_dir = '↑ 上升' if cyc.get('infl_up')  else '↓ 下降'

    # --- Flows ---
    c_rows = ''.join(flow_row(x) for x in d['country_flows'])
    s_rows = ''.join(flow_row(x) for x in d['sector_flows'])
    b_rows = ''.join(flow_row(x) for x in d['bond_flows'])

    # --- Hot stocks ---
    buy_rows  = ''.join(hot_row(x, True)  for x in d['buy_stocks'])  or '<tr><td colspan="5" class="neu">暫無符合條件</td></tr>'
    sell_rows = ''.join(hot_row(x, False) for x in d['sell_stocks']) or '<tr><td colspan="5" class="neu">暫無符合條件</td></tr>'

    # --- Crypto ---
    crypto_rows = ''
    for item in d['crypto']:
        p = item.get('price')
        if p is None: continue
        c = css_cls(item.get('pct', 0))
        p_str = f'${p:,.2f}' if p > 1 else f'${p:.5f}'
        crypto_rows += (f'<tr><td>{item["name"]}</td><td class="sym">{item["tick"]}</td>'
                        f'<td class="num">{p_str}</td>'
                        f'<td class="num {c}">{item.get("chg",0):+.2f}</td>'
                        f'<td class="num {c}">{item.get("pct",0):+.2f}%</td>'
                        f'<td class="{c} trend">{arrow(item.get("pct"))}</td></tr>')

    # ---- ASSEMBLE ----
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>每日宏觀資訊綜合早報 · {TODAY_STR}</title>
<style>{PAGE_CSS}</style>
</head>
<body>

<div style="position:fixed;bottom:28px;right:28px;z-index:999;display:flex;flex-direction:column;align-items:flex-end;gap:6px">
  <div style="background:rgba(15,42,74,0.92);color:#cbd5e1;font-size:10px;padding:6px 12px;border-radius:8px;line-height:1.7;text-align:right;max-width:210px">
    列印時請在設定中<br>關閉「頁首及頁尾」<br>以移除左下角網址浮水印
  </div>
  <button class="fab" onclick="window.print()">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
      <polyline points="6 9 6 2 18 2 18 9"></polyline>
      <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path>
      <rect x="6" y="14" width="12" height="8"></rect>
    </svg>
    列印 / 下載 PDF
  </button>
</div>

<div class="page">

<!-- MASTHEAD -->
<div class="masthead">
  <div class="masthead-top">
    <div class="masthead-title">
      <h1>每日宏觀資訊綜合早報</h1>
      <h2>Daily Macro Market Briefing</h2>
    </div>
    <div class="masthead-date">
      <div style="font-size:15px;font-weight:700">{TODAY_STR}</div>
      <div>生成時間 {REPORT_TIME}</div>
    </div>
  </div>
  <div class="masthead-meta">
    <span>&#128202; Yahoo Finance</span>
    <span>&#128200; CNN Fear &amp; Greed Index</span>
    <span>&#128240; RSS: Reuters / MarketWatch / CNBC</span>
    <span>&#9888; 本報告僅供參考，不構成投資建議</span>
  </div>
</div>

<!-- TICKER BAR -->
<div class="ticker-bar">{ticker_html}</div>

<!-- BODY -->
<div class="body-wrap">

<!-- 1. INDICES -->
<div class="sec">
  <div class="sec-hdr"><div class="sec-num">1</div><div class="sec-title">各國指數表現</div></div>
  {idx_html}
</div>

<!-- 2. NEWS -->
<div class="sec">
  <div class="sec-hdr">
    <div class="sec-num">2</div>
    <div class="sec-title">宏觀重點新聞{ai_note}</div>
  </div>
  <div style="font-size:10px;color:#94a3b8;margin-bottom:10px">
    篩選標準：高影響（Fed/GDP/通脹/地緣政治）｜中影響（企業財報/大宗商品）｜低影響（一般市場動態）
  </div>
  {news_html}
</div>

<!-- 3. COMMODITIES / FOREX / BONDS -->
<div class="sec">
  <div class="sec-hdr"><div class="sec-num">3</div><div class="sec-title">商品、外匯與債券</div></div>
  <div class="two-col">
    <div>
      <div class="sub-hdr">大宗商品</div>
      <table>
        <thead><tr><th>商品</th><th class="num">價格</th><th class="num">漲跌</th><th class="num">漲跌幅</th><th class="trend">趨勢</th></tr></thead>
        <tbody>{comm_rows}</tbody>
      </table>
    </div>
    <div>
      <div class="sub-hdr">外匯市場</div>
      <table>
        <thead><tr><th>貨幣對</th><th class="num">匯率</th><th class="num">漲跌</th><th class="num">漲跌幅</th><th class="trend">趨勢</th></tr></thead>
        <tbody>{fx_rows}</tbody>
      </table>
    </div>
  </div>
  <div class="sub-hdr" style="margin-top:14px">債券殖利率</div>
  <table>
    <thead><tr><th>債券</th><th class="num">殖利率</th><th class="num">變動</th><th class="num">幅度</th><th class="trend">趨勢</th></tr></thead>
    <tbody>{bond_rows}</tbody>
  </table>
</div>

<!-- 4. SENTIMENT -->
<div class="sec">
  <div class="sec-hdr"><div class="sec-num">4</div><div class="sec-title">市場情緒指標</div></div>
  <div class="sent-row">
    <div class="sent-card">
      <div class="sc-label">CNN 恐懼貪婪</div>
      <div class="sc-val" style="color:{fg_color}">{fg_str}</div>
      <div class="sc-sub">{fg_zh}</div>
    </div>
    <div class="sent-card">
      <div class="sc-label">VIX 恐慌指數</div>
      <div class="sc-val" style="color:{vix_color}">{vix_str}</div>
      <div class="sc-sub">{vix_label}</div>
    </div>
    <div class="sent-card">
      <div class="sc-label">美10Y 殖利率</div>
      <div class="sc-val" style="color:#f0b429">{tnx_str}</div>
      <div class="sc-sub">美元指數 {dxy_str}</div>
    </div>
    <div class="sent-card">
      <div class="sc-label">10Y-5Y 利差</div>
      <div class="sc-val" style="color:#93c5fd">{spr_str}</div>
      <div class="sc-sub">殖利率曲線</div>
    </div>
  </div>

  <div class="fg-wrap" style="padding:10px 16px 0">
    {fear_greed_gauge_svg(fg_score, fg_zh, fg_color)}
  </div>

  <table style="margin-bottom:14px">
    <thead><tr><th>指標</th><th class="num">當前</th><th class="num">前日</th><th class="num">一週前</th><th class="num">一月前</th><th class="num">一年前</th></tr></thead>
    <tbody>{fg_hist_row or '<tr><td colspan="6" class="neu">無法取得</td></tr>'}</tbody>
  </table>

  <div class="sub-hdr">經濟週期指示器</div>
  <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;margin-top:8px;padding:10px 16px;text-align:center">
    {economic_cycle_gauge_svg(cyc)}
  </div>
</div>

<!-- 5. CAPITAL FLOWS -->
<div class="sec">
  <div class="sec-hdr"><div class="sec-num">5</div><div class="sec-title">全球資金流向脈動</div></div>
  <div style="font-size:10px;color:#94a3b8;margin-bottom:8px">基於 ETF 每日原始資金流量（MFM × 成交量 × 收盤價）累加</div>
  <table>
    {FLOW_HDR}
    <tbody>{c_rows}</tbody>
  </table>
</div>

<!-- 6. SECTOR FLOWS -->
<div class="sec">
  <div class="sec-hdr"><div class="sec-num">6</div><div class="sec-title">GICS 11大板塊 &amp; 債券資金流向</div></div>
  <div class="sub-hdr">板塊 ETF 資金流向</div>
  <table>{FLOW_HDR}<tbody>{s_rows}</tbody></table>
  <div class="sub-hdr" style="margin-top:14px">債券市場資金流向</div>
  <table>{FLOW_HDR}<tbody>{b_rows}</tbody></table>
</div>

<!-- 7. HOT STOCKS -->
<div class="sec">
  <div class="sec-hdr"><div class="sec-num">7</div><div class="sec-title">當日熱門美股</div></div>
  <div style="font-size:10px;color:#94a3b8;margin-bottom:10px">
    篩選邏輯：資金追捧（量比 ≥ 1.5x + 上漲）｜資金出清（量比 ≥ 2.5x + 下跌）
  </div>
  <div class="two-col">
    <div>
      <div class="sub-hdr" style="color:#16a34a">&#128293; 資金追捧</div>
      <table>
        <thead><tr><th>股票</th><th>代碼</th><th class="num">收盤價</th><th class="num">漲跌幅</th><th class="num">量比</th></tr></thead>
        <tbody>{buy_rows}</tbody>
      </table>
    </div>
    <div>
      <div class="sub-hdr" style="color:#dc2626">&#9888;&#65039; 資金出清</div>
      <table>
        <thead><tr><th>股票</th><th>代碼</th><th class="num">收盤價</th><th class="num">漲跌幅</th><th class="num">量比</th></tr></thead>
        <tbody>{sell_rows}</tbody>
      </table>
    </div>
  </div>
</div>

<!-- 8. CRYPTO -->
<div class="sec">
  <div class="sec-hdr"><div class="sec-num">8</div><div class="sec-title">加密貨幣市場</div></div>
  <table>
    <thead><tr><th>幣種</th><th>代號</th><th class="num">價格（USD）</th><th class="num">24h 漲跌</th><th class="num">漲跌幅</th><th class="trend">趨勢</th></tr></thead>
    <tbody>{crypto_rows}</tbody>
  </table>
</div>

</div><!-- /body-wrap -->

<!-- FOOTER -->
<div class="report-footer">
  <div>報告製作時間：{REPORT_TIME}（本地時間）</div>
  <div>資料來源：Yahoo Finance · CNN Fear &amp; Greed Index · Reuters · MarketWatch · CNBC</div>
  <div>資金流向基於 ETF 每日原始資金流量（MFM &times; 成交量 &times; 收盤價）累加計算</div>
  <div class="disclaimer">本報告僅供參考，不構成任何投資建議。投資有風險，入市需謹慎。</div>
</div>

</div><!-- /page -->
</body>
</html>"""


# ============================================================
# MAIN
# ============================================================

def main():
    print('=' * 52)
    print('  每日宏觀資訊綜合早報 生成器')
    print(f'  日期：{TODAY_STR}')
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if api_key:
        print('  模式：Claude AI 中文分析（回退：MyMemory 免費翻譯）')
    else:
        print('  模式：MyMemory 免費翻譯（提示：設定 ANTHROPIC_API_KEY 啟用 AI 分析）')
    print('=' * 52)

    d = collect()

    print('\n  [生成] 產生 HTML 報告...')
    html = generate_html(d)

    out = REPORT_DIR / f'report_{TODAY_STR}.html'
    latest = Path(__file__).parent / 'latest_report.html'
    for path in [out, latest]:
        path.write_text(html, encoding='utf-8')

    news_count = len(d.get('news', []))
    tr_count   = sum(1 for n in d.get('news', []) if n.get('zh_title'))
    ai_count   = sum(1 for n in d.get('news', []) if n.get('zh_summary') and os.environ.get('ANTHROPIC_API_KEY'))
    print(f'\n  [完成] 報告已生成')
    print(f'         路徑：{out}')
    mode = f'Claude AI {ai_count}則' if ai_count else f'MyMemory翻譯 {tr_count}則'
    print(f'         新聞：{news_count} 則（{mode}）')
    print(f'\n  用瀏覽器開啟後，點擊右下角「列印/下載PDF」→ 選「另存為PDF」')

    try:
        import webbrowser
        webbrowser.open(str(latest))
    except Exception:
        pass


if __name__ == '__main__':
    main()
