import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from ta.trend import SMAIndicator, MACD
from ta.momentum import RSIIndicator
import pytz
from datetime import datetime, time, timedelta

# --- 0. 輔助函數: 取得美股關鍵時間 (自動切換冬夏令) ---
def get_us_tw_timeline():
    try:
        tz_ny = pytz.timezone('America/New_York')
        tz_tw = pytz.timezone('Asia/Taipei')
        now_ny = datetime.now(tz_ny)
        
        # 設定當日關鍵時間點 (紐約時間)
        t_pre = now_ny.replace(hour=4, minute=0, second=0, microsecond=0)   # 盤前
        t_open = now_ny.replace(hour=9, minute=30, second=0, microsecond=0)  # 開盤
        t_close = now_ny.replace(hour=16, minute=0, second=0, microsecond=0) # 收盤
        t_post = now_ny.replace(hour=20, minute=0, second=0, microsecond=0)  # 結算
        
        # 轉換為台灣時間字串
        fmt = "%H:%M"
        str_pre = t_pre.astimezone(tz_tw).strftime(fmt)
        str_open = t_open.astimezone(tz_tw).strftime(fmt)
        str_close = t_close.astimezone(tz_tw).strftime(fmt)
        str_post = t_post.astimezone(tz_tw).strftime(fmt)
        
        # 判斷目前是否為夏令 (DST)
        season = "夏令" if t_pre.dst() != timedelta(0) else "冬令"
        
        return f'''
        <div style="display: flex; justify-content: space-between; font-size: 0.65rem; color: #999; margin-top: 8px; border-top: 1px dashed #eee; padding-top: 4px;">
            <div style="text-align: center;"><span>盤前 ({season})</span><br><b style="color:#555">{str_pre}</b></div>
            <div style="text-align: center;"><span>🔔 開盤</span><br><b style="color:#000">{str_open}</b></div>
            <div style="text-align: center;"><span>🌙 收盤</span><br><b style="color:#000">{str_close}</b></div>
            <div style="text-align: center;"><span>🏁 結算</span><br><b style="color:#555">{str_post}</b></div>
        </div>
        '''
    except:
        return ""

# --- 1. 網頁設定 ---
st.set_page_config(page_title="AI 智能操盤戰情室 (VIP 終極版)", layout="wide", initial_sidebar_state="collapsed")

# --- 定義全域配色常數 (VIP 客製化) ---
COLOR_UP = "#059a81"      # 上漲 (松石綠)
COLOR_DOWN = "#f23645"    # 下跌 (法拉利紅)
COLOR_NEUTRAL = "#adb5bd" # 中性灰

# MACD 配色
MACD_BULL_GROW = "#2db09c"   # 深綠
MACD_BULL_SHRINK = "#a8e0d1" # 淺綠
MACD_BEAR_GROW = "#ff6666"   # 深紅
MACD_BEAR_SHRINK = "#ffcccc" # 淺紅

# 成交量配色 (暖色系分級)
VOL_EXPLODE = "#C70039" # 爆量 (深紅)
VOL_NORMAL = "#FF5733"  # 正常 (鮮橘)
VOL_SHRINK = "#FFC300"  # 量縮 (金黃)
VOL_MA_LINE = "#000000" # 均量線 (純黑)

# VWAP 配色
COLOR_VWAP = "#FF9800"  # 琥珀橘

# --- 2. CSS 美化 (權重修正版) ---
st.markdown(f"""
    <style>
    /* [強制亮色模式] */
    :root {{
        --primary-color: #ff4b4b;
        --background-color: #f8f9fa;
        --secondary-background-color: #ffffff;
        --text-color: #000000;
        --font: sans-serif;
    }}
    
    .stApp {{ background-color: #f8f9fa; }}
    
    /* 強制所有文字深色 (解決 iPhone Dark Mode) */
    /* 注意：這裡不針對 span 做全域強制，以免蓋掉我們自定義的顏色 span */
    h1, h2, h3, h4, h5, h6, p, div, label, li {{
        color: #000000 !important;
    }}
    
    /* 輸入框文字修正 */
    .stTextInput > label, .stNumberInput > label, .stRadio > label {{
        color: #000000 !important;
    }}
    
    /* --- [VIP 顏色專用類別] 權重最高 --- */
    .txt-up-vip {{ color: {COLOR_UP} !important; font-weight: bold; }}
    .txt-down-vip {{ color: {COLOR_DOWN} !important; font-weight: bold; }}
    .txt-gray-vip {{ color: {COLOR_NEUTRAL} !important; }}
    
    .chart-title {{
        font-size: 1.1rem;
        font-weight: 700;
        color: #000000 !important;
        margin-top: 10px;
        margin-bottom: 0px; 
        padding-left: 5px;
    }}

    .metric-card {{
        background-color: #ffffff;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 10px;
        border: 1px solid #f0f0f0;
        position: relative;
    }}
    /* metric-title 和 sub 保持原色設定 */
    .metric-title {{ color: #6c757d !important; font-size: 0.9rem; font-weight: 700; margin-bottom: 5px; }}
    .metric-value {{ font-size: 1.8rem; font-weight: 800; color: #212529 !important; }}
    .metric-sub {{ font-size: 0.9rem; margin-top: 5px; }} 
    
    .ext-price-box {{
        background-color: #f1f3f5;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 0.85rem;
        font-weight: 600;
        color: #666 !important;
        margin-top: 8px;
        display: inline-block;
    }}
    .ext-label {{ font-size: 0.75rem; color: #999 !important; margin-right: 5px; }}

    .spark-scale {{
        position: absolute;
        right: 15px;
        top: 55%;
        transform: translateY(-50%);
        text-align: right;
        font-size: 0.7rem;
        line-height: 1.4;
        font-weight: 600;
        /* 移除這裡的 color 強制，交給內部的 span 控制 */
    }}

    .ai-summary-card {{
        background-color: #e3f2fd;
        padding: 20px;
        border-radius: 15px;
        border-left: 5px solid #2196f3;
        margin-top: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }}
    .ai-title {{ font-weight: bold; font-size: 1.2rem; color: #0d47a1 !important; margin-bottom: 10px; display: flex; align-items: center; }}
    .ai-content {{ font-size: 1rem; color: #333 !important; line-height: 1.6; }}

    .ma-container {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        background-color: #ffffff;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border: 1px solid #f0f0f0;
        margin-bottom: 20px;
    }}
    .ma-box {{
        flex: 1 1 100px;
        text-align: center;
        padding: 10px;
        background-color: #f8f9fa;
        border-radius: 10px;
        border: 1px solid #dee2e6;
    }}
    .ma-label {{ font-size: 0.8rem; font-weight: bold; color: #666 !important; margin-bottom: 5px; }}
    .ma-val {{ font-size: 1.1rem; font-weight: 800; }}
    
    .status-badge {{ 
        padding: 4px 8px; 
        border-radius: 6px; 
        font-size: 0.85rem; 
        font-weight: bold; 
        color: white !important; 
        display: inline-block; 
        margin-top: 8px;
    }}
    
    .bg-up {{ background-color: {COLOR_UP}; }}
    .bg-down {{ background-color: {COLOR_DOWN}; }}
    .bg-gray {{ background-color: {COLOR_NEUTRAL}; }}
    .bg-blue {{ background-color: #0d6efd; }}

    .js-plotly-plot .plotly .modebar {{ display: none !important; }}

    .calc-box {{
        background-color: #ffffff;
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #eee;
        margin-bottom: 15px;
    }}
    .calc-header {{
        font-size: 1rem;
        font-weight: bold;
        color: #444 !important;
        margin-bottom: 10px;
        border-left: 4px solid {COLOR_UP};
        padding-left: 8px;
    }}
    .calc-result {{
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 8px;
        text-align: center;
        margin-top: 10px;
    }}
    .calc-res-title {{ font-size: 0.8rem; color: #888 !important; }}
    /* 移除這裡的 color: #333 !important，改用 class 控制 */
    .calc-res-val {{ font-size: 1.4rem; font-weight: bold; }}
    
    .fee-badge {{
        background-color: #fff3cd;
        color: #856404 !important;
        padding: 5px 10px;
        border-radius: 5px;
        font-size: 0.8rem;
        border: 1px solid #ffeeba;
        margin-bottom: 15px;
        display: flex;
        align-items: center;
        gap: 5px;
    }}
    
    div[role="radiogroup"] {{
        background-color: transparent;
        border: none;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. 數據抓取函數 ---
def fetch_stock_data_now(ticker):
    stock = yf.Ticker(ticker)
    df = stock.history(period="2y")
    df_intra = stock.history(period="1d", interval="5m", prepost=True)
    info = stock.info
    quote_type = info.get('quoteType', 'EQUITY')
    return df, df_intra, info, quote_type

def fetch_exchange_rate_now():
    try:
        fx = yf.Ticker("USDTWD=X")
        hist = fx.history(period="1d")
        if not hist.empty:
            return hist['Close'].iloc[-1]
        return 32.5
    except:
        return 32.5

# --- 4. 定義局部刷新元件 (@st.fragment) ---
@st.fragment
def render_calculator_tab(current_close_price, exchange_rate, quote_type):
    st.markdown("#### 🧮 交易前規劃")
    
    SEC_FEE_RATE = 0.0000278
    
    if quote_type == 'ETF':
        BUY_FIXED_FEE = 3.0
        BUY_RATE_FEE = 0.0
        SELL_FIXED_FEE = 3.0
        SELL_RATE_FEE = SEC_FEE_RATE
        fee_badge_text = "💡 檢測為 **ETF**：套用固定手續費 **$3 USD**"
    else:
        BUY_FIXED_FEE = 0.0
        BUY_RATE_FEE = 0.001
        SELL_FIXED_FEE = 0.0
        SELL_RATE_FEE = 0.001 + SEC_FEE_RATE
        fee_badge_text = "💡 檢測為 **一般股票**：套用費率 **0.1%**"

    st.markdown(f'<div class="fee-badge">{fee_badge_text}</div>', unsafe_allow_html=True)
    st.info(f"💰 目前匯率參考：**1 USD ≈ {exchange_rate:.2f} TWD**")

    # --- 1. 購買力試算 ---
    with st.container():
        st.markdown('<div class="calc-header">💰 預算試算 (我有多少錢?)</div>', unsafe_allow_html=True)
        
        bc1, bc2 = st.columns(2)
        with bc1:
            budget_twd = st.number_input("台幣預算 (TWD)", value=100000, step=1000, key="budget_input")
        with bc2:
            if "buy_price_input" not in st.session_state:
                st.session_state.buy_price_input = float(current_close_price)
            
            buy_price_input = st.number_input("預計買入價 (USD)", key="buy_price_input", step=0.1, format="%.2f")

        usd_budget = budget_twd / exchange_rate
        
        if usd_budget > BUY_FIXED_FEE:
            max_shares = (usd_budget - BUY_FIXED_FEE) / (buy_price_input * (1 + BUY_RATE_FEE))
        else:
            max_shares = 0
            
        total_buy_cost_usd = (max_shares * buy_price_input * (1 + BUY_RATE_FEE)) + BUY_FIXED_FEE
        total_buy_cost_twd = total_buy_cost_usd * exchange_rate
        
        if max_shares > 0:
            st.markdown(f"""
            <div class="calc-result">
                <div class="calc-res-title">可購買股數</div>
                <div class="calc-res-val" style="color:#0d6efd !important;">{max_shares:.2f} 股</div>
                <div style="font-size:0.8rem; margin-top:5px; color:#666 !important;">
                總成本: ${total_buy_cost_usd:.2f} USD (約 {total_buy_cost_twd:.0f} TWD)
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.error("預算不足以支付手續費")
    
    st.markdown("---")

    # --- 2. 賣出試算 (雙向邏輯) ---
    with st.container():
        st.markdown('<div class="calc-header">⚖️ 賣出試算 (獲利預估)</div>', unsafe_allow_html=True)
        
        c_input1, c_input2 = st.columns(2)
        with c_input1:
            shares_held = st.number_input("持有股數", value=10.0, step=1.0, key="hold_shares_input")
        with c_input2:
            if "cost_price_input" not in st.session_state:
                st.session_state.cost_price_input = float(current_close_price)
            
            cost_price = st.number_input("買入成本 (USD)", key="cost_price_input", step=0.1, format="%.2f")

        real_buy_cost_usd = (cost_price * shares_held * (1 + BUY_RATE_FEE)) + BUY_FIXED_FEE
        
        breakeven_price = (real_buy_cost_usd + SELL_FIXED_FEE) / (shares_held * (1 - SELL_RATE_FEE))
        
        st.caption(f"🛡️ 損益兩平價 (含手續費): **${breakeven_price:.2f}**")

        st.divider()

        calc_mode = st.radio("選擇試算目標：", 
                            ["🎯 設定【目標獲利】反推股價", "💵 設定【賣出價格】計算獲利"], 
                            horizontal=True,
                            key="calc_mode_radio")

        if calc_mode == "🎯 設定【目標獲利】反推股價":
            target_profit_twd = st.number_input("我想賺多少台幣 (TWD)?", value=3000, step=500, key="target_profit_input")
            target_profit_usd = target_profit_twd / exchange_rate
            
            target_sell_price = (target_profit_usd + real_buy_cost_usd + SELL_FIXED_FEE) / (shares_held * (1 - SELL_RATE_FEE))
            
            pct_need = ((target_sell_price / cost_price) - 1) * 100 if cost_price > 0 else 0
            
            st.markdown(f"""
            <div class="calc-result">
                <div class="calc-res-title">建議掛單賣出價</div>
                <div class="calc-res-val txt-up-vip">${target_sell_price:.2f}</div>
                <div style="font-size:0.8rem;" class="txt-up-vip">需上漲 {pct_need:.1f}%</div>
            </div>
            """, unsafe_allow_html=True)

        else:
            if "target_sell_input" not in st.session_state:
                st.session_state.target_sell_input = float(cost_price) * 1.05

            target_sell_input = st.number_input("預計賣出價格 (USD)", key="target_sell_input", step=0.1, format="%.2f")
            
            net_revenue_usd = (target_sell_input * shares_held * (1 - SELL_RATE_FEE)) - SELL_FIXED_FEE
            
            net_profit_usd = net_revenue_usd - real_buy_cost_usd
            net_profit_twd = net_profit_usd * exchange_rate
            
            # 使用 VIP class
            res_class = "txt-up-vip" if net_profit_twd >= 0 else "txt-down-vip"
            res_prefix = "+" if net_profit_twd >= 0 else ""

            st.markdown(f"""
            <div class="calc-result">
                <div class="calc-res-title">預估淨獲利 (TWD)</div>
                <div class="calc-res-val {res_class}">{res_prefix}{net_profit_twd:.0f} 元</div>
                <div style="font-size:0.8rem; color:#666 !important;">
                美金損益: {res_prefix}${net_profit_usd:.2f}
                </div>
            </div>
            """, unsafe_allow_html=True)

@st.fragment
def render_inventory_tab(current_close_price, quote_type):
    st.markdown("#### 📦 庫存損益與加碼攤平")
    
    SEC_FEE_RATE = 0.0000278
    if quote_type == 'ETF':
        BUY_FIXED_FEE = 3.0
        BUY_RATE_FEE = 0.0
        SELL_FIXED_FEE = 3.0
        SELL_RATE_FEE = SEC_FEE_RATE
        fee_badge_text = "💡 檢測為 **ETF**：套用固定手續費 **$3 USD**"
    else:
        BUY_FIXED_FEE = 0.0
        BUY_RATE_FEE = 0.001
        SELL_FIXED_FEE = 0.0
        SELL_RATE_FEE = 0.001 + SEC_FEE_RATE
        fee_badge_text = "💡 檢測為 **一般股票**：套用費率 **0.1%**"

    st.caption(f"{fee_badge_text}")

    with st.container():
        ic1, ic2 = st.columns(2)
        with ic1:
            st.caption("📍 目前持倉")
            curr_shares = st.number_input("目前股數", value=100.0, key="inv_curr_shares")
            
            if "inv_curr_avg" not in st.session_state:
                st.session_state.inv_curr_avg = float(current_close_price) * 1.1
            curr_avg_price = st.number_input("平均成交價 (USD)", key="inv_curr_avg", step=0.1, format="%.2f")

        with ic2:
            st.caption("➕ 預計加碼")
            new_shares = st.number_input("加碼股數", value=50.0, key="inv_new_shares")
            
            if "inv_new_price" not in st.session_state:
                st.session_state.inv_new_price = float(current_close_price)
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
    
    # 使用 VIP Class
    pl_class = "txt-up-vip" if unrealized_pl >= 0 else "txt-down-vip"
    # 平均成本變化顏色
    avg_change_class = "txt-up-vip" if new_avg_price < curr_avg_price else "txt-gray-vip"

    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">加碼後平均成交價</div>
        <div style="display:flex; justify-content:space-between; align-items:end;">
            <div class="metric-value">${new_avg_price:.2f}</div>
            <div class="{avg_change_class}">
                {f'⬇ 下降 ${curr_avg_price - new_avg_price:.2f}' if new_avg_price < curr_avg_price else '變動不大'}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c_res1, c_res2 = st.columns(2)
    with c_res1:
        st.markdown(f"""
        <div class="calc-result">
            <div class="calc-res-title">加碼後總股數</div>
            <div class="calc-res-val">{total_shares:.0f} 股</div>
        </div>
        """, unsafe_allow_html=True)
    with c_res2:
        st.markdown(f"""
        <div class="calc-result">
            <div class="calc-res-title">預估總損益 (含費)</div>
            <div class="calc-res-val {pl_class}">${unrealized_pl:.2f}</div>
        </div>
        """, unsafe_allow_html=True)


# --- 5. 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 參數設定")
    ticker_input = st.text_input("股票代號", "TSLA", key="sidebar_ticker").upper()
    
    if st.button("🔄 更新報價 (Refresh)"):
        if 'stored_ticker' in st.session_state:
            del st.session_state['stored_ticker']
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

# --- 6. 主程式 ---
if ticker_input:
    try:
        if 'stored_ticker' not in st.session_state or st.session_state.stored_ticker != ticker_input:
            
            with st.spinner(f"正在抓取 {ticker_input} 數據..."):
                df, df_intra, info, quote_type = fetch_stock_data_now(ticker_input)
                exchange_rate = fetch_exchange_rate_now()
                
                st.session_state.stored_ticker = ticker_input
                st.session_state.data_df = df
                st.session_state.data_df_intra = df_intra
                st.session_state.data_info = info
                st.session_state.data_quote_type = quote_type
                st.session_state.data_exchange_rate = exchange_rate
                
                keys_to_clear = ["buy_price_input", "cost_price_input", "target_sell_input", "inv_curr_avg", "inv_new_price"]
                for k in keys_to_clear:
                    if k in st.session_state:
                        del st.session_state[k]

        df = st.session_state.data_df
        df_intra = st.session_state.data_df_intra
        info = st.session_state.data_info
        quote_type = st.session_state.data_quote_type
        exchange_rate = st.session_state.data_exchange_rate

        if not df.empty and len(df) > 200:
            
            # --- A. 指標計算 ---
            if strategy_mode == "🤖 自動判別 (Auto)":
                mcap = info.get('marketCap', 0)
                if mcap > 200_000_000_000:
                    strat_fast, strat_slow = 10, 20
                    strat_desc = "🐘 巨頭穩健"
                else:
                    strat_fast, strat_slow = 5, 10
                    strat_desc = "🚀 小型飆股"
            
            ma_list = [5, 10, 20, 30, 60, 120, 200]
            for d in ma_list:
                df[f'MA_{d}'] = SMAIndicator(df['Close'], window=d).sma_indicator()
            
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

            # ==========================================
            # 分頁 1: 技術分析
            # ==========================================
            with tab_analysis:
                if not df_intra.empty:
                    df_intra['Cum_Vol'] = df_intra['Volume'].cumsum()
                    df_intra['Cum_Vol_Price'] = (df_intra['Close'] * df_intra['Volume']).cumsum()
                    df_intra['VWAP'] = df_intra['Cum_Vol_Price'] / df_intra['Cum_Vol']

                live_price = df_intra['Close'].iloc[-1] if not df_intra.empty else 0
                regular_price = info.get('currentPrice', info.get('regularMarketPrice', last['Close']))
                previous_close = info.get('previousClose', prev['Close'])
                
                is_extended = False
                ext_price = 0
                ext_pct = 0
                ext_label = ""
                
                if 'preMarketPrice' in info and info['preMarketPrice'] is not None:
                    ext_price = info['preMarketPrice']
                    is_extended = True
                    ext_label = "盤前"
                elif 'postMarketPrice' in info and info['postMarketPrice'] is not None:
                    ext_price = info['postMarketPrice']
                    is_extended = True
                    ext_label = "盤後"
                
                if not is_extended and abs(live_price - regular_price) / regular_price > 0.001:
                     ext_price = live_price
                     is_extended = True
                     ext_label = "盤後/試撮"

                reg_change = regular_price - previous_close
                reg_pct = (reg_change / previous_close) * 100
                # 美股：綠漲紅跌 (使用自定義色)
                
                # 使用 VIP class 字串來代入 HTML
                reg_class = "txt-up-vip" if reg_change > 0 else "txt-down-vip"

                if is_extended:
                    ext_change = ext_price - regular_price
                    ext_pct = (ext_change / regular_price) * 100
                    ext_class = "txt-up-vip" if ext_change > 0 else "txt-down-vip"

                st.markdown(f"### 📱 {info.get('longName', ticker_input)} ({ticker_input})")
                st.caption(f"目前策略：{strat_desc}")

                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    fig_spark = go.Figure()
                    
                    if not df_intra.empty:
                        df_intra.index = pd.to_datetime(df_intra.index)
                        if ".TW" in ticker_input:
                            tz = 'Asia/Taipei'
                            open_time = time(9, 0)
                            close_time = time(13, 30)
                        else:
                            tz = 'America/New_York'
                            open_time = time(9, 30)
                            close_time = time(16, 0)
                        try:
                            df_intra_tz = df_intra.tz_convert(tz)
                        except:
                            df_intra_tz = df_intra

                        # [Modify] Calculate H/L based on Regular Trading Hours only (if available)
                        mask_reg_hl = (df_intra_tz.index.time >= open_time) & (df_intra_tz.index.time <= close_time)
                        df_reg_hl = df_intra_tz[mask_reg_hl]
                        
                        if not df_reg_hl.empty:
                            day_high = df_reg_hl['High'].max()
                            day_low = df_reg_hl['Low'].min()
                        else:
                            # If regular session hasn't started, use full data (Pre-market)
                            day_high = df_intra_tz['High'].max()
                            day_low = df_intra_tz['Low'].min()

                        day_high_pct = ((day_high - previous_close) / previous_close) * 100
                        day_low_pct = ((day_low - previous_close) / previous_close) * 100

                        fig_spark.add_trace(go.Scatter(x=df_intra.index, y=df_intra['Close'], mode='lines', line=dict(color='#bdc3c7', width=1.5, dash='dot'), hoverinfo='skip'))
                        
                        mask = (df_intra_tz.index.time >= open_time) & (df_intra_tz.index.time <= close_time)
                        df_regular = df_intra[mask]
                        if not df_regular.empty:
                            day_open_reg = df_regular['Open'].iloc[0]
                            day_close_reg = df_regular['Close'].iloc[-1]
                            spark_color = COLOR_UP if day_close_reg >= day_open_reg else COLOR_DOWN
                            fill_color = "rgba(5, 154, 129, 0.15)" if day_close_reg >= day_open_reg else "rgba(242, 54, 69, 0.15)"
                            
                            fig_spark.add_trace(go.Scatter(x=df_regular.index, y=df_regular['Close'], mode='lines', line=dict(color=spark_color, width=2), fill='tozeroy', fillcolor=fill_color))
                            
                            if 'VWAP' in df_regular.columns:
                                fig_spark.add_trace(go.Scatter(x=df_regular.index, y=df_regular['VWAP'], mode='lines', line=dict(color=COLOR_VWAP, width=1), hoverinfo='skip'))

                        y_min = day_low * 0.999
                        y_max = day_high * 1.001
                        fig_spark.update_layout(height=80, margin=dict(l=0, r=40, t=5, b=5), xaxis=dict(visible=False), yaxis=dict(visible=False, range=[y_min, y_max]), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False, dragmode=False)
                        
                        # [修正] 使用 VIP Class
                        price_html = f"""<div class="metric-card"><div class="metric-title">最新股價</div><div class="metric-value {reg_class}">{regular_price:.2f}</div><div class="metric-sub {reg_class}">{('+' if reg_change > 0 else '')}{reg_change:.2f} ({reg_pct:.2f}%)</div>"""
                        
                        if is_extended:
                            price_html += f"""<div class="ext-price-box"><span class="ext-label">{ext_label}</span><span class="{ext_class}">{ext_price:.2f} ({('+' if ext_pct > 0 else '')}{ext_pct:.2f}%)</span></div>"""
                        
                        # [修正] H/L 使用 VIP Class
                        h_class = "txt-up-vip" if day_high_pct >= 0 else "txt-down-vip"
                        l_class = "txt-up-vip" if day_low_pct >= 0 else "txt-down-vip"
                        
                        price_html += f"""<div class="spark-scale"><div class="{h_class}">H: {day_high_pct:+.1f}%</div><div style="margin-top:25px;" class="{l_class}">L: {day_low_pct:+.1f}%</div></div></div>"""
                        st.markdown(price_html, unsafe_allow_html=True)
                        st.plotly_chart(fig_spark, use_container_width=True, config={'displayModeBar': False, 'staticPlot': True})
                        if ".TW" not in ticker_input:
                            st.markdown(get_us_tw_timeline(), unsafe_allow_html=True)
                    else:
                        st.info("暫無即時數據")

                with c2:
                    pe = info.get('trailingPE', 'N/A')
                    st.markdown(f"""<div class="metric-card"><div class="metric-title">本益比 (P/E)</div><div class="metric-value">{pe if isinstance(pe, str) else f"{pe:.1f}"}</div><div class="metric-sub">估值參考</div></div>""", unsafe_allow_html=True)
                with c3:
                    eps = info.get('trailingEps', 'N/A')
                    st.markdown(f"""<div class="metric-card"><div class="metric-title">EPS</div><div class="metric-value">{eps}</div><div class="metric-sub">獲利能力</div></div>""", unsafe_allow_html=True)
                with c4:
                    mcap = info.get('marketCap', 0)
                    m_str = f"{mcap/1000000000:.1f}B" if mcap > 1000000000 else f"{mcap/1000000:.1f}M"
                    st.markdown(f"""<div class="metric-card"><div class="metric-title">市值</div><div class="metric-value">{m_str}</div><div class="metric-sub">{info.get('sector','N/A')}</div></div>""", unsafe_allow_html=True)

                st.markdown("#### 🤖 策略訊號解讀")
                k1, k2, k3, k4 = st.columns(4)
                
                trend_status = "盤整"
                rsi_status = "中性"
                vol_status = "一般"
                macd_status = "不明"

                trend_msg = "💤 睡覺行情 (盤整)"
                trend_bg = "bg-gray"
                trend_desc = "多空不明，建議觀望"
                if last['Close'] > strat_fast_val > strat_slow_val:
                    trend_msg = "🚀 火力全開！(多頭)"
                    trend_bg = "bg-up" 
                    trend_desc = "均線向上，順勢操作"
                    trend_status = "多頭"
                elif last['Close'] < strat_fast_val < strat_slow_val:
                    trend_msg = "🐻 熊出沒注意 (空頭)"
                    trend_bg = "bg-down"
                    trend_desc = "均線蓋頭，保守為宜"
                    trend_status = "空頭"
                
                with k1:
                    st.markdown(f"""<div class="metric-card"><div class="metric-title">趨勢訊號</div><div class="metric-value" style="font-size:1.3rem;">{trend_msg}</div><div><span class="status-badge {trend_bg}">MA{strat_fast} vs MA{strat_slow}</span></div><div class="metric-sub">{trend_desc}</div></div>""", unsafe_allow_html=True)
                
                vol_r = last['Volume'] / df['Vol_MA'].iloc[-1] if df['Vol_MA'].iloc[-1] > 0 else 0
                v_msg = "❄️ 冷冷清清"
                v_bg = "bg-gray"
                if vol_r > 2.0: 
                    v_msg = "🔥 資金派對 (爆量)"
                    v_bg = "bg-down" 
                    vol_status = "爆量"
                elif vol_r > 1.0:
                    v_msg = "💧 人氣回溫" 
                    v_bg = "bg-blue"
                    vol_status = "溫和"
                with k2:
                    st.markdown(f"""<div class="metric-card"><div class="metric-title">量能判讀</div><div class="metric-value" style="font-size:1.3rem;">{v_msg}</div><div><span class="status-badge {v_bg}">{vol_r:.1f} 倍均量</span></div><div class="metric-sub">成交量活躍度分析</div></div>""", unsafe_allow_html=True)

                m_msg = "🐂 牛軍集結" if last['Hist'] > 0 else "📉 空軍壓境"
                m_bg = "bg-up" if last['Hist'] > 0 else "bg-down"
                macd_status = "多方" if last['Hist'] > 0 else "空方"
                with k3:
                    st.markdown(f"""<div class="metric-card"><div class="metric-title">MACD 趨勢</div><div class="metric-value" style="font-size:1.3rem;">{m_msg}</div><div><span class="status-badge {m_bg}">數值: {last['MACD']:.2f}</span></div><div class="metric-sub">籌碼動能方向</div></div>""", unsafe_allow_html=True)

                r_val = last['RSI']
                r_msg = "⚖️ 多空拔河"
                r_bg = "bg-gray"
                if r_val > 70: 
                    r_msg = "🔥 太燙了！(過熱)" 
                    r_bg = "bg-down"
                    rsi_status = "過熱"
                elif r_val < 30: 
                    r_msg = "🧊 跌過頭囉 (超賣)"
                    r_bg = "bg-up"
                    rsi_status = "超賣"
                with k4:
                    st.markdown(f"""<div class="metric-card"><div class="metric-title">RSI 強弱</div><div class="metric-value" style="font-size:1.3rem;">{r_msg}</div><div><span class="status-badge {r_bg}">數值: {r_val:.1f}</span></div><div class="metric-sub">乖離率判斷</div></div>""", unsafe_allow_html=True)

                st.markdown("#### 📏 關鍵均線監控")
                ma_html_inner = ""
                for d in ma_list:
                    val = last[f'MA_{d}']
                    prev_val = prev[f'MA_{d}']
                    arrow = "▲" if val > prev_val else "▼"
                    cls = "txt-up-vip" if val > prev_val else "txt-down-vip"
                    ma_html_inner += f'<div class="ma-box"><div class="ma-label">MA {d}</div><div class="ma-val {cls}">{val:.2f} {arrow}</div></div>'
                st.markdown(f'<div class="ma-container">{ma_html_inner}</div>', unsafe_allow_html=True)

                st.markdown("#### 📉 技術分析")
                
                st.write("##### 📅 選擇歷史走勢長度 (月)")
                chart_months = st.slider(" ", 1, 12, 6, label_visibility="collapsed")
                
                cutoff = df.index[-1] - pd.DateOffset(months=chart_months)
                df_chart = df[df.index >= cutoff].copy()
                
                all_dates = pd.date_range(start=df_chart.index[0], end=df_chart.index[-1])
                missing_dates = all_dates.difference(df_chart.index)
                range_breaks = [dict(values=missing_dates.strftime("%Y-%m-%d").tolist())]

                st.markdown("<div class='chart-title'>📈 股價走勢 & 均線</div>", unsafe_allow_html=True)
                fig_price = go.Figure()
                fig_price.add_trace(go.Candlestick(
                    x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], 
                    name='K線', showlegend=False,
                    increasing_line_color=COLOR_UP, decreasing_line_color=COLOR_DOWN
                ))
                fig_price.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MA_5'], line=dict(color='#D500F9', width=1), name='MA5', showlegend=True))
                fig_price.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MA_20'], line=dict(color='#FF6D00', width=1.5), name='MA20', showlegend=True))
                fig_price.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MA_60'], line=dict(color='#00C853', width=1.5), name='MA60', showlegend=True))
                fig_price.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MA_120'], line=dict(color='#78909C', width=1.5, dash='dot'), name='MA120', showlegend=True))
                
                fig_price.update_layout(
                    template="plotly_white",
                    height=400, 
                    margin=dict(l=10, r=10, t=10, b=100),
                    paper_bgcolor='white', plot_bgcolor='white', 
                    xaxis_rangeslider_visible=False, dragmode=False, 
                    legend=dict(orientation="h", yanchor="top", y=-0.3, xanchor="center", x=0.5, font=dict(color='black')),
                    font=dict(color='black'), 
                    xaxis=dict(color='black', showgrid=True, gridcolor='#f0f0f0'),
                    yaxis=dict(color='black', showgrid=True, gridcolor='#f0f0f0')
                )
                fig_price.update_xaxes(rangebreaks=range_breaks)
                st.plotly_chart(fig_price, use_container_width=True, config={'displayModeBar': False}, theme=None)

                # --- 成交量 ---
                vol_colors = []
                max_vol = 0
                for i in range(len(df_chart)):
                    row = df_chart.iloc[i]
                    vol = row['Volume']
                    if vol > max_vol: max_vol = vol
                    
                    vol_ma_val = row['Vol_MA'] if pd.notna(row['Vol_MA']) and row['Vol_MA'] > 0 else vol
                    ratio = vol / vol_ma_val if vol_ma_val > 0 else 1.0
                    
                    if ratio >= 2.0: c = VOL_EXPLODE
                    elif ratio >= 1.0: c = VOL_NORMAL
                    else: c = VOL_SHRINK
                    vol_colors.append(c)

                st.markdown("<div class='chart-title'>📊 成交量</div>", unsafe_allow_html=True)
                fig_vol = go.Figure()
                fig_vol.add_trace(go.Bar(x=df_chart.index, y=df_chart['Volume'], marker_color=vol_colors, name='Volume'))
                fig_vol.add_trace(go.Scatter(x=df_chart.index, y=df_chart['Vol_MA'], mode='lines', line=dict(color=VOL_MA_LINE, width=1.0), name='Vol MA'))
                
                fig_vol.update_layout(
                    template="plotly_white",
                    height=250, 
                    margin=dict(l=10, r=10, t=10, b=10), 
                    paper_bgcolor='white', plot_bgcolor='white', 
                    dragmode=False, showlegend=False,
                    yaxis=dict(range=[0, max_vol * 1.25], color='black', showgrid=True, gridcolor='#f0f0f0'),
                    xaxis=dict(color='black', showgrid=True, gridcolor='#f0f0f0'),
                    font=dict(color='black')
                )
                fig_vol.update_xaxes(rangebreaks=range_breaks)
                st.plotly_chart(fig_vol, use_container_width=True, config={'displayModeBar': False}, theme=None)

                st.markdown("<div class='chart-title'>⚡ RSI 相對強弱指標</div>", unsafe_allow_html=True)
                fig_rsi = go.Figure()
                fig_rsi.add_trace(go.Scatter(x=df_chart.index, y=df_chart['RSI'], line=dict(color='#9C27B0', width=2), name='RSI'))
                fig_rsi.add_hline(y=70, line_dash="dash", line_color=COLOR_DOWN) 
                fig_rsi.add_hline(y=30, line_dash="dash", line_color=COLOR_UP)   
                
                fig_rsi.update_layout(
                    template="plotly_white",
                    height=250, margin=dict(l=10, r=10, t=10, b=10), 
                    paper_bgcolor='white', plot_bgcolor='white', dragmode=False,
                    font=dict(color='black'), xaxis=dict(color='black', showgrid=True, gridcolor='#f0f0f0'), 
                    yaxis=dict(color='black', showgrid=True, gridcolor='#f0f0f0')
                )
                fig_rsi.update_xaxes(rangebreaks=range_breaks)
                st.plotly_chart(fig_rsi, use_container_width=True, config={'displayModeBar': False}, theme=None)

                # --- MACD ---
                full_macd_colors = []
                for i in range(len(df)):
                    hist = df['Hist'].iloc[i]
                    prev_hist = df['Hist'].iloc[i-1] if i > 0 else 0
                    
                    if hist >= 0:
                        col = MACD_BULL_GROW if hist > prev_hist else MACD_BULL_SHRINK
                    else:
                        col = MACD_BEAR_GROW if hist < prev_hist else MACD_BEAR_SHRINK
                    full_macd_colors.append(col)
                
                slice_idx = len(df) - len(df_chart)
                chart_macd_colors = full_macd_colors[slice_idx:]

                st.markdown("<div class='chart-title'>🌊 MACD 趨勢指標</div>", unsafe_allow_html=True)
                fig_macd = go.Figure()
                fig_macd.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MACD'], line=dict(color='#2196F3', width=1), name='MACD'))
                fig_macd.add_trace(go.Scatter(x=df_chart.index, y=df_chart['Signal'], line=dict(color='#FF5722', width=1), name='Signal'))
                fig_macd.add_trace(go.Bar(x=df_chart.index, y=df_chart['Hist'], marker_color=chart_macd_colors, name='Hist'))
                
                fig_macd.update_layout(
                    template="plotly_white",
                    height=250, margin=dict(l=10, r=10, t=10, b=10), 
                    paper_bgcolor='white', plot_bgcolor='white', dragmode=False,
                    font=dict(color='black'), xaxis=dict(color='black', showgrid=True, gridcolor='#f0f0f0'), 
                    yaxis=dict(color='black', showgrid=True, gridcolor='#f0f0f0')
                )
                fig_macd.update_xaxes(rangebreaks=range_breaks)
                st.plotly_chart(fig_macd, use_container_width=True, config={'displayModeBar': False}, theme=None)

                ai_suggestion = ""
                if trend_status == "多頭":
                    ai_suggestion += f"目前 {ticker_input} 呈現多頭排列，均線向上發散，顯示買盤力道強勁。"
                    if rsi_status == "過熱":
                        ai_suggestion += "惟 RSI 指標已進入過熱區 (>70)，短線可能面臨獲利了結賣壓，建議不要過度追價，可拉回五日線不破再布局。"
                    else:
                        ai_suggestion += "RSI 處於健康區間，動能充沛，可沿著均線順勢操作。"
                elif trend_status == "空頭":
                    ai_suggestion += f"目前 {ticker_input} 呈現空頭排列，均線蓋頭反壓，空方力道佔優。"
                    if rsi_status == "超賣":
                        ai_suggestion += "雖然跌勢未止，但 RSI 已進入超賣區 (<30)，短線隨時有機會出現技術性反彈，搶反彈手腳要快。"
                    else:
                        ai_suggestion += "技術指標偏弱，建議多看少做，等待底部型態打出再行進場。"
                else:
                    ai_suggestion += f"目前 {ticker_input} 處於盤整震盪階段，方向不明確。"
                    if vol_status == "爆量":
                        ai_suggestion += "雖然價格震盪，但近期出現爆量，顯示多空雙方正在激烈交戰，變盤在即，請密切注意突破方向。"
                
                st.markdown(f"""<div class="ai-summary-card"><div class="ai-title">🤖 AI 綜合判讀報告</div><div class="ai-content">{ai_suggestion}<br><br><b>關鍵數據摘要：</b><br>• 趨勢：{trend_status}<br>• 量能：{vol_status} ({vol_r:.1f}倍)<br>• 籌碼 (MACD)：{macd_status}<br>• 強弱 (RSI)：{r_val:.1f} ({rsi_status})</div></div>""", unsafe_allow_html=True)

            # ==========================================
            # 分頁 2: 交易規劃計算機 (使用局部刷新)
            # ==========================================
            with tab_calc:
                render_calculator_tab(current_close_price, exchange_rate, quote_type)

            # ==========================================
            # 分頁 3: 庫存管理 (使用局部刷新)
            # ==========================================
            with tab_inv:
                render_inventory_tab(current_close_price, quote_type)

        else:
            st.error("資料不足，請檢查股票代號。")
    except Exception as e:
        st.error(f"系統忙碌中: {e}")