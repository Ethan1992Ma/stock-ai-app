import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import google.generativeai as genai  # 新增 AI 模組
from ta.trend import SMAIndicator, MACD
from ta.momentum import RSIIndicator
from datetime import time, timedelta

# --- 1. 網頁設定 ---
st.set_page_config(page_title="AI 智能操盤戰情室 (VIP 終極整合版)", layout="wide", initial_sidebar_state="expanded")

# --- 定義全域配色常數 ---
COLOR_UP = "#059a81"
COLOR_DOWN = "#f23645"
COLOR_NEUTRAL = "#adb5bd"
MACD_BULL_GROW = "#2db09c"
MACD_BULL_SHRINK = "#a8e0d1"
MACD_BEAR_GROW = "#ff6666"
MACD_BEAR_SHRINK = "#ffcccc"
VOL_EXPLODE = "#C70039"
VOL_NORMAL = "#FF5733"
VOL_SHRINK = "#FFC300"
VOL_MA_LINE = "#000000"
COLOR_VWAP = "#FF9800"

# --- 2. CSS 美化 ---
st.markdown(f"""
    <style>
    :root {{ --primary-color: #ff4b4b; --background-color: #f8f9fa; --secondary-background-color: #ffffff; --text-color: #000000; --font: sans-serif; }}
    .stApp {{ background-color: #f8f9fa; }}
    h1, h2, h3, h4, h5, h6, p, div, label, li, span {{ color: #000000 !important; }}
    .stTextInput > label, .stNumberInput > label, .stRadio > label {{ color: #000000 !important; }}
    
    .txt-up-vip {{ color: {COLOR_UP} !important; font-weight: bold; }}
    .txt-down-vip {{ color: {COLOR_DOWN} !important; font-weight: bold; }}
    .txt-gray-vip {{ color: {COLOR_NEUTRAL} !important; }}
    
    .metric-card {{ background-color: #ffffff; padding: 20px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 10px; border: 1px solid #f0f0f0; position: relative; }}
    .metric-title {{ color: #6c757d !important; font-size: 0.9rem; font-weight: 700; margin-bottom: 5px; }}
    .metric-value {{ font-size: 1.8rem; font-weight: 800; color: #212529 !important; }}
    .metric-sub {{ font-size: 0.9rem; margin-top: 5px; }} 
    
    .ext-price-box {{ background-color: #f1f3f5; padding: 4px 8px; border-radius: 6px; font-size: 0.85rem; font-weight: 600; color: #666 !important; margin-top: 8px; display: inline-block; }}
    .ext-label {{ font-size: 0.75rem; color: #999 !important; margin-right: 5px; }}
    .spark-scale {{ position: absolute; right: 15px; top: 55%; transform: translateY(-50%); text-align: right; font-size: 0.7rem; line-height: 1.4; font-weight: 600; }}

    .ai-summary-card {{ background-color: #e3f2fd; padding: 20px; border-radius: 15px; border-left: 5px solid #2196f3; margin-top: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; }}
    .ai-title {{ font-weight: bold; font-size: 1.2rem; color: #0d47a1 !important; margin-bottom: 10px; display: flex; align-items: center; }}
    .ai-content {{ font-size: 1rem; color: #333 !important; line-height: 1.6; white-space: pre-line; }}

    .ma-container {{ display: flex; flex-wrap: wrap; gap: 10px; background-color: #ffffff; padding: 20px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #f0f0f0; margin-bottom: 20px; }}
    .ma-box {{ flex: 1 1 100px; text-align: center; padding: 10px; background-color: #f8f9fa; border-radius: 10px; border: 1px solid #dee2e6; }}
    .ma-label {{ font-size: 0.8rem; font-weight: bold; color: #666 !important; margin-bottom: 5px; }}
    .ma-val {{ font-size: 1.1rem; font-weight: 800; }}
    
    .status-badge {{ padding: 4px 8px; border-radius: 6px; font-size: 0.85rem; font-weight: bold; color: white !important; display: inline-block; margin-top: 8px; }}
    .bg-up {{ background-color: {COLOR_UP}; }} .bg-down {{ background-color: {COLOR_DOWN}; }} .bg-gray {{ background-color: {COLOR_NEUTRAL}; }} .bg-blue {{ background-color: #0d6efd; }}

    .js-plotly-plot .plotly .modebar {{ display: none !important; }}
    .calc-box {{ background-color: #ffffff; padding: 15px; border-radius: 12px; border: 1px solid #eee; margin-bottom: 15px; }}
    .calc-header {{ font-size: 1rem; font-weight: bold; color: #444 !important; margin-bottom: 10px; border-left: 4px solid {COLOR_UP}; padding-left: 8px; }}
    .calc-result {{ background-color: #f8f9fa; padding: 10px; border-radius: 8px; text-align: center; margin-top: 10px; }}
    .calc-res-title {{ font-size: 0.8rem; color: #888 !important; }}
    .calc-res-val {{ font-size: 1.4rem; font-weight: bold; }}
    .fee-badge {{ background-color: #fff3cd; color: #856404 !important; padding: 5px 10px; border-radius: 5px; font-size: 0.8rem; border: 1px solid #ffeeba; margin-bottom: 15px; display: flex; align-items: center; gap: 5px; }}
    div[role="radiogroup"] {{ background-color: transparent; border: none; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. 數據抓取函數 (快取 + 防斷檔邏輯) ---
@st.cache_data(ttl=60)
def fetch_stock_data_cached(ticker):
    try:
        stock = yf.Ticker(ticker)
        # 1. 抓日線 (長線趨勢)
        df = stock.history(period="2y") # 保持原本的 2y
        
        # 2. 抓分時線 (防呆邏輯：抓 5 天，取最後一天)
        df_intra_raw = stock.history(period="5d", interval="5m", prepost=True)
        
        if not df_intra_raw.empty:
            # 轉換時區到台灣，解決 X 軸時間問題
            try:
                df_intra_raw.index = df_intra_raw.index.tz_convert('Asia/Taipei')
            except:
                pass # 如果已經是該時區則忽略

            # 找出資料中「最後一個日期」(可能是今天，也可能是週五)
            last_date = df_intra_raw.index.date[-1]
            
            # 只保留最後一天的資料 (包含該日的盤前、盤中、盤後)
            df_intra = df_intra_raw[df_intra_raw.index.date == last_date].copy()
        else:
            df_intra = pd.DataFrame()

        info = stock.info
        quote_type = info.get('quoteType', 'EQUITY')
        return df, df_intra, info, quote_type
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), {}, "ERROR"

def fetch_exchange_rate_now():
    try:
        fx = yf.Ticker("USDTWD=X")
        hist = fx.history(period="1d")
        if not hist.empty:
            return hist['Close'].iloc[-1]
        return 32.5
    except:
        return 32.5

# --- 4. Gemini AI 分析函數 ---
def get_gemini_analysis(api_key, ticker, data_summary):
    if not api_key:
        return "⚠️ 請先在側邊欄輸入 Gemini API Key"
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        你是一位華爾街頂級交易員，請根據以下 {ticker} 的技術數據，用繁體中文給出一段專業、犀利且有溫度的短評 (約 200 字)。
        
        【技術數據】
        - 現價: {data_summary['price']}
        - 趨勢狀態: {data_summary['trend']}
        - RSI (14): {data_summary['rsi']:.1f} ({data_summary['rsi_status']})
        - MACD狀態: {data_summary['macd_status']}
        - 成交量狀態: {data_summary['vol_status']}
        
        【回答要求】
        1. 先講結論 (多/空/盤整)。
        2. 分析關鍵風險或機會。
        3. 給出操作建議 (例如「拉回均線佈局」或「嚴設停損」)。
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ AI 分析失敗: {str(e)}"

# --- 5. 局部刷新元件 ---
@st.fragment
def render_calculator_tab(current_close_price, exchange_rate, quote_type):
    # ... (保持原本的計算機邏輯，因篇幅限制直接使用你的原代碼邏輯) ...
    st.markdown("#### 🧮 交易前規劃")
    SEC_FEE_RATE = 0.0000278
    if quote_type == 'ETF':
        BUY_FIXED_FEE, BUY_RATE_FEE = 3.0, 0.0
        SELL_FIXED_FEE, SELL_RATE_FEE = 3.0, SEC_FEE_RATE
        fee_badge_text = "💡 檢測為 **ETF**：套用固定手續費 **$3 USD**"
    else:
        BUY_FIXED_FEE, BUY_RATE_FEE = 0.0, 0.001
        SELL_FIXED_FEE, SELL_RATE_FEE = 0.0, 0.001 + SEC_FEE_RATE
        fee_badge_text = "💡 檢測為 **一般股票**：套用費率 **0.1%**"

    st.markdown(f'<div class="fee-badge">{fee_badge_text}</div>', unsafe_allow_html=True)
    st.info(f"💰 目前匯率參考：**1 USD ≈ {exchange_rate:.2f} TWD**")

    with st.container():
        st.markdown('<div class="calc-header">💰 預算試算 (我有多少錢?)</div>', unsafe_allow_html=True)
        bc1, bc2 = st.columns(2)
        with bc1: budget_twd = st.number_input("台幣預算 (TWD)", value=100000, step=1000, key="budget_input")
        with bc2:
            if "buy_price_input" not in st.session_state: st.session_state.buy_price_input = float(current_close_price)
            buy_price_input = st.number_input("預計買入價 (USD)", key="buy_price_input", step=0.1, format="%.2f")
        usd_budget = budget_twd / exchange_rate
        max_shares = (usd_budget - BUY_FIXED_FEE) / (buy_price_input * (1 + BUY_RATE_FEE)) if usd_budget > BUY_FIXED_FEE else 0
        total_buy_cost_usd = (max_shares * buy_price_input * (1 + BUY_RATE_FEE)) + BUY_FIXED_FEE
        total_buy_cost_twd = total_buy_cost_usd * exchange_rate
        
        if max_shares > 0:
            st.markdown(f"""<div class="calc-result"><div class="calc-res-title">可購買股數</div><div class="calc-res-val" style="color:#0d6efd !important;">{max_shares:.2f} 股</div><div style="font-size:0.8rem; margin-top:5px; color:#666 !important;">總成本: ${total_buy_cost_usd:.2f} USD (約 {total_buy_cost_twd:.0f} TWD)</div></div>""", unsafe_allow_html=True)
        else: st.error("預算不足")
    
    st.markdown("---")
    with st.container():
        st.markdown('<div class="calc-header">⚖️ 賣出試算 (獲利預估)</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1: shares_held = st.number_input("持有股數", value=10.0, step=1.0, key="hold_shares_input")
        with c2:
            if "cost_price_input" not in st.session_state: st.session_state.cost_price_input = float(current_close_price)
            cost_price = st.number_input("買入成本 (USD)", key="cost_price_input", step=0.1, format="%.2f")
        real_buy_cost_usd = (cost_price * shares_held * (1 + BUY_RATE_FEE)) + BUY_FIXED_FEE
        breakeven_price = (real_buy_cost_usd + SELL_FIXED_FEE) / (shares_held * (1 - SELL_RATE_FEE))
        st.caption(f"🛡️ 損益兩平價 (含手續費): **${breakeven_price:.2f}**")
        st.divider()
        calc_mode = st.radio("選擇試算目標：", ["🎯 設定【目標獲利】反推股價", "💵 設定【賣出價格】計算獲利"], horizontal=True, key="calc_mode_radio")

        if calc_mode == "🎯 設定【目標獲利】反推股價":
            target_profit_twd = st.number_input("我想賺多少台幣 (TWD)?", value=3000, step=500, key="target_profit_input")
            target_profit_usd = target_profit_twd / exchange_rate
            target_sell_price = (target_profit_usd + real_buy_cost_usd + SELL_FIXED_FEE) / (shares_held * (1 - SELL_RATE_FEE))
            pct_need = ((target_sell_price / cost_price) - 1) * 100 if cost_price > 0 else 0
            st.markdown(f"""<div class="calc-result"><div class="calc-res-title">建議掛單賣出價</div><div class="calc-res-val txt-up-vip">${target_sell_price:.2f}</div><div style="font-size:0.8rem;" class="txt-up-vip">需上漲 {pct_need:.1f}%</div></div>""", unsafe_allow_html=True)
        else:
            if "target_sell_input" not in st.session_state: st.session_state.target_sell_input = float(cost_price) * 1.05
            target_sell_input = st.number_input("預計賣出價格 (USD)", key="target_sell_input", step=0.1, format="%.2f")
            net_revenue_usd = (target_sell_input * shares_held * (1 - SELL_RATE_FEE)) - SELL_FIXED_FEE
            net_profit_usd = net_revenue_usd - real_buy_cost_usd
            net_profit_twd = net_profit_usd * exchange_rate
            res_class = "txt-up-vip" if net_profit_twd >= 0 else "txt-down-vip"
            st.markdown(f"""<div class="calc-result"><div class="calc-res-title">預估淨獲利 (TWD)</div><div class="calc-res-val {res_class}">{'+' if net_profit_twd>=0 else ''}{net_profit_twd:.0f} 元</div><div style="font-size:0.8rem; color:#666 !important;">美金損益: {'+' if net_profit_usd>=0 else ''}${net_profit_usd:.2f}</div></div>""", unsafe_allow_html=True)

@st.fragment
def render_inventory_tab(current_close_price, quote_type):
    # ... (保持原本的庫存邏輯) ...
    st.markdown("#### 📦 庫存損益與加碼攤平")
    SEC_FEE_RATE = 0.0000278
    if quote_type == 'ETF':
        BUY_FIXED_FEE, BUY_RATE_FEE = 3.0, 0.0
        SELL_FIXED_FEE, SELL_RATE_FEE = 3.0, SEC_FEE_RATE
    else:
        BUY_FIXED_FEE, BUY_RATE_FEE = 0.0, 0.001
        SELL_FIXED_FEE, SELL_RATE_FEE = 0.0, 0.001 + SEC_FEE_RATE

    with st.container():
        ic1, ic2 = st.columns(2)
        with ic1:
            st.caption("📍 目前持倉")
            curr_shares = st.number_input("目前股數", value=100.0, key="inv_curr_shares")
            if "inv_curr_avg" not in st.session_state: st.session_state.inv_curr_avg = float(current_close_price) * 1.1
            curr_avg_price = st.number_input("平均成交價 (USD)", key="inv_curr_avg", step=0.1, format="%.2f")
        with ic2:
            st.caption("➕ 預計加碼")
            new_shares = st.number_input("加碼股數", value=50.0, key="inv_new_shares")
            if "inv_new_price" not in st.session_state: st.session_state.inv_new_price = float(current_close_price)
            new_buy_price = st.number_input("加碼單價 (USD)", key="inv_new_price", step=0.1, format="%.2f")
    st.markdown("---")
    
    total_shares = curr_shares + new_shares
    cost_old = curr_shares * curr_avg_price
    cost_new = new_shares * new_buy_price
    new_avg_price = (cost_old + cost_new) / total_shares if total_shares > 0 else 0
    cost_old_w_fee = (curr_shares * curr_avg_price * (1 + BUY_RATE_FEE)) + (BUY_FIXED_FEE if curr_shares > 0 else 0)
    cost_new_w_fee = (new_shares * new_buy_price * (1 + BUY_RATE_FEE)) + (BUY_FIXED_FEE if new_shares > 0 else 0)
    total_invested_real = cost_old_w_fee + cost_new_w_fee
    market_val_gross = total_shares * new_buy_price
    market_val_net = (market_val_gross * (1 - SELL_RATE_FEE)) - (SELL_FIXED_FEE if total_shares > 0 else 0)
    unrealized_pl = market_val_net - total_invested_real
    pl_class = "txt-up-vip" if unrealized_pl >= 0 else "txt-down-vip"
    avg_change_class = "txt-up-vip" if new_avg_price < curr_avg_price else "txt-gray-vip"

    st.markdown(f"""<div class="metric-card"><div class="metric-title">加碼後平均成交價</div><div style="display:flex; justify-content:space-between; align-items:end;"><div class="metric-value">${new_avg_price:.2f}</div><div class="{avg_change_class}">{f'⬇ 下降 ${curr_avg_price - new_avg_price:.2f}' if new_avg_price < curr_avg_price else '變動不大'}</div></div></div>""", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: st.markdown(f"""<div class="calc-result"><div class="calc-res-title">加碼後總股數</div><div class="calc-res-val">{total_shares:.0f} 股</div></div>""", unsafe_allow_html=True)
    with c2: st.markdown(f"""<div class="calc-result"><div class="calc-res-title">預估總損益 (含費)</div><div class="calc-res-val {pl_class}">${unrealized_pl:.2f}</div></div>""", unsafe_allow_html=True)

# --- 6. 側邊欄與主程式 ---
with st.sidebar:
    st.header("⚙️ 參數設定")
    ticker_input = st.text_input("股票代號", "TSLA", key="sidebar_ticker").upper()
    gemini_key = st.text_input("Gemini API Key (選填)", type="password", placeholder="填入可啟用 AI 分析")
    st.caption("[取得免費 API Key](https://aistudio.google.com/app/apikey)")
    
    if st.button("🔄 更新報價 (Refresh)"):
        st.cache_data.clear() # 清除快取，強制重抓
        st.rerun()

    st.markdown("---")
    st.subheader("🧠 策略邏輯")
    strategy_mode = st.radio("判讀模式", ["🤖 自動判別 (Auto)", "🛠️ 手動設定 (Manual)"], key="sidebar_strat_mode")
    strat_fast, strat_slow = 5, 20
    strat_desc = "預設"
    if strategy_mode == "🛠️ 手動設定 (Manual)":
        strat_fast = st.number_input("策略快線 (Fast)", value=5, key="sidebar_fast")
        strat_slow = st.number_input("策略慢線 (Slow)", value=20, key="sidebar_slow")
        strat_desc = "自訂策略"

if ticker_input:
    # 使用快取函數讀取數據
    df, df_intra, info, quote_type = fetch_stock_data_cached(ticker_input)
    exchange_rate = fetch_exchange_rate_now()

    if not df.empty and len(df) > 50:
        # --- A. 指標計算 ---
        if strategy_mode == "🤖 自動判別 (Auto)":
            mcap = info.get('marketCap', 0)
            strat_fast, strat_slow = (10, 20) if mcap > 200_000_000_000 else (5, 10)
            strat_desc = "🐘 巨頭穩健" if mcap > 200_000_000_000 else "🚀 小型飆股"
        
        ma_list = [5, 10, 20, 30, 60, 120, 200]
        for d in ma_list: df[f'MA_{d}'] = SMAIndicator(df['Close'], window=d).sma_indicator()
        
        strat_fast_val = SMAIndicator(df['Close'], window=strat_fast).sma_indicator().iloc[-1]
        strat_slow_val = SMAIndicator(df['Close'], window=strat_slow).sma_indicator().iloc[-1]
        
        df['RSI'] = RSIIndicator(df['Close'], window=14).rsi()
        macd = MACD(df['Close'])
        df['MACD'] = macd.macd()
        df['Signal'] = macd.macd_signal()
        df['Hist'] = macd.macd_diff() 
        df['Vol_MA'] = SMAIndicator(df['Volume'], window=20).sma_indicator()

        last = df.iloc[-1]
        prev = df.iloc[-2]
        current_close_price = last['Close']

        # --- 建立 Tabs 分頁 ---
        tab_analysis, tab_calc, tab_inv = st.tabs(["📊 技術分析", "🧮 交易計算", "📦 庫存管理"])

        with tab_analysis:
            # --- 處理盤前盤後與價格顯示 ---
            regular_price = info.get('currentPrice', info.get('regularMarketPrice', last['Close']))
            previous_close = info.get('previousClose', prev['Close'])
            
            # 如果 df_intra 有值，就用最後一筆當即時價，否則用 regular_price
            live_price = df_intra['Close'].iloc[-1] if not df_intra.empty else regular_price
            
            is_extended = False
            ext_price, ext_pct, ext_label = 0, 0, ""

            if 'preMarketPrice' in info and info['preMarketPrice']:
                ext_price = info['preMarketPrice']
                is_extended, ext_label = True, "盤前"
            elif 'postMarketPrice' in info and info['postMarketPrice']:
                ext_price = info['postMarketPrice']
                is_extended, ext_label = True, "盤後"
            
            # 如果沒有盤前盤後欄位，但即時價跟收盤價差太多，視為盤後試撮
            if not is_extended and abs(live_price - regular_price) / regular_price > 0.001:
                    ext_price = live_price
                    is_extended, ext_label = True, "盤後/即時"

            reg_change = regular_price - previous_close
            reg_pct = (reg_change / previous_close) * 100
            reg_class = "txt-up-vip" if reg_change > 0 else "txt-down-vip"

            if is_extended:
                ext_change = ext_price - regular_price
                ext_pct = (ext_change / regular_price) * 100
                ext_class = "txt-up-vip" if ext_change > 0 else "txt-down-vip"

            st.markdown(f"### 📱 {info.get('longName', ticker_input)} ({ticker_input})")
            st.caption(f"目前策略：{strat_desc}")

            # --- 頂部 Metric 區塊 (含 Sparkline) ---
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                fig_spark = go.Figure()
                day_high_pct, day_low_pct = 0, 0 # 預設

                if not df_intra.empty:
                    # 計算當日 High/Low
                    day_high = df_intra['High'].max()
                    day_low = df_intra['Low'].min()
                    day_high_pct = ((day_high - previous_close) / previous_close) * 100
                    day_low_pct = ((day_low - previous_close) / previous_close) * 100
                    
                    # 畫即時走勢
                    start_open = df_intra['Open'].iloc[0]
                    curr_close = df_intra['Close'].iloc[-1]
                    spark_color = COLOR_UP if curr_close >= start_open else COLOR_DOWN
                    fill_color = "rgba(5, 154, 129, 0.1)" if curr_close >= start_open else "rgba(242, 54, 69, 0.1)"

                    fig_spark.add_trace(go.Scatter(
                        x=df_intra.index, y=df_intra['Close'], 
                        mode='lines', line=dict(color=spark_color, width=2), 
                        fill='tozeroy', fillcolor=fill_color, hoverinfo='x+y'
                    ))
                    
                    # 設定 X 軸 (台北時間格式化)
                    fig_spark.update_xaxes(
                        tickformat="%H:%M", # 顯示 22:30 格式
                        showgrid=False,
                        mirror=True
                    )
                    y_min, y_max = df_intra['Low'].min()*0.999, df_intra['High'].max()*1.001
                    fig_spark.update_layout(height=80, margin=dict(l=0, r=40, t=5, b=5), yaxis=dict(visible=False, range=[y_min, y_max]), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)

                # 組合 HTML
                price_html = f"""<div class="metric-card"><div class="metric-title">最新股價</div><div class="metric-value {reg_class}">{regular_price:.2f}</div><div class="metric-sub {reg_class}">{('+' if reg_change > 0 else '')}{reg_change:.2f} ({reg_pct:.2f}%)</div>"""
                if is_extended: price_html += f"""<div class="ext-price-box"><span class="ext-label">{ext_label}</span><span class="{ext_class}">{ext_price:.2f} ({('+' if ext_pct > 0 else '')}{ext_pct:.2f}%)</span></div>"""
                
                h_class = "txt-up-vip" if day_high_pct >= 0 else "txt-down-vip"
                l_class = "txt-up-vip" if day_low_pct >= 0 else "txt-down-vip"
                price_html += f"""<div class="spark-scale"><div class="{h_class}">H: {day_high_pct:+.1f}%</div><div style="margin-top:25px;" class="{l_class}">L: {day_low_pct:+.1f}%</div></div></div>"""
                
                st.markdown(price_html, unsafe_allow_html=True)
                if not df_intra.empty:
                    st.plotly_chart(fig_spark, use_container_width=True, config={'displayModeBar': False, 'staticPlot': False}) # staticPlot=False 讓滑鼠可以看時間
                else:
                    st.info("⚠️ 暫無即時走勢 (可能為休市)")

            with c2: st.markdown(f"""<div class="metric-card"><div class="metric-title">本益比 (P/E)</div><div class="metric-value">{info.get('trailingPE', 'N/A')}</div><div class="metric-sub">估值參考</div></div>""", unsafe_allow_html=True)
            with c3: st.markdown(f"""<div class="metric-card"><div class="metric-title">EPS</div><div class="metric-value">{info.get('trailingEps', 'N/A')}</div><div class="metric-sub">獲利能力</div></div>""", unsafe_allow_html=True)
            with c4: 
                m_val = info.get('marketCap', 0)
                st.markdown(f"""<div class="metric-card"><div class="metric-title">市值</div><div class="metric-value">{f"{m_val/10**9:.1f}B" if m_val>10**9 else f"{m_val/10**6:.1f}M"}</div><div class="metric-sub">{info.get('sector','N/A')}</div></div>""", unsafe_allow_html=True)

            # --- 訊號燈 ---
            st.markdown("#### 🤖 策略訊號解讀")
            k1, k2, k3, k4 = st.columns(4)
            
            trend_status, trend_msg, trend_bg = "盤整", "💤 睡覺行情", "bg-gray"
            if last['Close'] > strat_fast_val > strat_slow_val: trend_status, trend_msg, trend_bg = "多頭", "🚀 火力全開", "bg-up"
            elif last['Close'] < strat_fast_val < strat_slow_val: trend_status, trend_msg, trend_bg = "空頭", "🐻 熊出沒", "bg-down"
            
            vol_r = last['Volume'] / df['Vol_MA'].iloc[-1] if df['Vol_MA'].iloc[-1] > 0 else 0
            v_msg, v_bg = ("🔥 爆量", "bg-down") if vol_r > 2.0 else ("💧 溫和", "bg-blue") if vol_r > 1.0 else ("❄️ 量縮", "bg-gray")
            
            macd_status, m_bg = ("🐂 多方", "bg-up") if last['Hist'] > 0 else ("📉 空方", "bg-down")
            
            r_val = last['RSI']
            r_msg, r_bg = ("🔥 過熱", "bg-down") if r_val > 70 else ("🧊 超賣", "bg-up") if r_val < 30 else ("⚖️ 中性", "bg-gray")

            with k1: st.markdown(f"""<div class="metric-card"><div class="metric-title">趨勢訊號</div><div class="metric-value" style="font-size:1.3rem;">{trend_msg}</div><div><span class="status-badge {trend_bg}">{trend_status}</span></div></div>""", unsafe_allow_html=True)
            with k2: st.markdown(f"""<div class="metric-card"><div class="metric-title">量能判讀</div><div class="metric-value" style="font-size:1.3rem;">{v_msg}</div><div><span class="status-badge {v_bg}">{vol_r:.1f} 倍</span></div></div>""", unsafe_allow_html=True)
            with k3: st.markdown(f"""<div class="metric-card"><div class="metric-title">MACD 趨勢</div><div class="metric-value" style="font-size:1.3rem;">{macd_status}</div><div><span class="status-badge {m_bg}">{last['MACD']:.2f}</span></div></div>""", unsafe_allow_html=True)
            with k4: st.markdown(f"""<div class="metric-card"><div class="metric-title">RSI 強弱</div><div class="metric-value" style="font-size:1.3rem;">{r_msg}</div><div><span class="status-badge {r_bg}">{r_val:.1f}</span></div></div>""", unsafe_allow_html=True)

            # --- 均線 & 圖表 ---
            st.markdown("#### 📉 技術分析")
            ma_html_inner = ""
            for d in ma_list:
                val, prev_val = last[f'MA_{d}'], prev[f'MA_{d}']
                cls = "txt-up-vip" if val > prev_val else "txt-down-vip"
                ma_html_inner += f'<div class="ma-box"><div class="ma-label">MA {d}</div><div class="ma-val {cls}">{val:.2f}</div></div>'
            st.markdown(f'<div class="ma-container">{ma_html_inner}</div>', unsafe_allow_html=True)

            chart_months = st.slider("選擇歷史長度 (月)", 1, 12, 6)
            df_chart = df[df.index >= df.index[-1] - pd.DateOffset(months=chart_months)].copy()
            
            # K線圖
            fig_price = go.Figure()
            fig_price.add_trace(go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], increasing_line_color=COLOR_UP, decreasing_line_color=COLOR_DOWN, name='K線'))
            for m in [5, 20, 60]: fig_price.add_trace(go.Scatter(x=df_chart.index, y=df_chart[f'MA_{m}'], line=dict(width=1), name=f'MA{m}'))
            fig_price.update_layout(height=350, margin=dict(l=10, r=10, t=10, b=10), template="plotly_white", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig_price, use_container_width=True)

            # MACD 圖 (確保顏色正確)
            fig_macd = go.Figure()
            colors = [MACD_BULL_GROW if (h>=0 and h>ph) else MACD_BULL_SHRINK if (h>=0 and h<=ph) else MACD_BEAR_GROW if (h<0 and h<ph) else MACD_BEAR_SHRINK for h, ph in zip(df_chart['Hist'], df['Hist'].shift(1).loc[df_chart.index])]
            fig_macd.add_trace(go.Bar(x=df_chart.index, y=df_chart['Hist'], marker_color=colors, name='Hist'))
            fig_macd.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MACD'], line=dict(color='#2196F3'), name='MACD'))
            fig_macd.add_trace(go.Scatter(x=df_chart.index, y=df_chart['Signal'], line=dict(color='#FF5722'), name='Signal'))
            fig_macd.update_layout(height=200, margin=dict(l=10, r=10, t=10, b=10), template="plotly_white")
            st.plotly_chart(fig_macd, use_container_width=True)

            # --- AI 分析區塊 ---
            st.markdown("#### 🧠 AI 觀點")
            
            # 1. 顯示原本的規則式摘要 (預設)
            ai_suggestion = f"目前 {ticker_input} 處於{trend_status}，RSI {r_msg}，成交量 {v_msg}。"
            if trend_status == "多頭": ai_suggestion += " 均線向上發散，建議沿五日線操作。"
            elif trend_status == "空頭": ai_suggestion += " 均線蓋頭反壓，建議保守觀望或反彈調節。"
            
            st.markdown(f"""<div class="ai-summary-card"><div class="ai-title">🤖 系統自動判讀</div><div class="ai-content">{ai_suggestion}</div></div>""", unsafe_allow_html=True)
            
            # 2. 顯示 Gemini 按鈕
            if st.button("✨ 呼叫 Gemini 深度分析 (需填 API Key)"):
                if not gemini_key:
                    st.error("請先在左側側邊欄填入 Gemini API Key")
                else:
                    with st.spinner("AI 正在思考市場邏輯..."):
                        data_summary = {
                            "price": f"{current_close_price:.2f}",
                            "trend": trend_status,
                            "rsi": last['RSI'],
                            "rsi_status": r_msg,
                            "macd_status": macd_status,
                            "vol_status": v_msg
                        }
                        gemini_res = get_gemini_analysis(gemini_key, ticker_input, data_summary)
                        st.markdown(f"""<div class="ai-summary-card" style="border-left-color: #9C27B0;"><div class="ai-title" style="color: #6a1b9a !important;">🧠 Gemini 深度解析</div><div class="ai-content">{gemini_res}</div></div>""", unsafe_allow_html=True)

        # 載入計算機與庫存分頁
        with tab_calc: render_calculator_tab(current_close_price, exchange_rate, quote_type)
        with tab_inv: render_inventory_tab(current_close_price, quote_type)

    else:
        st.error("查無資料，請檢查代號是否正確。")