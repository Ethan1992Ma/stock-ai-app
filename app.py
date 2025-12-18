import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from ta.trend import SMAIndicator, MACD
from ta.momentum import RSIIndicator

# --- 1. 網頁設定 ---
st.set_page_config(page_title="AI 智能操盤戰情室", layout="wide", initial_sidebar_state="collapsed")

# --- 2. CSS 美化 ---
st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    .metric-card {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        margin-bottom: 10px;
    }
    .metric-title { color: #6c757d; font-size: 0.85rem; font-weight: 600; }
    .metric-value { font-size: 1.5rem; font-weight: bold; color: #212529; }
    .status-badge { padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; color: white; }
    .bg-red { background-color: #ff4b4b; }
    .bg-green { background-color: #21c354; }
    .bg-gray { background-color: #6c757d; }
    .bg-blue { background-color: #007bff; }
    /* 隱藏 Plotly 工具列 */
    .js-plotly-plot .plotly .modebar { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. 數據處理 ---
@st.cache_data(ttl=300)
def get_data(ticker, period):
    stock = yf.Ticker(ticker)
    # yfinance 的 period 選項: 1mo, 3mo, 6mo, 1y, 2y, 5y, ytd, max
    df = stock.history(period=period)
    return df

# --- 4. 側邊欄 (保留進階設定) ---
with st.sidebar:
    st.header("⚙️ 設定參數")
    ticker_input = st.text_input("股票代號", "ONDS").upper()
    st.markdown("---")
    ma_short = st.number_input("短線 MA", value=5)
    ma_long = st.number_input("長線 MA", value=20)

# --- 5. 主程式 ---
# 標題區 + 時間切換
col_title, col_period = st.columns([2, 2])
with col_title:
    st.markdown(f"## 📊 {ticker_input} 戰情室")

with col_period:
    # 優化：直接在首頁切換時間週期
    period = st.radio("時間區間", ["1mo", "3mo", "6mo", "1y"], index=2, horizontal=True, format_func=lambda x: {"1mo":"1月", "3mo":"1季", "6mo":"半年", "1y":"1年"}[x])

if ticker_input:
    try:
        df = get_data(ticker_input, period)
        
        if not df.empty and len(df) > 20:
            # --- 指標計算 ---
            df['MA_S'] = SMAIndicator(df['Close'], window=ma_short).sma_indicator()
            df['MA_L'] = SMAIndicator(df['Close'], window=ma_long).sma_indicator()
            df['RSI'] = RSIIndicator(df['Close'], window=14).rsi()
            macd = MACD(df['Close'])
            df['MACD'] = macd.macd()
            df['Signal'] = macd.macd_signal()
            df['Hist'] = macd.macd_diff()
            df['Vol_MA'] = SMAIndicator(df['Volume'], window=20).sma_indicator()

            last = df.iloc[-1]
            prev = df.iloc[-2]
            change = last['Close'] - prev['Close']
            pct_change = (change / prev['Close']) * 100
            price_color = "#ff4b4b" if change > 0 else "#21c354"

            # --- A. 卡片區 (Card UI) ---
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">最新股價</div>
                    <div class="metric-value" style="color: {price_color};">
                        {last['Close']:.2f} 
                        <span style="font-size:1rem;">{('+' if change > 0 else '')}{pct_change:.2f}%</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            with c2:
                # 簡單判斷 RSI
                rsi_val = last['RSI']
                rsi_status = "中性"
                rsi_bg = "bg-gray"
                if rsi_val > 70: rsi_status, rsi_bg = "過熱", "bg-red"
                elif rsi_val < 30: rsi_status, rsi_bg = "超賣", "bg-green"
                
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">RSI 強弱指標</div>
                    <div class="metric-value">{rsi_val:.1f}</div>
                    <div><span class="status-badge {rsi_bg}">{rsi_status}</span></div>
                </div>
                """, unsafe_allow_html=True)

            # --- B. 綜合圖表區 (修復 RSI/MACD 消失的問題) ---
            st.subheader("📉 技術分析圖表")
            
            # 建立 4 列圖表：價格、成交量、RSI、MACD
            fig = make_subplots(
                rows=4, cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.02, 
                row_heights=[0.5, 0.15, 0.15, 0.2], # 分配高度
                subplot_titles=("價格 & 均線", "成交量", "RSI", "MACD")
            )

            # 1. 主圖 (K線 + MA)
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA_S'], line=dict(color='orange', width=1), name=f'MA{ma_short}'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA_L'], line=dict(color='purple', width=1), name=f'MA{ma_long}'), row=1, col=1)

            # 2. 成交量
            colors = ['red' if o > c else 'green' for o, c in zip(df['Open'], df['Close'])]
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='成交量'), row=2, col=1)

            # 3. RSI (補回來的)
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='#9C27B0', width=2), name='RSI'), row=3, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

            # 4. MACD (補回來的)
            fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='#2196F3', width=1), name='MACD'), row=4, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['Signal'], line=dict(color='#FF5722', width=1), name='Signal'), row=4, col=1)
            fig.add_trace(go.Bar(x=df.index, y=df['Hist'], marker_color=['red' if h < 0 else 'green' for h in df['Hist']], name='Hist'), row=4, col=1)

            # 手機優化設定
            fig.update_layout(
                height=900, # 拉長高度，讓4個圖都不會擠
                margin=dict(l=10, r=10, t=30, b=10),
                xaxis_rangeslider_visible=False,
                showlegend=False,
                dragmode=False # 鎖定防誤觸
            )
            fig.update_xaxes(fixedrange=True)
            fig.update_yaxes(fixedrange=True)

            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        else:
            st.warning("資料不足或無法取得，請稍後再試。")
    except Exception as e:
        st.error(f"發生錯誤: {e}")