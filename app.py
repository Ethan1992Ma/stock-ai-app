import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from ta.trend import SMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands # 新增布林通道

# --- 網頁設定 ---
st.set_page_config(page_title="AI 智能操盤手 Pro", layout="wide", initial_sidebar_state="expanded")

# --- CSS 優化 ---
st.markdown("""
    <style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 10px;
    }
    /* 手機優化：隱藏 Plotly 工具列 */
    .js-plotly-plot .plotly .modebar {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📱 AI 智能操盤手 Pro")

# --- 1. 快取優化：下載資料不重複跑 (Speed Boost) ---
@st.cache_data(ttl=3600) # 設定快取 1 小時，避免重複下載
def get_stock_data(ticker_symbol):
    try:
        stock = yf.Ticker(ticker_symbol)
        # 取得歷史資料
        df = stock.history(period="1y") 
        # 取得基本面資料
        info = stock.info
        return df, info, None
    except Exception as e:
        return None, None, str(e)

# --- 側邊欄 ---
st.sidebar.header("🔍 設定")

# 優化輸入體驗：加上常用清單
ticker_list = ["TSLA", "NVDA", "AAPL", "AMD", "ONDS", "2330.TW", "0050.TW"]
ticker = st.sidebar.selectbox("選擇或輸入代碼", ticker_list, index=0)
# 允許手動輸入 (若不在清單內)
manual_ticker = st.sidebar.text_input("或手動輸入其他代碼", "").upper()
if manual_ticker:
    ticker = manual_ticker

st.sidebar.markdown("---")
st.sidebar.header("⚙️ 參數")
strategy_mode = st.sidebar.radio("策略模式", ("🤖 自動判別", "🛠️ 手動設定"))

# 參數設定邏輯 (保持原樣)
buy_fast, buy_slow = 5, 10
sell_fast, sell_slow = 20, 60
strategy_name = "預設"

if strategy_mode == "🤖 自動判別":
    # 這裡簡化邏輯，直接用文字顯示，實際參數在下方應用
    pass 
else:
    buy_fast = st.sidebar.number_input("買進快線", 5)
    buy_slow = st.sidebar.number_input("買進慢線", 10)
    sell_fast = st.sidebar.number_input("賣出快線", 20)
    sell_slow = st.sidebar.number_input("賣出慢線", 60)

# --- 核心計算與繪圖 ---
if st.button("🚀 開始分析", type="primary", use_container_width=True):
    with st.spinner('AI 正在加速運算中...'):
        # 1. 呼叫快取函數下載資料
        df, info, err = get_stock_data(ticker)

        if err or df.empty:
            st.error(f"找不到資料或代號錯誤: {err}")
        else:
            # --- 策略自動判別邏輯應用 ---
            market_cap = info.get('marketCap', 0)
            if strategy_mode == "🤖 自動判別":
                if market_cap > 200_000_000_000:
                    strategy_name = "🐘 巨頭穩健策略"
                    buy_fast, buy_slow = 10, 20
                    sell_fast, sell_slow = 20, 60
                else:
                    strategy_name = "🚀 小型妖股策略"
                    buy_fast, buy_slow = 3, 8
                    sell_fast, sell_slow = 5, 20
            else:
                strategy_name = "🛠️ 手動設定"

            # --- 技術指標計算 ---
            # MA
            df['Buy_Fast'] = SMAIndicator(close=df['Close'], window=buy_fast).sma_indicator()
            df['Sell_Slow'] = SMAIndicator(close=df['Close'], window=sell_slow).sma_indicator()
            
            # 布林通道 (新功能!)
            indicator_bb = BollingerBands(close=df["Close"], window=20, window_dev=2)
            df['BB_High'] = indicator_bb.bollinger_hband()
            df['BB_Low'] = indicator_bb.bollinger_lband()

            # RSI & MACD
            df['RSI'] = RSIIndicator(close=df['Close'], window=14).rsi()
            macd = MACD(close=df['Close'])
            df['MACD_Line'] = macd.macd()
            df['MACD_Signal'] = macd.macd_signal()
            df['MACD_Hist'] = macd.macd_diff()

            # --- 顯示區塊 ---
            
            # A. 資訊卡片 (新增基本面數據)
            last_close = df['Close'].iloc[-1]
            prev_close = df['Close'].iloc[-2]
            change = last_close - prev_close
            pct_change = (change / prev_close) * 100
            
            st.subheader(f"{info.get('longName', ticker)}")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("收盤價", f"{last_close:.2f}", f"{pct_change:.2f}%")
            
            # 基本面數據 (容錯處理，怕有些股票沒資料)
            pe_ratio = info.get('trailingPE', 'N/A')
            eps = info.get('trailingEps', 'N/A')
            high_52 = info.get('fiftyTwoWeekHigh', 0)
            
            # 格式化顯示
            pe_str = f"{pe_ratio:.1f}" if isinstance(pe_ratio, (int, float)) else "N/A"
            col2.metric("本益比 (P/E)", pe_str)
            col3.metric("EPS", eps)
            
            # 離52週高點還有多遠
            if isinstance(high_52, (int, float)) and high_52 > 0:
                dist_high = ((last_close - high_52) / high_52) * 100
                col4.metric("距52週高", f"{high_52}", f"{dist_high:.1f}%")
            else:
                col4.metric("52週高", "N/A")

            st.caption(f"策略：{strategy_name} | 市值：{market_cap/1000000000:.2f}B")
            st.divider()

            # B. 圖表 (加入布林通道)
            fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03, 
                                row_heights=[0.5, 0.15, 0.15, 0.2],
                                subplot_titles=("價格 & 布林通道", "成交量", "RSI", "MACD"))

            # K線
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線'), row=1, col=1)
            
            # 布林通道 (淺灰色背景)
            fig.add_trace(go.Scatter(x=df.index, y=df['BB_High'], line=dict(color='rgba(200,200,200,0.5)', width=1), name='布林上軌'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['BB_Low'], line=dict(color='rgba(200,200,200,0.5)', width=1), name='布林下軌', fill='tonexty', fillcolor='rgba(200,200,200,0.1)'), row=1, col=1)

            # 均線
            fig.add_trace(go.Scatter(x=df.index, y=df['Buy_Fast'], line=dict(color='orange', width=1), name='快線'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['Sell_Slow'], line=dict(color='purple', width=1), name='慢線'), row=1, col=1)

            # 其他指標
            colors = ['red' if o > c else 'green' for o, c in zip(df['Open'], df['Close'])]
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='量'), row=2, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='#9C27B0', width=2), name='RSI'), row=3, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)
            
            fig.add_trace(go.Scatter(x=df.index, y=df['MACD_Line'], line=dict(color='#2196F3', width=1), name='MACD'), row=4, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MACD_Signal'], line=dict(color='#FF5722', width=1), name='Signal'), row=4, col=1)
            fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], marker_color=['red' if h < 0 else 'green' for h in df['MACD_Hist']], name='Hist'), row=4, col=1)

            # 鎖定圖表防誤觸
            fig.update_layout(height=900, xaxis_rangeslider_visible=False, showlegend=False, margin=dict(l=10, r=10, t=10, b=10), dragmode=False)
            fig.update_xaxes(fixedrange=True)
            fig.update_yaxes(fixedrange=True)

            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': False})