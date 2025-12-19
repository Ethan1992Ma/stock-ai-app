import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from ta.trend import SMAIndicator, MACD
from ta.momentum import RSIIndicator
import pytz
from datetime import datetime, time, timedelta

# --- 1. 網頁設定 ---
st.set_page_config(page_title="AI 智能操盤戰情室 (VIP 終極版)", layout="wide", initial_sidebar_state="collapsed")

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
    h1, h2, h3, h4, h5, h6, p, div, label, li {{ color: #000000 !important; }}
    .stTextInput > label, .stNumberInput > label, .stRadio > label {{ color: #000000 !important; }}
    
    .txt-up-vip {{ color: {COLOR_UP} !important; font-weight: bold; }}
    .txt-down-vip {{ color: {COLOR_DOWN} !important; font-weight: bold; }}
    .txt-gray-vip {{ color: {COLOR_NEUTRAL} !important; }}
    
    .chart-title {{ font-size: 1.1rem; font-weight: 700; color: #000000 !important; margin-top: 10px; margin-bottom: 0px; padding-left: 5px; }}
    .metric-card {{ background-color: #ffffff; padding: 20px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 10px; border: 1px solid #f0f0f0; position: relative; }}
    .metric-title {{ color: #6c757d !important; font-size: 0.9rem; font-weight: 700; margin-bottom: 5px; }}
    .metric-value {{ font-size: 1.8rem; font-weight: 800; color: #212529 !important; }}
    .metric-sub {{ font-size: 0.9rem; margin-top: 5px; }} 
    
    .ext-price-box {{ background-color: #f1f3f5; padding: 4px 8px; border-radius: 6px; font-size: 0.85rem; font-weight: 600; color: #666 !important; margin-top: 8px; display: inline-block; }}
    .ext-label {{ font-size: 0.75rem; color: #999 !important; margin-right: 5px; }}
    .spark-scale {{ position: absolute; right: 15px; top: 55%; transform: translateY(-50%); text-align: right; font-size: 0.7rem; line-height: 1.4; font-weight: 600; }}

    .ai-summary-card {{ background-color: #e3f2fd; padding: 20px; border-radius: 15px; border-left: 5px solid #2196f3; margin-top: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; }}
    .ai-title {{ font-weight: bold; font-size: 1.2rem; color: #0d47a1 !important; margin-bottom: 10px; display: flex; align-items: center; }}
    .ai-content {{ font-size: 1rem; color: #333 !important; line-height: 1.6; }}

    .ma-container {{ display: flex; flex-wrap: wrap; gap: 10px; background-color: #ffffff; padding: 20px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #f0f0f0; margin-bottom: 20px; }}
    .ma-box {{ flex: 1 1 100px; text-align: center; padding: 10px; background-color: #f8f9fa; border-radius: 10px; border: 1px solid #dee2e6; }}
    .ma-label {{ font-size: 0.8rem; font-weight: bold; color: #666 !important; margin-bottom: 5px; }}
    .ma-val {{ font-size: 1.1rem; font-weight: 800; }}
    
    .status-badge {{ padding: 4px 8px; border-radius: 6px; font-size: 0.85rem; font-weight: bold; color: white !important; display: inline-block; margin-top: 8px; }}
    .bg-up {{ background-color: {COLOR_UP}; }}
    .bg-down {{ background-color: {COLOR_DOWN}; }}
    .bg-gray {{ background-color: {COLOR_NEUTRAL}; }}
    .bg-blue {{ background-color: #0d6efd; }}

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
        if not hist.empty: return hist['Close'].iloc[-1]
        return 32.5
    except: return 32.5

# --- 4. 定義局部刷新元件 ---
@st.fragment
def render_calculator_tab(current_close_price, exchange_rate, quote_type):
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
        else: st.error("預算不足以支付手續費")
    
    st.markdown("---")

    with st.container():
        st.markdown('<div class="calc-header">⚖️ 賣出試算 (獲利預估)</div>', unsafe_allow_html=True)
        c_input1, c_input2 = st.columns(2)
        with c_input1: shares_held = st.number_input("持有股數", value=10.0, step=1.0, key="hold_shares_input")
        with c_input2:
            if "cost_price_input" not in st.session_state: st.session_state.cost_price_input = float(current_close_price)
            cost_price = st.number_input("買入成本 (USD)", key="cost_price_input", step=0.1, format="%.2f")

        real_buy_cost_usd = (cost_price * shares_held * (1 + BUY_RATE_FEE)) + BUY_FIXED_FEE
        breakeven_price = (real_buy_cost_usd + SELL_FIXED_FEE) / (shares_held * (1 - SELL_RATE_FEE))
        st.caption(f"🛡️ 損益兩平價 (含手續費): **${breakeven_price:.2f}**")
        st.divider()

        calc_mode = st.radio("選擇試算目標：", ["🎯 設定【目標獲利】反推股價", "💵 設定【賣出價格】計算獲利"], horizontal=True, key="calc_mode_radio")

        if calc_mode == "🎯 設定【目標獲利】反推股價":
            target_profit_twd = st.number_input("我想賺多少台幣 (TWD)?", value=3000, step=500, key="target_profit_input")
            target_sell_price = ((target_profit_twd / exchange_rate) + real_buy_cost_usd + SELL_FIXED_FEE) / (shares_held * (1 - SELL_RATE_FEE))
            pct_need = ((target_sell_price / cost_price) - 1) * 100 if cost_price > 0 else 0
            st.markdown(f"""<div class="calc-result"><div class="calc-res-title">建議掛單賣出價</div><div class="calc-res-val txt-up-vip">${target_sell_price:.2f}</div><div style="font-size:0.8rem;" class="txt-up-vip">需上漲 {pct_need:.1f}%</div></div>""", unsafe_allow_html=True)
        else:
            if "target_sell_input" not in st.session_state: st.session_state.target_sell_input = float(cost_price) * 1.05
            target_sell_input = st.number_input("預計賣出價格 (USD)", key="target_sell_input", step=0.1, format="%.2f")
            net_profit_twd = ((target_sell_input * shares_held * (1 - SELL_RATE_FEE)) - SELL_FIXED_FEE - real_buy_cost_usd) * exchange_rate
            res_class, res_prefix = ("txt-up-vip", "+") if net_profit_twd >= 0 else ("txt-down-vip", "")
            st.markdown(f"""<div class="calc-result"><div class="calc-res-title">預估淨獲利 (TWD)</div><div class="calc-res-val {res_class}">{res_prefix}{net_profit_twd:.0f} 元</div><div style="font-size:0.8rem; color:#666 !important;">美金損益: {res_prefix}${net_profit_twd/exchange_rate:.2f}</div></div>""", unsafe_allow_html=True)

@st.fragment
def render_inventory_tab(current_close_price, quote_type):
    st.markdown("#### 📦 庫存損益與加碼攤平")
    SEC_FEE_RATE = 0.0000278
    if quote_type == 'ETF':
        BUY_FIXED_FEE, BUY_RATE_FEE = 3.0, 0.0
        SELL_FIXED_FEE, SELL_RATE_FEE = 3.0, SEC_FEE_RATE
        fee_badge_text = "💡 檢測為 **ETF**：套用固定手續費 **$3 USD**"
    else:
        BUY_FIXED_FEE, BUY_RATE_FEE = 0.0, 0.001
        SELL_FIXED_FEE, SELL_RATE_FEE = 0.0, 0.001 + SEC_FEE_RATE
        fee_badge_text = "💡 檢測為 **一般股票**：套用費率 **0.1%**"
    st.caption(f"{fee_badge_text}")

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
    total_cost_real = ((curr_shares * curr_avg_price * (1 + BUY_RATE_FEE)) + (BUY_FIXED_FEE if curr_shares > 0 else 0)) + \
                      ((new_shares * new_buy_price * (1 + BUY_RATE_FEE)) + (BUY_FIXED_FEE if new_shares > 0 else 0))
    new_avg_price = (curr_shares * curr_avg_price + new_shares * new_buy_price) / total_shares if total_shares > 0 else 0
    market_val_net = (total_shares * new_buy_price * (1 - SELL_RATE_FEE)) - (SELL_FIXED_FEE if total_shares > 0 else 0)
    unrealized_pl = market_val_net - total_cost_real
    
    pl_class = "txt-up-vip" if unrealized_pl >= 0 else "txt-down-vip"
    avg_change_class = "txt-up-vip" if new_avg_price < curr_avg_price else "txt-gray-vip"

    st.markdown(f"""
    <div class="metric-card"><div class="metric-title">加碼後平均成交價</div><div style="display:flex; justify-content:space-between; align-items:end;">
        <div class="metric-value">${new_avg_price:.2f}</div><div class="{avg_change_class}">{f'⬇ 下降 ${curr_avg_price - new_avg_price:.2f}' if new_avg_price < curr_avg_price else '變動不大'}</div></div></div>
    """, unsafe_allow_html=True)

    c_res1, c_res2 = st.columns(2)
    with c_res1: st.markdown(f"""<div class="calc-result"><div class="calc-res-title">加碼後總股數</div><div class="calc-res-val">{total_shares:.0f} 股</div></div>""", unsafe_allow_html=True)
    with c_res2: st.markdown(f"""<div class="calc-result"><div class="calc-res-title">預估總損益 (含費)</div><div class="calc-res-val {pl_class}">${unrealized_pl:.2f}</div></div>""", unsafe_allow_html=True)

# --- 5. 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 參數設定")
    ticker_input = st.text_input("股票代號", "TSLA", key="sidebar_ticker").upper()
    if st.button("🔄 更新報價 (Refresh)"):
        if 'stored_ticker' in st.session_state: del st.session_state['stored_ticker']
        st.rerun()
    st.markdown("---")
    st.subheader("🧠 策略邏輯")
    strategy_mode = st.radio("判讀模式", ["🤖 自動判別 (Auto)", "🛠️ 手動設定 (Manual)"], key="sidebar_strat_mode")
    strat_fast, strat_slow, strat_desc = 5, 20, "預設"
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
                st.session_state.update(stored_ticker=ticker_input, data_df=df, data_df_intra=df_intra, data_info=info, data_quote_type=quote_type, data_exchange_rate=exchange_rate)
                for k in ["buy_price_input", "cost_price_input", "target_sell_input", "inv_curr_avg", "inv_new_price"]:
                    if k in st.session_state: del st.session_state[k]

        df, df_intra, info = st.session_state.data_df, st.session_state.data_df_intra, st.session_state.data_info
        quote_type, exchange_rate = st.session_state.data_quote_type, st.session_state.data_exchange_rate

        if not df.empty and len(df) > 200:
            if strategy_mode == "🤖 自動判別 (Auto)":
                strat_fast, strat_slow = (10, 20) if info.get('marketCap', 0) > 200_000_000_000 else (5, 10)
                strat_desc = "🐘 巨頭穩健" if info.get('marketCap', 0) > 200_000_000_000 else "🚀 小型飆股"
            
            ma_list = [5, 10, 20, 30, 60, 120, 200]
            for d in ma_list: df[f'MA_{d}'] = SMAIndicator(df['Close'], window=d).sma_indicator()
            
            last = df.iloc[-1]
            strat_fast_val, strat_slow_val = SMAIndicator(df['Close'], window=strat_fast).sma_indicator().iloc[-1], SMAIndicator(df['Close'], window=strat_slow).sma_indicator().iloc[-1]
            
            df['RSI'] = RSIIndicator(df['Close'], window=14).rsi()
            macd = MACD(df['Close'])
            df['MACD'], df['Signal'], df['Hist'] = macd.macd(), macd.macd_signal(), macd.macd_diff()
            # [修復 Hist 錯誤] 
            df['Hist'] = df['Hist'].fillna(0)
            
            df['Vol_MA'] = SMAIndicator(df['Volume'], window=20).sma_indicator()
            current_close_price = last['Close']

            tab_analysis, tab_calc, tab_inv = st.tabs(["📊 技術分析", "🧮 交易計算", "📦 庫存管理"])

            with tab_analysis:
                # --- 準備資料 & 時區處理 ---
                if not df_intra.empty:
                    df_intra.index = pd.to_datetime(df_intra.index)
                    if ".TW" in ticker_input:
                        tz_str = 'Asia/Taipei'
                        open_time, close_time = time(9, 0), time(13, 30)
                    else:
                        tz_str = 'America/New_York'
                        open_time, close_time = time(9, 30), time(16, 0)
                    
                    try: df_intra_tz = df_intra.tz_convert(tz_str)
                    except: df_intra_tz = df_intra

                    # 計算 H/L (僅正規交易時間)
                    mask_reg_hl = (df_intra_tz.index.time >= open_time) & (df_intra_tz.index.time <= close_time)
                    df_reg_hl = df_intra_tz[mask_reg_hl]
                    day_high = df_reg_hl['High'].max() if not df_reg_hl.empty else df_intra_tz['High'].max()
                    day_low = df_reg_hl['Low'].min() if not df_reg_hl.empty else df_intra_tz['Low'].min()

                previous_close = info.get('previousClose', df.iloc[-2]['Close'])
                regular_price = info.get('currentPrice', info.get('regularMarketPrice', last['Close']))
                
                # 判斷盤前/盤後價格
                is_extended, ext_price, ext_label = False, 0, ""
                live_price = df_intra['Close'].iloc[-1] if not df_intra.empty else 0
                
                if info.get('preMarketPrice'):
                     ext_price, is_extended, ext_label = info['preMarketPrice'], True, "盤前"
                elif info.get('postMarketPrice'):
                     ext_price, is_extended, ext_label = info['postMarketPrice'], True, "盤後"
                elif abs(live_price - regular_price) / regular_price > 0.001:
                     ext_price, is_extended, ext_label = live_price, True, "盤後/試撮"

                reg_change = regular_price - previous_close
                reg_pct = (reg_change / previous_close) * 100
                reg_class = "txt-up-vip" if reg_change > 0 else "txt-down-vip"

                st.markdown(f"### 📱 {info.get('longName', ticker_input)} ({ticker_input})")
                st.caption(f"目前策略：{strat_desc}")

                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    fig_spark = go.Figure()
                    if not df_intra.empty:
                        # 繪製走勢圖 (只畫正規時間的填充，其餘虛線)
                        fig_spark.add_trace(go.Scatter(x=df_intra_tz.index, y=df_intra_tz['Close'], mode='lines', line=dict(color='#bdc3c7', width=1.5, dash='dot'), hoverinfo='skip'))
                        
                        mask = (df_intra_tz.index.time >= open_time) & (df_intra_tz.index.time <= close_time)
                        df_regular = df_intra_tz[mask]
                        if not df_regular.empty:
                            day_open_reg = df_regular['Open'].iloc[0]
                            day_close_reg = df_regular['Close'].iloc[-1]
                            spark_color = COLOR_UP if day_close_reg >= day_open_reg else COLOR_DOWN
                            fill_color = "rgba(5, 154, 129, 0.15)" if day_close_reg >= day_open_reg else "rgba(242, 54, 69, 0.15)"
                            fig_spark.add_trace(go.Scatter(x=df_regular.index, y=df_regular['Close'], mode='lines', line=dict(color=spark_color, width=2), fill='tozeroy', fillcolor=fill_color))

                        # --- [核心修正: 鎖定美股冬令時間軸] ---
                        if ".TW" not in ticker_input:
                            current_date = df_intra_tz.index[0].date()
                            tz_ny = pytz.timezone('America/New_York')
                            
                            # 強制鎖定美東時間 04:00 - 20:00 (對應台灣 17:00 - 09:00 冬令)
                            dt_start = tz_ny.localize(datetime.combine(current_date, time(4, 0)))
                            dt_end = tz_ny.localize(datetime.combine(current_date, time(20, 0)))
                            
                            fig_spark.update_layout(xaxis=dict(range=[dt_start, dt_end], visible=False))
                        else:
                             fig_spark.update_layout(xaxis=dict(visible=False))

                        y_min, y_max = day_low * 0.999, day_high * 1.001
                        fig_spark.update_layout(height=80, margin=dict(l=0, r=40, t=5, b=5), yaxis=dict(visible=False, range=[y_min, y_max]), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False, dragmode=False)

                        # 價格與 H/L 顯示
                        price_html = f"""<div class="metric-card"><div class="metric-title">最新股價</div><div class="metric-value {reg_class}">{regular_price:.2f}</div><div class="metric-sub {reg_class}">{('+' if reg_change > 0 else '')}{reg_change:.2f} ({reg_pct:.2f}%)</div>"""
                        if is_extended:
                            ext_change = ext_price - regular_price
                            ext_pct = (ext_change / regular_price) * 100
                            ext_class = "txt-up-vip" if ext_change > 0 else "txt-down-vip"
                            price_html += f"""<div class="ext-price-box"><span class="ext-label">{ext_label}</span><span class="{ext_class}">{ext_price:.2f} ({('+' if ext_pct > 0 else '')}{ext_pct:.2f}%)</span></div>"""
                        
                        day_high_pct = ((day_high - previous_close) / previous_close) * 100
                        day_low_pct = ((day_low - previous_close) / previous_close) * 100
                        h_class = "txt-up-vip" if day_high_pct >= 0 else "txt-down-vip"
                        l_class = "txt-up-vip" if day_low_pct >= 0 else "txt-down-vip"
                        
                        price_html += f"""<div class="spark-scale"><div class="{h_class}">H: {day_high_pct:+.1f}%</div><div style="margin-top:25px;" class="{l_class}">L: {day_low_pct:+.1f}%</div></div></div>"""
                        st.markdown(price_html, unsafe_allow_html=True)
                        st.plotly_chart(fig_spark, use_container_width=True, config={'displayModeBar': False, 'staticPlot': True})
                        
                        # --- [核心修正: 完美對齊的時間軸] ---
                        if ".TW" not in ticker_input:
                            timeline_html = f"""
                            <div style="position: relative; height: 35px; margin-top: 5px; border-top: 1px dashed #eee; font-size: 0.65rem; color: #999; width: 100%;">
                                <div style="position: absolute; left: 0%; transform: translateX(0%); text-align: left;">
                                    <span>盤前</span><br><b style="color:#555">17:00</b>
                                </div>
                                <div style="position: absolute; left: 34.375%; transform: translateX(-50%); text-align: center;">
                                    <span>🔔 開盤</span><br><b style="color:#000">22:30</b>
                                </div>
                                <div style="position: absolute; left: 75%; transform: translateX(-50%); text-align: center;">
                                    <span>🌙 收盤</span><br><b style="color:#000">05:00</b>
                                </div>
                                <div style="position: absolute; right: 0%; transform: translateX(0%); text-align: right;">
                                    <span>結算</span><br><b style="color:#555">09:00</b>
                                </div>
                            </div>
                            """
                            st.markdown(timeline_html, unsafe_allow_html=True)
                    else:
                        st.info("暫無即時數據")

                # 其餘基本面數據
                with c2: st.markdown(f"""<div class="metric-card"><div class="metric-title">本益比 (P/E)</div><div class="metric-value">{info.get('trailingPE', 'N/A')}</div><div class="metric-sub">估值參考</div></div>""", unsafe_allow_html=True)
                with c3: st.markdown(f"""<div class="metric-card"><div class="metric-title">EPS</div><div class="metric-value">{info.get('trailingEps', 'N/A')}</div><div class="metric-sub">獲利能力</div></div>""", unsafe_allow_html=True)
                with c4:
                    mcap = info.get('marketCap', 0)
                    m_str = f"{mcap/1000000000:.1f}B" if mcap > 1000000000 else f"{mcap/1000000:.1f}M"
                    st.markdown(f"""<div class="metric-card"><div class="metric-title">市值</div><div class="metric-value">{m_str}</div><div class="metric-sub">{info.get('sector','N/A')}</div></div>""", unsafe_allow_html=True)

                st.markdown("#### 🤖 策略訊號解讀")
                k1, k2, k3, k4 = st.columns(4)
                
                # [修復 Hist 讀取] 
                hist_val = last.get('Hist', 0)
                
                trend_status, trend_msg, trend_bg = "盤整", "💤 睡覺行情 (盤整)", "bg-gray"
                if last['Close'] > strat_fast_val > strat_slow_val: trend_status, trend_msg, trend_bg = "多頭", "🚀 火力全開！(多頭)", "bg-up"
                elif last['Close'] < strat_fast_val < strat_slow_val: trend_status, trend_msg, trend_bg = "空頭", "🐻 熊出沒注意 (空頭)", "bg-down"
                with k1: st.markdown(f"""<div class="metric-card"><div class="metric-title">趨勢訊號</div><div class="metric-value" style="font-size:1.3rem;">{trend_msg}</div><div><span class="status-badge {trend_bg}">MA{strat_fast} vs MA{strat_slow}</span></div></div>""", unsafe_allow_html=True)
                
                vol_r = last['Volume'] / df['Vol_MA'].iloc[-1] if df['Vol_MA'].iloc[-1] > 0 else 0
                v_msg, v_bg = "❄️ 冷冷清清", "bg-gray"
                if vol_r > 2.0: v_msg, v_bg = "🔥 資金派對 (爆量)", "bg-down"
                elif vol_r > 1.0: v_msg, v_bg = "💧 人氣回溫", "bg-blue"
                with k2: st.markdown(f"""<div class="metric-card"><div class="metric-title">量能判讀</div><div class="metric-value" style="font-size:1.3rem;">{v_msg}</div><div><span class="status-badge {v_bg}">{vol_r:.1f} 倍均量</span></div></div>""", unsafe_allow_html=True)

                m_msg, m_bg = ("🐂 牛軍集結", "bg-up") if hist_val > 0 else ("📉 空軍壓境", "bg-down")
                with k3: st.markdown(f"""<div class="metric-card"><div class="metric-title">MACD 趨勢</div><div class="metric-value" style="font-size:1.3rem;">{m_msg}</div><div><span class="status-badge {m_bg}">{last.get('MACD', 0):.2f}</span></div></div>""", unsafe_allow_html=True)

                r_val = last['RSI']
                r_msg, r_bg = "⚖️ 多空拔河", "bg-gray"
                if r_val > 70: r_msg, r_bg = "🔥 太燙了！(過熱)", "bg-down"
                elif r_val < 30: r_msg, r_bg = "🧊 跌過頭囉 (超賣)", "bg-up"
                with k4: st.markdown(f"""<div class="metric-card"><div class="metric-title">RSI 強弱</div><div class="metric-value" style="font-size:1.3rem;">{r_msg}</div><div><span class="status-badge {r_bg}">{r_val:.1f}</span></div></div>""", unsafe_allow_html=True)

                # --- 其餘圖表部分 ---
                st.markdown("#### 📏 關鍵均線監控")
                ma_html = "".join([f'<div class="ma-box"><div class="ma-label">MA {d}</div><div class="ma-val {"txt-up-vip" if last[f"MA_{d}"] > df.iloc[-2][f"MA_{d}"] else "txt-down-vip"}">{last[f"MA_{d}"]:.2f} {"▲" if last[f"MA_{d}"] > df.iloc[-2][f"MA_{d}"] else "▼"}</div></div>' for d in ma_list])
                st.markdown(f'<div class="ma-container">{ma_html}</div>', unsafe_allow_html=True)
                
                st.markdown("#### 📉 技術分析")
                st.write("##### 📅 選擇歷史走勢長度 (月)")
                chart_months = st.slider(" ", 1, 12, 6, label_visibility="collapsed")
                
                cutoff = df.index[-1] - pd.DateOffset(months=chart_months)
                df_chart = df[df.index >= cutoff].copy()
                range_breaks = [dict(values=pd.date_range(start=df_chart.index[0], end=df_chart.index[-1]).difference(df_chart.index).strftime("%Y-%m-%d").tolist())]

                st.markdown("<div class='chart-title'>📈 股價走勢 & 均線</div>", unsafe_allow_html=True)
                fig_price = go.Figure()
                fig_price.add_trace(go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], increasing_line_color=COLOR_UP, decreasing_line_color=COLOR_DOWN))
                for m, c in zip([5, 20, 60], ['#D500F9', '#FF6D00', '#00C853']): fig_price.add_trace(go.Scatter(x=df_chart.index, y=df_chart[f'MA_{m}'], line=dict(color=c, width=1), name=f'MA{m}'))
                fig_price.update_layout(height=400, margin=dict(l=10,r=10,t=10,b=50), xaxis_rangeslider_visible=False, showlegend=False, template="plotly_white")
                fig_price.update_xaxes(rangebreaks=range_breaks)
                st.plotly_chart(fig_price, use_container_width=True)

                st.markdown("<div class='chart-title'>📊 成交量</div>", unsafe_allow_html=True)
                colors = [VOL_EXPLODE if (r['Volume']/(r['Vol_MA'] if r['Vol_MA']>0 else 1))>=2 else VOL_NORMAL if (r['Volume']/(r['Vol_MA'] if r['Vol_MA']>0 else 1))>=1 else VOL_SHRINK for _, r in df_chart.iterrows()]
                fig_vol = go.Figure(data=[go.Bar(x=df_chart.index, y=df_chart['Volume'], marker_color=colors), go.Scatter(x=df_chart.index, y=df_chart['Vol_MA'], line=dict(color='black', width=1))])
                fig_vol.update_layout(height=200, margin=dict(l=10,r=10,t=10,b=10), showlegend=False, template="plotly_white")
                fig_vol.update_xaxes(rangebreaks=range_breaks)
                st.plotly_chart(fig_vol, use_container_width=True)

                st.markdown("<div class='chart-title'>⚡ RSI & MACD</div>", unsafe_allow_html=True)
                c_rsi, c_macd = st.columns(2)
                with c_rsi:
                    fig_rsi = go.Figure(go.Scatter(x=df_chart.index, y=df_chart['RSI'], line=dict(color='#9C27B0')))
                    fig_rsi.add_hline(y=70, line_dash="dash", line_color='red'); fig_rsi.add_hline(y=30, line_dash="dash", line_color='green')
                    fig_rsi.update_layout(height=200, margin=dict(l=10,r=10,t=10,b=10), template="plotly_white"); fig_rsi.update_xaxes(rangebreaks=range_breaks)
                    st.plotly_chart(fig_rsi, use_container_width=True)
                with c_macd:
                    # [修復 Hist 繪圖]
                    hist_data = df_chart['Hist'].fillna(0)
                    fig_macd = go.Figure([go.Scatter(x=df_chart.index, y=df_chart['MACD'], line=dict(color='#2196F3')), go.Scatter(x=df_chart.index, y=df_chart['Signal'], line=dict(color='#FF5722')), go.Bar(x=df_chart.index, y=hist_data, marker_color=[(MACD_BULL_GROW if h>0 else MACD_BEAR_GROW) for h in hist_data])])
                    fig_macd.update_layout(height=200, margin=dict(l=10,r=10,t=10,b=10), showlegend=False, template="plotly_white"); fig_macd.update_xaxes(rangebreaks=range_breaks)
                    st.plotly_chart(fig_macd, use_container_width=True)

                st.markdown(f"""<div class="ai-summary-card"><div class="ai-title">🤖 AI 綜合判讀報告</div><div class="ai-content">目前 {ticker_input} 呈現{trend_status}排列，RSI 數值 {r_val:.1f} ({r_msg})。請留意上方壓力與支撐。</div></div>""", unsafe_allow_html=True)

            with tab_calc: render_calculator_tab(current_close_price, exchange_rate, quote_type)
            with tab_inv: render_inventory_tab(current_close_price, quote_type)
        else: st.error("資料不足")
    except Exception as e: st.error(f"系統忙碌中: {e}")