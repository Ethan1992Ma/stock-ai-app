import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import google.generativeai as genai
from ta.trend import SMAIndicator, MACD
from ta.momentum import RSIIndicator
from datetime import time, datetime, timedelta
import pytz

# --- 1. 網頁設定 ---
st.set_page_config(page_title="AI 智能操盤戰情室 (VIP 終極版)", layout="wide", initial_sidebar_state="expanded")

# --- 定義全域配色常數 (VIP 客製化) ---
COLOR_UP = "#059a81"      # 上漲 (松石綠)
COLOR_DOWN = "#f23645"    # 下跌 (法拉利紅)
COLOR_NEUTRAL = "#adb5bd" # 中性灰
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
    
    .ai-summary-card {{ background-color: #e3f2fd; padding: 20px; border-radius: 15px; border-left: 5px solid #2196f3; margin-top: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; }}
    .ai-title {{ font-weight: bold; font-size: 1.2rem; color: #0d47a1 !important; margin-bottom: 10px; display: flex; align-items: center; }}
    .ai-content {{ font-size: 1rem; color: #333 !important; line-height: 1.6; white-space: pre-line; }}

    .calc-box {{ background-color: #ffffff; padding: 15px; border-radius: 12px; border: 1px solid #eee; margin-bottom: 15px; }}
    .calc-header {{ font-size: 1rem; font-weight: bold; color: #444 !important; margin-bottom: 10px; border-left: 4px solid {COLOR_UP}; padding-left: 8px; }}
    .calc-result {{ background-color: #f8f9fa; padding: 10px; border-radius: 8px; text-align: center; margin-top: 10px; }}
    .calc-res-title {{ font-size: 0.8rem; color: #888 !important; }}
    .calc-res-val {{ font-size: 1.4rem; font-weight: bold; }}
    
    .fee-badge {{ background-color: #fff3cd; color: #856404 !important; padding: 5px 10px; border-radius: 5px; font-size: 0.8rem; border: 1px solid #ffeeba; margin-bottom: 15px; display: flex; align-items: center; gap: 5px; }}
    
    /* 隱藏 Plotly Modebar */
    .js-plotly-plot .plotly .modebar {{ display: none !important; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. 數據抓取 (含 Cache 與 防斷檔機制) ---
@st.cache_data(ttl=60)
def fetch_stock_data_cached(ticker):
    try:
        stock = yf.Ticker(ticker)
        # 1. 抓日線 (長線趨勢) - 這裡用 1y 確保 MA200 算得出來
        df = stock.history(period="1y")
        
        # 2. 抓分時線 (防呆邏輯：抓 5 天)
        # prepost=True 確保抓到盤前盤後
        df_intra_raw = stock.history(period="5d", interval="5m", prepost=True)
        
        if not df_intra_raw.empty:
            # 轉換時區到台灣
            df_intra_raw.index = df_intra_raw.index.tz_convert('Asia/Taipei')
            
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
        return "⚠️ 請先在側邊欄輸入 Gemini API Key 才能啟動 AI 大腦。"
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        你是一位精通技術分析的華爾街頂級交易員。請根據以下 {ticker} 的即時數據，用繁體中文給出一段精準、犀利且具備操作指引的短評 (約 150-200 字)。
        
        【技術數據】
        - 現價: {data_summary['price']}
        - 趨勢狀態: {data_summary['trend']} (MA5 vs MA20)
        - RSI (14): {data_summary['rsi']:.1f} ({data_summary['rsi_status']})
        - MACD狀態: {data_summary['macd_status']}
        - 成交量: {data_summary['vol_status']}
        
        【回答結構】
        1. **市場現況**：一句話定調目前是多頭、空頭還是盤整。
        2. **關鍵風險/機會**：指出 RSI 是否過熱/超賣，或是 MACD 是否有背離/黃金交叉。
        3. **操作建議**：給出具體的策略（例如：拉回均線佈局、跌破 X 元停損、或是分批獲利了結）。
        4. 語氣：專業、冷靜、客觀。
        """
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ AI 分析連線失敗: {str(e)} \n請檢查 API Key 是否正確。"

# --- 5. 局部刷新元件 (計算機 & 庫存) ---
# 這裡完整保留原本的功能
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

    # 預算試算
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
        
        st.markdown(f"""
        <div class="calc-result">
            <div class="calc-res-title">可購買股數</div>
            <div class="calc-res-val" style="color:#0d6efd !important;">{max_shares:.2f} 股</div>
            <div style="font-size:0.8rem; margin-top:5px; color:#666 !important;">總成本: ${total_buy_cost_usd:.2f} USD (約 {total_buy_cost_twd:.0f} TWD)</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()

    # 賣出試算
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
        
        calc_mode = st.radio("選擇試算目標：", ["🎯 設定【目標獲利】反推股價", "💵 設定【賣出價格】計算獲利"], horizontal=True, key="calc_mode_radio")

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
            
            res_class = "txt-up-vip" if net_profit_twd >= 0 else "txt-down-vip"
            res_prefix = "+" if net_profit_twd >= 0 else ""

            st.markdown(f"""
            <div class="calc-result">
                <div class="calc-res-title">預估淨獲利 (TWD)</div>
                <div class="calc-res-val {res_class}">{res_prefix}{net_profit_twd:.0f} 元</div>
                <div style="font-size:0.8rem; color:#666 !important;">美金損益: {res_prefix}${net_profit_usd:.2f}</div>
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
    else:
        BUY_FIXED_FEE = 0.0
        BUY_RATE_FEE = 0.001
        SELL_FIXED_FEE = 0.0
        SELL_RATE_FEE = 0.001 + SEC_FEE_RATE

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
    
    pl_class = "txt-up-vip" if unrealized_pl >= 0 else "txt-down-vip"
    avg_change_class = "txt-up-vip" if new_avg_price < curr_avg_price else "txt-gray-vip"

    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">加碼後平均成交價</div>
        <div style="display:flex; justify-content:space-between; align-items:end;">
            <div class="metric-value">${new_avg_price:.2f}</div>
            <div class="{avg_change_class}">{f'⬇ 下降 ${curr_avg_price - new_avg_price:.2f}' if new_avg_price < curr_avg_price else '變動不大'}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c_res1, c_res2 = st.columns(2)
    with c_res1:
        st.markdown(f"""<div class="calc-result"><div class="calc-res-title">加碼後總股數</div><div class="calc-res-val">{total_shares:.0f} 股</div></div>""", unsafe_allow_html=True)
    with c_res2:
        st.markdown(f"""<div class="calc-result"><div class="calc-res-title">預估總損益 (含費)</div><div class="calc-res-val {pl_class}">${unrealized_pl:.2f}</div></div>""", unsafe_allow_html=True)


# --- 6. 主程式 ---
with st.sidebar:
    st.header("⚙️ 參數設定")
    ticker_input = st.text_input("股票代號", "TSLA", key="sidebar_ticker").upper()
    
    st.markdown("---")
    st.subheader("🤖 AI 設定")
    gemini_key = st.text_input("Gemini API Key", type="password", placeholder="請輸入 API Key")
    st.caption("🔗 [取得免費 Google Gemini Key](https://aistudio.google.com/app/apikey)")
    
    if st.button("🔄 更新報價 (Refresh)"):
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")
    st.caption("Technical analysis powered by yfinance & Gemini")


if ticker_input:
    # 呼叫 Cache 函數，不再每次重抓
    df, df_intra, info, quote_type = fetch_stock_data_cached(ticker_input)
    exchange_rate = fetch_exchange_rate_now()

    if not df.empty and len(df) > 20:
        # --- 指標計算 ---
        ma_list = [5, 10, 20, 30, 60, 120, 200]
        for d in ma_list:
            df[f'MA_{d}'] = SMAIndicator(df['Close'], window=d).sma_indicator()
        
        df['RSI'] = RSIIndicator(df['Close'], window=14).rsi()
        macd = MACD(df['Close'])
        df['MACD'] = macd.macd()
        df['Signal'] = macd.macd_signal()
        df['Hist'] = macd.macd_diff() 
        df['Vol_MA'] = SMAIndicator(df['Volume'], window=20).sma_indicator()

        last = df.iloc[-1]
        prev = df.iloc[-2]
        current_close_price = last['Close']
        
        # 簡易狀態判斷 (給 AI 用)
        rsi_stat = "過熱" if last['RSI'] > 70 else "超賣" if last['RSI'] < 30 else "中性"
        trend_stat = "多頭排列" if last['Close'] > last['MA_5'] > last['MA_20'] else "空頭排列" if last['Close'] < last['MA_5'] < last['MA_20'] else "盤整"
        macd_stat = "金叉向上" if last['Hist'] > 0 else "死叉向下"
        vol_stat = "量增" if last['Volume'] > df['Volume'].mean() else "量縮"

        # --- 建立 Tabs 分頁 ---
        tab_analysis, tab_calc, tab_inv = st.tabs(["📊 技術分析 & AI", "🧮 交易計算", "📦 庫存管理"])

        # ==========================================
        # 分頁 1: 技術分析 (含 Sparkline 修復 & AI)
        # ==========================================
        with tab_analysis:
            # 報價抬頭
            regular_price = info.get('currentPrice', info.get('regularMarketPrice', last['Close']))
            reg_change = regular_price - info.get('previousClose', prev['Close'])
            reg_pct = (reg_change / info.get('previousClose', prev['Close'])) * 100
            reg_class = "txt-up-vip" if reg_change > 0 else "txt-down-vip"
            
            st.markdown(f"### 📱 {info.get('longName', ticker_input)} ({ticker_input})")
            
            # --- 迷你走勢圖區塊 ---
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown("##### 📈 即時資金流向")
                if not df_intra.empty:
                    fig_spark = go.Figure()
                    
                    is_up = df_intra['Close'].iloc[-1] >= df_intra['Open'].iloc[0]
                    line_color = COLOR_UP if is_up else COLOR_DOWN
                    fill_color = f"rgba(5, 154, 129, 0.15)" if is_up else f"rgba(242, 54, 69, 0.15)"

                    fig_spark.add_trace(go.Scatter(
                        x=df_intra.index, y=df_intra['Close'], 
                        mode='lines', 
                        line=dict(color=line_color, width=2),
                        fill='tozeroy', fillcolor=fill_color
                    ))
                    
                    # X 軸修正：顯示小時:分鐘 (台灣時間)
                    fig_spark.update_xaxes(
                        tickformat="%H:%M",
                        showgrid=True, gridcolor='#eee',
                    )
                    fig_spark.update_layout(
                        height=220,
                        margin=dict(l=0, r=0, t=10, b=20),
                        paper_bgcolor='white', plot_bgcolor='white',
                        yaxis=dict(showgrid=False, visible=True, side='right'),
                        dragmode=False
                    )
                    st.plotly_chart(fig_spark, use_container_width=True, config={'displayModeBar': False})
                else:
                    st.info("⚠️ 暫無即時走勢數據 (可能為休市期間)")

            with c2:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">最新股價</div>
                    <div class="metric-value {reg_class}">${regular_price:.2f}</div>
                    <div class="metric-sub {reg_class}">{'+' if reg_change>0 else ''}{reg_change:.2f} ({reg_pct:.2f}%)</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">RSI (14)</div>
                    <div class="metric-value">{last['RSI']:.1f}</div>
                    <div class="metric-sub">{rsi_stat}</div>
                </div>
                """, unsafe_allow_html=True)

            # --- AI 分析按鈕 ---
            st.markdown("---")
            if st.button("✨ 呼叫 Gemini AI 進行分析", use_container_width=True):
                with st.spinner("AI 正在觀察盤勢..."):
                    data_summary = {
                        "price": f"{regular_price:.2f}",
                        "trend": trend_stat,
                        "rsi": last['RSI'],
                        "rsi_status": rsi_stat,
                        "macd_status": macd_stat,
                        "vol_status": vol_stat
                    }
                    ai_res = get_gemini_analysis(gemini_key, ticker_input, data_summary)
                    st.markdown(f"""
                    <div class="ai-summary-card">
                        <div class="ai-title">🧠 Gemini 觀點</div>
                        <div class="ai-content">{ai_res}</div>
                    </div>
                    """, unsafe_allow_html=True)

            # --- 傳統技術分析圖表 (日線) ---
            st.markdown("##### 📉 趨勢與籌碼")
            
            # K線圖
            fig_price = go.Figure()
            fig_price.add_trace(go.Candlestick(
                x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], 
                name='K線', showlegend=False,
                increasing_line_color=COLOR_UP, decreasing_line_color=COLOR_DOWN
            ))
            fig_price.add_trace(go.Scatter(x=df.index, y=df['MA_5'], line=dict(color='#D500F9', width=1), name='MA5'))
            fig_price.add_trace(go.Scatter(x=df.index, y=df['MA_20'], line=dict(color='#FF6D00', width=1.5), name='MA20'))
            
            fig_price.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0), xaxis_rangeslider_visible=False)
            st.plotly_chart(fig_price, use_container_width=True)

            # MACD 圖
            fig_macd = go.Figure()
            colors = []
            for i in range(len(df)):
                h = df['Hist'].iloc[i]
                prev_h = df['Hist'].iloc[i-1] if i > 0 else 0
                if h >= 0:
                    colors.append(MACD_BULL_GROW if h > prev_h else MACD_BULL_SHRINK)
                else:
                    colors.append(MACD_BEAR_GROW if h < prev_h else MACD_BEAR_SHRINK)
            
            fig_macd.add_trace(go.Bar(x=df.index, y=df['Hist'], marker_color=colors, name='MACD Hist'))
            fig_macd.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='#2196F3'), name='MACD'))
            fig_macd.add_trace(go.Scatter(x=df.index, y=df['Signal'], line=dict(color='#FF5722'), name='Signal'))
            fig_macd.update_layout(height=200, margin=dict(l=0, r=0, t=10, b=20))
            st.plotly_chart(fig_macd, use_container_width=True)

        # ==========================================
        # 分頁 2: 交易計算機 (使用局部刷新)
        # ==========================================
        with tab_calc:
            render_calculator_tab(current_close_price, exchange_rate, quote_type)

        # ==========================================
        # 分頁 3: 庫存管理 (使用局部刷新)
        # ==========================================
        with tab_inv:
            render_inventory_tab(current_close_price, quote_type)

    else:
        st.error("❌ 資料抓取失敗或代號錯誤，請檢查。")
