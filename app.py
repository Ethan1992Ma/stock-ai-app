import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from ta.trend import SMAIndicator, MACD
from ta.momentum import RSIIndicator

# --- 1. 網頁設定 ---
st.set_page_config(page_title="AI 智能操盤戰情室", layout="wide", initial_sidebar_state="collapsed")

# --- 2. CSS 美化 (卡片式設計核心) ---
st.markdown("""
    <style>
    /* 全局背景微調 */
    .stApp {
        background-color: #f8f9fa;
    }
    
    /* 卡片樣式定義 */
    .metric-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    .metric-title {
        color: #6c757d;
        font-size: 0.9rem;
        font-weight: 600;
        margin-bottom: 5px;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: bold;
        color: #212529;
    }
    .metric-delta {
        font-size: 1rem;
        margin-left: 5px;
    }
    .metric-text {
        color: #495057;
        font-size: 0.9rem;
        margin-top: 10px;
    }
    
    /* 狀態標籤顏色 */
    .status-badge {
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: bold;
        color: white;
    }
    .bg-red { background-color: #ff4b4b; }
    .bg-green { background-color: #21c354; }
    .bg-gray { background-color: #6c757d; }
    .bg-blue { background-color: #007bff; }
    
    /* 隱藏 Plotly 工具列 */
    .js-plotly-plot .plotly .modebar {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. 數據快取與邏輯 ---
@st.cache_data(ttl=300) # 5分鐘快取
def get_data(ticker):
    stock = yf.Ticker(ticker)
    df = stock.history(period="1y")
    return df

# 輔助函式：判斷趨勢
def check_trend(val, ma_val):
    return "📈 多頭排列" if val > ma_val else "📉 空頭排列"

# --- 4. 側邊欄設定 ---
with st.sidebar:
    st.header("⚙️ 設定參數")
    ticker = st.text_input("股票代號", "TSLA").upper()
    st.markdown("---")
    ma_short = st.number_input("短線 MA", value=5)
    ma_long = st.number_input("長線 MA", value=20)
    ma_trend = st.number_input("趨勢線 (生命線)", value=60)

# --- 5. 主程式 ---
st.markdown(f"## 📊 {ticker} AI 智能戰情室")

if ticker:
    try:
        df = get_data(ticker)
        
        if not df.empty:
            # --- 計算指標 ---
            # MA
            df['MA_S'] = SMAIndicator(df['Close'], window=ma_short).sma_indicator()
            df['MA_L'] = SMAIndicator(df['Close'], window=ma_long).sma_indicator()
            df['MA_T'] = SMAIndicator(df['Close'], window=ma_trend).sma_indicator()
            
            # RSI
            df['RSI'] = RSIIndicator(df['Close'], window=14).rsi()
            
            # MACD
            macd = MACD(df['Close'])
            df['MACD'] = macd.macd()
            df['Signal'] = macd.macd_signal()
            df['Hist'] = macd.macd_diff()
            
            # 成交量均量
            df['Vol_MA'] = SMAIndicator(df['Volume'], window=20).sma_indicator()
            
            # 取最新一筆資料
            last = df.iloc[-1]
            prev = df.iloc[-2]
            
            # 計算漲跌
            change = last['Close'] - prev['Close']
            pct_change = (change / prev['Close']) * 100
            color_price = "#ff4b4b" if change > 0 else "#21c354" # 台股紅漲綠跌邏輯
            
            # --- A. 第一排：核心報價與成交量熱力 (還原卡片設計) ---
            col1, col2 = st.columns(2)
            
            # 價格卡片
            with col1:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">目前股價 (PRICE)</div>
                    <div class="metric-value" style="color: {color_price};">
                        {last['Close']:.2f}
                        <span class="metric-delta">
                            {('+' if change > 0 else '')}{change:.2f} ({pct_change:.2f}%)
                        </span>
                    </div>
                    <div class="metric-text">資料日期: {last.name.strftime('%Y-%m-%d')}</div>
                </div>
                """, unsafe_allow_html=True)

            # RVol 成交量分析卡片
            rvol = last['Volume'] / last['Vol_MA'] if last['Vol_MA'] > 0 else 1
            vol_status = "💧 量縮觀望"
            vol_color = "bg-gray"
            if rvol > 1.5:
                vol_status = "🔥 爆量攻擊"
                vol_color = "bg-red"
            elif rvol > 1.0:
                vol_status = "💧 溫和放量"
                vol_color = "bg-blue"
            
            with col2:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">成交量熱力分析 (RVol)</div>
                    <div class="metric-value">
                        {rvol:.1f} <span style="font-size:1rem; color:#888;">倍均量</span>
                    </div>
                    <div style="margin-top:10px;">
                        <span class="status-badge {vol_color}">{vol_status}</span>
                    </div>
                    <div class="metric-text">今日量能是20日均量的 {rvol:.2f} 倍</div>
                </div>
                """, unsafe_allow_html=True)

            # --- B. 第二排：AI 綜合判讀 (白話文解讀) ---
            col3, col4, col5 = st.columns(3)
            
            # 1. 均線狀態
            trend_short = "多方" if last['Close'] > last['MA_S'] else "空方"
            trend_long = "多頭格局" if last['MA_S'] > last['MA_L'] else "整理/空頭"
            
            with col3:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">📊 均線排列狀態</div>
                    <div class="metric-text">
                        <b>短線：</b> {trend_short}控盤 <br>
                        <b>長線：</b> {trend_long} <br>
                        <hr style="margin:5px 0;">
                        <span style="font-size:0.8rem; color:#666;">MA{ma_short} vs MA{ma_long}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            # 2. RSI 解讀
            rsi_val = last['RSI']
            rsi_msg = "⚪ 中性區域"
            if rsi_val > 70: rsi_msg = "🔴 過熱 (超買)"
            elif rsi_val < 30: rsi_msg = "🟢 過冷 (超賣)"
            
            with col4:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">⚡ RSI 相對強弱指標 ({rsi_val:.1f})</div>
                    <div class="metric-value" style="font-size:1.4rem;">{rsi_msg}</div>
                    <div class="metric-text">判斷是否過度追高或殺低</div>
                </div>
                """, unsafe_allow_html=True)
                
            # 3. MACD 解讀
            macd_msg = "🟢 多方掌控" if last['Hist'] > 0 else "🔴 空方掌控"
            macd_trend = "增強 ↗" if last['Hist'] > prev['Hist'] else "減弱 ↘"
            
            with col5:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">🌊 MACD 趨勢指標</div>
                    <div class="metric-value" style="font-size:1.4rem;">{macd_msg}</div>
                    <div class="metric-text">動能：{macd_trend}</div>
                </div>
                """, unsafe_allow_html=True)

            # --- C. 視覺化圖表 (整合版) ---
            st.subheader("📉 綜合戰情走勢圖")
            
            # 使用 Subplots 但優化比例
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                vertical_spacing=0.03, row_heights=[0.7, 0.3],
                                specs=[[{"secondary_y": True}], [{}]])

            # 主圖：K線 + 均線
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'],
                                         low=df['Low'], close=df['Close'], name='K線'), row=1, col=1)
            
            fig.add_trace(go.Scatter(x=df.index, y=df['MA_S'], line=dict(color='orange', width=1), name=f'MA{ma_short}'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA_L'], line=dict(color='purple', width=1), name=f'MA{ma_long}'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA_T'], line=dict(color='blue', width=1, dash='dot'), name=f'MA{ma_trend}'), row=1, col=1)

            # 副圖：成交量 + MACD (技巧性疊合或分開) -> 這裡依你需求保留成交量
            colors_vol = ['red' if o > c else 'green' for o, c in zip(df['Open'], df['Close'])]
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors_vol, name='成交量'), row=2, col=1)

            # 佈局設定
            fig.update_layout(
                height=600, # 高度適中，適合手機
                margin=dict(l=10, r=10, t=30, b=10),
                xaxis_rangeslider_visible=False,
                dragmode=False, # 鎖定防誤觸
                legend=dict(orientation="h", y=1, x=0, bgcolor='rgba(255,255,255,0.5)')
            )
            fig.update_xaxes(fixedrange=True)
            fig.update_yaxes(fixedrange=True)

            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    except Exception as e:
        st.error(f"發生錯誤: {e}")
else:
    st.info("請在左側輸入股票代號")