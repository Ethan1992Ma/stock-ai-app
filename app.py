import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from ta.trend import SMAIndicator, MACD
from ta.momentum import RSIIndicator

# --- 1. 網頁設定 ---
st.set_page_config(page_title="AI 全能操盤戰情室", layout="wide", initial_sidebar_state="collapsed")

# --- 2. CSS 美化 (卡片與版面) ---
st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    
    /* 資訊卡片樣式 */
    .metric-card {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.08);
        margin-bottom: 10px;
        border: 1px solid #e9ecef;
    }
    .metric-title { color: #6c757d; font-size: 0.85rem; font-weight: 700; letter-spacing: 0.5px; }
    .metric-value { font-size: 1.4rem; font-weight: 800; color: #212529; margin: 5px 0; }
    .metric-sub { font-size: 0.85rem; color: #495057; }
    
    /* 狀態標籤 */
    .status-badge { padding: 3px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; color: white; display: inline-block; margin-top: 5px; }
    .bg-red { background-color: #ff4b4b; }
    .bg-green { background-color: #21c354; }
    .bg-gray { background-color: #adb5bd; }
    .bg-blue { background-color: #0d6efd; }
    .bg-orange { background-color: #fd7e14; }

    /* 手機圖表優化 */
    .js-plotly-plot .plotly .modebar { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. 數據處理 (快取) ---
@st.cache_data(ttl=300)
def get_stock_data(ticker):
    stock = yf.Ticker(ticker)
    # 固定抓取 2 年資料
    df = stock.history(period="2y")
    info = stock.info
    return df, info

# --- 4. 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 參數設定")
    ticker_input = st.text_input("股票代號", "TSLA").upper()
    st.markdown("---")
    ma_short = st.number_input("短線 MA", value=5)
    ma_long = st.number_input("長線 MA", value=20)
    vol_ma_len = st.number_input("均量天數", value=20)

# --- 5. 主程式邏輯 ---
if ticker_input:
    try:
        # 1. 抓資料
        df, info = get_stock_data(ticker_input)
        
        if not df.empty and len(df) > 60:
            # 2. 計算指標
            # MA
            df['MA_S'] = SMAIndicator(df['Close'], window=ma_short).sma_indicator()
            df['MA_L'] = SMAIndicator(df['Close'], window=ma_long).sma_indicator()
            df['MA_60'] = SMAIndicator(df['Close'], window=60).sma_indicator() # 生命線
            
            # RSI & MACD
            df['RSI'] = RSIIndicator(df['Close'], window=14).rsi()
            macd = MACD(df['Close'])
            df['MACD'] = macd.macd()
            df['Signal'] = macd.macd_signal()
            df['Hist'] = macd.macd_diff()
            
            # 成交量
            df['Vol_MA'] = SMAIndicator(df['Volume'], window=vol_ma_len).sma_indicator()

            # 最新數據
            last = df.iloc[-1]
            prev = df.iloc[-2]
            change = last['Close'] - prev['Close']
            pct_change = (change / prev['Close']) * 100
            price_color = "#ff4b4b" if change > 0 else "#21c354"
            
            # --- 版面開始 ---
            st.markdown(f"### 📱 {info.get('longName', ticker_input)} ({ticker_input})")
            
            # 【區塊 A】基本面數據 (P/E, EPS, 市值)
            col_b1, col_b2, col_b3, col_b4 = st.columns(4)
            with col_b1:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">最新股價</div>
                    <div class="metric-value" style="color:{price_color}">{last['Close']:.2f}</div>
                    <div class="metric-sub">{('+' if change > 0 else '')}{change:.2f} ({pct_change:.2f}%)</div>
                </div>""", unsafe_allow_html=True)
            
            with col_b2:
                pe = info.get('trailingPE', 'N/A')
                pe_val = f"{pe:.1f}" if isinstance(pe, (int, float)) else "N/A"
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">本益比 (P/E)</div>
                    <div class="metric-value">{pe_val}</div>
                    <div class="metric-sub">估值參考</div>
                </div>""", unsafe_allow_html=True)
                
            with col_b3:
                eps = info.get('trailingEps', 'N/A')
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">每股盈餘 (EPS)</div>
                    <div class="metric-value">{eps}</div>
                    <div class="metric-sub">獲利能力</div>
                </div>""", unsafe_allow_html=True)

            with col_b4:
                mcap = info.get('marketCap', 0)
                mcap_str = f"{mcap/1000000000:.1f}B" if mcap > 1000000000 else f"{mcap/1000000:.1f}M"
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">總市值</div>
                    <div class="metric-value">{mcap_str}</div>
                    <div class="metric-sub">{info.get('sector', 'N/A')}</div>
                </div>""", unsafe_allow_html=True)

            # 【區塊 B】AI 技術分析卡片 (你指定的 4 大分析)
            st.markdown("#### 🤖 AI 趨勢解讀")
            c1, c2, c3, c4 = st.columns(4)
            
            # 1. 均線分析
            trend_msg = "盤整 / 空頭"
            trend_bg = "bg-gray"
            if last['Close'] > last['MA_S'] > last['MA_L']:
                trend_msg = "多頭排列 📈"
                trend_bg = "bg-red"
            elif last['Close'] < last['MA_S'] < last['MA_L']:
                trend_msg = "空頭排列 📉"
                trend_bg = "bg-green"
                
            with c1:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">均線趨勢</div>
                    <div class="metric-value" style="font-size:1.1rem; margin:10px 0;">{trend_msg}</div>
                    <div><span class="status-badge {trend_bg}">MA{ma_short} vs MA{ma_long}</span></div>
                    <div class="metric-sub" style="margin-top:5px;">站上60日線: {"是" if last['Close']>last['MA_60'] else "否"}</div>
                </div>""", unsafe_allow_html=True)

            # 2. 量能分析 (RVol)
            vol_ratio = last['Volume'] / last['Vol_MA'] if last['Vol_MA'] > 0 else 0
            vol_msg = "量縮觀望 💤"
            vol_bg = "bg-gray"
            if vol_ratio > 1.5:
                vol_msg = "爆量攻擊 🔥"
                vol_bg = "bg-red"
            elif vol_ratio > 1.0:
                vol_msg = "溫和放量 💧"
                vol_bg = "bg-blue"
                
            with c2:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">量能分析 (RVol)</div>
                    <div class="metric-value" style="font-size:1.1rem; margin:10px 0;">{vol_msg}</div>
                    <div><span class="status-badge {vol_bg}">{vol_ratio:.1f} 倍均量</span></div>
                    <div class="metric-sub" style="margin-top:5px;">今日vs20日均量</div>
                </div>""", unsafe_allow_html=True)

            # 3. MACD 分析
            macd_msg = "空方控盤 🐻"
            macd_bg = "bg-green"
            if last['Hist'] > 0:
                macd_msg = "多方控盤 🐂"
                macd_bg = "bg-red"
            
            macd_strength = "動能增強 ↗" if abs(last['Hist']) > abs(prev['Hist']) else "動能減弱 ↘"

            with c3:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">MACD 籌碼</div>
                    <div class="metric-value" style="font-size:1.1rem; margin:10px 0;">{macd_msg}</div>
                    <div><span class="status-badge {macd_bg}">{macd_strength}</span></div>
                    <div class="metric-sub" style="margin-top:5px;">柱狀圖方向判讀</div>
                </div>""", unsafe_allow_html=True)

            # 4. RSI 分析
            rsi_val = last['RSI']
            rsi_msg = "中性區域 ⚖️"
            rsi_bg = "bg-gray"
            if rsi_val > 70: 
                rsi_msg = "過熱警戒 🔴"
                rsi_bg = "bg-red"
            elif rsi_val < 30: 
                rsi_msg = "超賣區 🟢"
                rsi_bg = "bg-green"
                
            with c4:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">RSI 強弱</div>
                    <div class="metric-value" style="font-size:1.1rem; margin:10px 0;">{rsi_msg}</div>
                    <div><span class="status-badge {rsi_bg}">數值: {rsi_val:.1f}</span></div>
                    <div class="metric-sub" style="margin-top:5px;">乖離率參考</div>
                </div>""", unsafe_allow_html=True)

            # 【區塊 C】完整圖表 (2年日線)
            st.markdown("#### 📉 技術分析圖表 (2年日線)")
            
            fig = make_subplots(
                rows=4, cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.03, 
                row_heights=[0.5, 0.15, 0.15, 0.2],
                subplot_titles=("價格 & 均線", "成交量", "RSI", "MACD")
            )

            # 1. K線 + MA
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA_S'], line=dict(color='orange', width=1), name=f'MA{ma_short}'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA_L'], line=dict(color='purple', width=1), name=f'MA{ma_long}'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA_60'], line=dict(color='blue', width=1, dash='dot'), name='MA60'), row=1, col=1)

            # 2. 成交量
            colors = ['red' if o > c else 'green' for o, c in zip(df['Open'], df['Close'])]
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='成交量'), row=2, col=1)

            # 3. RSI
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='#9C27B0', width=2), name='RSI'), row=3, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

            # 4. MACD
            fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='#2196F3', width=1), name='MACD'), row=4, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['Signal'], line=dict(color='#FF5722', width=1), name='Signal'), row=4, col=1)
            fig.add_trace(go.Bar(x=df.index, y=df['Hist'], marker_color=['red' if h < 0 else 'green' for h in df['Hist']], name='Hist'), row=4, col=1)

            fig.update_layout(
                height=1000, # 高度增加，確保2年資料顯示清晰
                margin=dict(l=10, r=10, t=20, b=10),
                xaxis_rangeslider_visible=False,
                showlegend=False,
                dragmode=False
            )
            fig.update_xaxes(fixedrange=True)
            fig.update_yaxes(fixedrange=True)

            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        else:
            st.error("無法取得足夠資料，請檢查股票代號。")
    except Exception as e:
        st.error(f"發生錯誤: {e}")
