import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
# 使用你成功安裝的 ta 套件
from ta.trend import SMAIndicator, MACD
from ta.momentum import RSIIndicator

# --- 網頁設定 (手機優先模式) ---
st.set_page_config(page_title="AI 智能操盤手", layout="wide", initial_sidebar_state="expanded")

# --- CSS 優化手機閱讀體驗 ---
st.markdown("""
    <style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 10px;
    }
    div[data-testid="stExpander"] details summary p {
        font-size: 1.1rem;
        font-weight: 600;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📱 AI 智能操盤手 (雙模組+多指標)")

# --- 側邊欄：設定 ---
st.sidebar.header("🔍 股票與策略設定")
ticker = st.sidebar.text_input("輸入代碼 (如 NVDA, ONDS, TSLA)", "TSLA").upper()

st.sidebar.markdown("---")
st.sidebar.header("⚙️ 策略邏輯選擇")

# 策略模式選擇
strategy_mode = st.sidebar.radio(
    "選擇判斷模式",
    ("🤖 自動判別 (Auto-Detect)", "🛠️ 手動設定 (Manual)"),
    help="自動判別會根據市值大小，自動切換適合巨頭股或小型股的均線參數。"
)

# 初始化參數變數
buy_fast, buy_slow = 5, 10
sell_fast, sell_slow = 20, 60
strategy_name = "預設"

# 函數：取得股票資訊與自動策略
def get_stock_info_and_strategy(ticker_symbol, mode):
    try:
        stock = yf.Ticker(ticker_symbol)
        info = stock.info
        
        # 取得市值 (若無數據則預設為 0)
        market_cap = info.get('marketCap', 0)
        
        # 策略邏輯
        s_buy_f, s_buy_s, s_sell_f, s_sell_s = 5, 10, 20, 60 # 預設值
        s_type = "手動/未知"

        if mode == "🤖 自動判別 (Auto-Detect)":
            # 門檻：2000億美金 (約 6兆台幣) 定義為巨頭
            if market_cap > 200_000_000_000: 
                # --- Mega Tech Strategy (穩健趨勢) ---
                s_type = "🐘 巨頭穩健策略 (Mega Cap)"
                s_buy_f, s_buy_s = 10, 20   # 進場較慢，確認趨勢
                s_sell_f, s_sell_s = 20, 60 # 出場寬鬆，吃大波段
            else:
                # --- Small/Penny Stock Strategy (靈敏快進快出) ---
                s_type = "🚀 小型妖股策略 (Small Cap)"
                s_buy_f, s_buy_s = 3, 8     # 極速進場
                s_sell_f, s_sell_s = 5, 20  # 苗頭不對立刻跑
        else:
            s_type = "🛠️ 使用者手動設定"
            
        return info, s_type, s_buy_f, s_buy_s, s_sell_f, s_sell_s
    except Exception as e:
        # 回傳空資訊以防報錯
        return {}, "無法取得基本面資訊", 5, 10, 20, 60

# 若選擇手動，顯示滑桿；若自動，則隱藏滑桿但顯示數值
if strategy_mode == "🛠️ 手動設定 (Manual)":
    st.sidebar.subheader("手動參數調整")
    buy_fast = st.sidebar.number_input("買進快線 (MA)", value=5)
    buy_slow = st.sidebar.number_input("買進慢線 (MA)", value=10)
    sell_fast = st.sidebar.number_input("賣出快線 (MA)", value=20)
    sell_slow = st.sidebar.number_input("賣出慢線 (MA)", value=60)
else:
    # 預先執行一次 info 抓取以決定參數顯示給使用者看
    _, strategy_name, buy_fast, buy_slow, sell_fast, sell_slow = get_stock_info_and_strategy(ticker, strategy_mode)
    st.sidebar.info(f"偵測模式：\n{strategy_name}")
    st.sidebar.text(f"當前參數：買({buy_fast}/{buy_slow}) 賣({sell_fast}/{sell_slow})")

# --- 核心分析函數 ---
def analyze_data(ticker, b_f, b_s, s_f, s_s):
    try:
        # 下載資料
        df = yf.download(ticker, period="1y", auto_adjust=True)
        
        # 處理 yfinance 可能返回的多層索引 (MultiIndex)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        if df.empty: return None, "無數據"
        
        # 1. 基礎均線 (使用 ta 套件)
        mas = [5, 10, 20, 60, 120]
        for m in mas:
            indicator = SMAIndicator(close=df['Close'], window=m)
            df[f'MA_{m}'] = indicator.sma_indicator()

        # 2. 雙邏輯策略均線
        df['Buy_Fast'] = SMAIndicator(close=df['Close'], window=b_f).sma_indicator()
        df['Buy_Slow'] = SMAIndicator(close=df['Close'], window=b_s).sma_indicator()
        df['Sell_Fast'] = SMAIndicator(close=df['Close'], window=s_f).sma_indicator()
        df['Sell_Slow'] = SMAIndicator(close=df['Close'], window=s_s).sma_indicator()

        # 3. RSI (14天)
        df['RSI'] = RSIIndicator(close=df['Close'], window=14).rsi()

        # 4. MACD (12, 26, 9)
        macd = MACD(close=df['Close'], window_slow=26, window_fast=12, window_sign=9)
        df['MACD_Line'] = macd.macd()
        df['MACD_Signal'] = macd.macd_signal()
        df['MACD_Hist'] = macd.macd_diff()

        return df, None
    except Exception as e:
        return None, str(e)

# --- 主執行區 ---
if st.button("🚀 開始智能診斷", type="primary", use_container_width=True):
    with st.spinner('正在連線 API、分析籌碼與計算指標...'):
        # 1. 取得基本面與策略
        info, strat_name, b_f, b_s, s_f, s_s = get_stock_info_and_strategy(ticker, strategy_mode)
        
        # 2. 取得技術面數據
        df, err = analyze_data(ticker, b_f, b_s, s_f, s_s)

    if err:
        st.error(f"發生錯誤: {err}")
    else:
        # 資料準備
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # --- A. 股票資訊卡 (Header) ---
        col_h1, col_h2 = st.columns([1, 2])
        with col_h1:
            change = last['Close'] - prev['Close']
            st.metric("最新收盤", f"{last['Close']:.2f}", f"{change:.2f}")
        with col_h2:
            st.markdown(f"**{info.get('longName', ticker)}**")
            st.caption(f"策略應用：{strat_name}")
            market_cap_val = info.get('marketCap', 0)
            if market_cap_val > 1000000000:
                mcap_str = f"{market_cap_val/1000000000:.2f} B"
            else:
                mcap_str = f"{market_cap_val/1000000:.2f} M"
            st.text(f"市值: {mcap_str} | 產業: {info.get('sector', 'N/A')}")

        st.divider()

        # --- B. 綜合判讀報告 (手機易讀版) ---
        st.subheader("📋 AI 綜合判讀")
        
        # 1. 價格邏輯
        buy_sig = last['Buy_Fast'] > last['Buy_Slow']
        sell_sig = last['Sell_Fast'] < last['Sell_Slow']
        
        status_col1, status_col2 = st.columns(2)
        with status_col1:
            if buy_sig:
                st.success(f"多方：持有中 (MA{b_f} > MA{b_s})")
            else:
                st.warning("多方：觀望")
        with status_col2:
            if sell_sig:
                st.error(f"空方：警戒 (MA{s_f} < MA{s_s})")
            else:
                st.success("空方：安全")

        # 2. RSI 判讀
        rsi_val = last['RSI']
        if rsi_val > 70:
            st.markdown(f"**RSI ({rsi_val:.1f})**：🔴 **過熱 (超買區)** - 注意回調風險")
        elif rsi_val < 30:
            st.markdown(f"**RSI ({rsi_val:.1f})**：🟢 **過冷 (超賣區)** - 醞釀反彈機會")
        else:
            st.markdown(f"**RSI ({rsi_val:.1f})**：⚪ **中性區域** - 順勢操作")

        # 3. MACD 判讀
        macd_hist = last['MACD_Hist']
        prev_hist = prev['MACD_Hist']
        
        if macd_hist > 0 and macd_hist > prev_hist:
            st.markdown("**MACD**：🟢 **多頭增強** (紅柱變長)")
        elif macd_hist > 0 and macd_hist < prev_hist:
            st.markdown("**MACD**：🟡 **多頭減弱** (紅柱縮短)")
        elif macd_hist < 0 and macd_hist < prev_hist:
            st.markdown("**MACD**：🔴 **空頭增強** (綠柱變長)")
        else:
            st.markdown("**MACD**：🟠 **空頭減弱** (綠柱縮短)")

        st.divider()

        # --- C. 視覺化圖表 (4視窗) ---
        st.subheader("📈 戰情儀表板")
        
        # 建立 4 個子圖
        fig = make_subplots(
            rows=4, cols=1, 
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.5, 0.15, 0.15, 0.2],
            subplot_titles=("價格與均線", "成交量", "RSI 強弱指標", "MACD 趨勢指標")
        )

        # 1. K線圖
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
            name='K線'
        ), row=1, col=1)
        
        # 繪製策略均線
        fig.add_trace(go.Scatter(x=df.index, y=df['Buy_Fast'], line=dict(color='orange', width=1), name=f'快線 {b_f}'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Sell_Slow'], line=dict(color='purple', width=1), name=f'慢線 {s_s}'), row=1, col=1)

        # 2. 成交量
        colors = ['red' if o > c else 'green' for o, c in zip(df['Open'], df['Close'])]
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='成交量'), row=2, col=1)

        # 3. RSI
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='#9C27B0', width=2), name='RSI'), row=3, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

        # 4. MACD
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD_Line'], line=dict(color='#2196F3', width=1), name='MACD'), row=4, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD_Signal'], line=dict(color='#FF5722', width=1), name='Signal'), row=4, col=1)
        hist_colors = ['red' if h < 0 else 'green' for h in df['MACD_Hist']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], marker_color=hist_colors, name='Hist'), row=4, col=1)

        # 版面設定
        fig.update_layout(
            height=900, 
            xaxis_rangeslider_visible=False,
            showlegend=False,
            margin=dict(l=10, r=10, t=30, b=10)
        )
        
        st.plotly_chart(fig, use_container_width=True)