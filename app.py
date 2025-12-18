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
    
    /* 通用卡片樣式 */
    .metric-card {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        margin-bottom: 10px;
        border: 1px solid #e9ecef;
    }
    .metric-title { color: #6c757d; font-size: 0.85rem; font-weight: 700; letter-spacing: 0.5px; }
    .metric-value { font-size: 1.4rem; font-weight: 800; color: #212529; margin: 5px 0; }
    .metric-sub { font-size: 0.8rem; color: #adb5bd; }
    
    /* 均線監控專用樣式 (Flexbox) */
    .ma-container {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        justify-content: space-between;
        background-color: #ffffff;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        border: 1px solid #e9ecef;
        margin-top: 5px;
        margin-bottom: 20px;
    }
    .ma-box {
        flex: 1 1 80px; /* 最小寬度80px，自動伸縮 */
        text-align: center;
        padding: 8px;
        background-color: #f8f9fa;
        border-radius: 8px;
        border: 1px solid #dee2e6;
    }
    .ma-label { font-size: 0.8rem; font-weight: bold; color: #495057; margin-bottom: 4px; }
    .ma-val { font-size: 1rem; font-weight: 800; }
    .txt-up { color: #ff4b4b; }
    .txt-down { color: #21c354; }

    /* 狀態標籤 */
    .status-badge { padding: 3px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; color: white; display: inline-block; margin-top: 5px; }
    .bg-red { background-color: #ff4b4b; }
    .bg-green { background-color: #21c354; }
    .bg-gray { background-color: #adb5bd; }
    .bg-blue { background-color: #0d6efd; }

    /* Plotly 優化 */
    .js-plotly-plot .plotly .modebar { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. 數據處理 ---
@st.cache_data(ttl=300)
def get_stock_data(ticker):
    stock = yf.Ticker(ticker)
    # 抓取 2 年資料
    df = stock.history(period="2y")
    info = stock.info
    return df, info

# --- 4. 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 參數設定")
    ticker_input = st.text_input("股票代號", "TSLA").upper()
    st.markdown("---")
    
    st.subheader("🧠 策略邏輯")
    strategy_mode = st.radio("判讀模式", ["🤖 自動判別 (Auto)", "🛠️ 手動設定 (Manual)"])
    
    strat_fast, strat_slow = 5, 20
    strat_desc = "預設"

    if strategy_mode == "🛠️ 手動設定 (Manual)":
        strat_fast = st.number_input("策略快線 (Fast)", value=5)
        strat_slow = st.number_input("策略慢線 (Slow)", value=20)
        strat_desc = "自訂策略"

# --- 5. 主程式 ---
if ticker_input:
    try:
        # 1. 抓資料
        df, info = get_stock_data(ticker_input)
        
        if not df.empty and len(df) > 200:
            # --- 自動策略 ---
            if strategy_mode == "🤖 自動判別 (Auto)":
                mcap = info.get('marketCap', 0)
                if mcap > 200_000_000_000:
                    strat_fast, strat_slow = 10, 20
                    strat_desc = "🐘 巨頭穩健"
                else:
                    strat_fast, strat_slow = 5, 10
                    strat_desc = "🚀 小型飆股"
            
            # 2. 計算指標
            # 均線列表
            ma_list = [5, 10, 20, 30, 60, 120, 200]
            for d in ma_list:
                df[f'MA_{d}'] = SMAIndicator(df['Close'], window=d).sma_indicator()
            
            # 策略判讀均線
            strat_fast_val = SMAIndicator(df['Close'], window=strat_fast).sma_indicator().iloc[-1]
            strat_slow_val = SMAIndicator(df['Close'], window=strat_slow).sma_indicator().iloc[-1]
            
            # 其他
            df['RSI'] = RSIIndicator(df['Close'], window=14).rsi()
            macd = MACD(df['Close'])
            df['MACD'] = macd.macd()
            df['Signal'] = macd.macd_signal()
            df['Hist'] = macd.macd_diff()
            df['Vol_MA'] = SMAIndicator(df['Volume'], window=20).sma_indicator()

            # 最新數據
            last = df.iloc[-1]
            prev = df.iloc[-2]
            change = last['Close'] - prev['Close']
            pct_change = (change / prev['Close']) * 100
            price_color = "#ff4b4b" if change > 0 else "#21c354"
            
            # --- 版面顯示 ---
            st.markdown(f"### 📱 {info.get('longName', ticker_input)} ({ticker_input})")
            st.caption(f"目前策略：{strat_desc} (判讀依據 MA{strat_fast} vs MA{strat_slow})")

            # 【區塊 A】基本面與價格
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">最新股價</div>
                    <div class="metric-value" style="color:{price_color}">{last['Close']:.2f}</div>
                    <div class="metric-sub">{('+' if change > 0 else '')}{change:.2f} ({pct_change:.2f}%)</div>
                </div>""", unsafe_allow_html=True)
            with c2:
                pe = info.get('trailingPE', 'N/A')
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">本益比 (P/E)</div>
                    <div class="metric-value">{pe if isinstance(pe, str) else f"{pe:.1f}"}</div>
                    <div class="metric-sub">估值參考</div>
                </div>""", unsafe_allow_html=True)
            with c3:
                eps = info.get('trailingEps', 'N/A')
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">EPS</div>
                    <div class="metric-value">{eps}</div>
                    <div class="metric-sub">獲利能力</div>
                </div>""", unsafe_allow_html=True)
            with c4:
                mcap = info.get('marketCap', 0)
                m_str = f"{mcap/1000000000:.1f}B" if mcap > 1000000000 else f"{mcap/1000000:.1f}M"
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">市值</div>
                    <div class="metric-value">{m_str}</div>
                    <div class="metric-sub">{info.get('sector','N/A')}</div>
                </div>""", unsafe_allow_html=True)

            # 【區塊 B】AI 訊號卡片 (移除多餘文字)
            st.markdown("#### 🤖 策略訊號解讀")
            k1, k2, k3, k4 = st.columns(4)
            
            # 1. 趨勢
            trend_msg = "盤整 / 觀望"
            trend_bg = "bg-gray"
            if last['Close'] > strat_fast_val > strat_slow_val:
                trend_msg = "多頭趨勢 📈"
                trend_bg = "bg-red"
            elif last['Close'] < strat_fast_val < strat_slow_val:
                trend_msg = "空頭趨勢 📉"
                trend_bg = "bg-green"
            
            with k1:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">趨勢訊號</div>
                    <div class="metric-value" style="font-size:1.1rem; margin:10px 0;">{trend_msg}</div>
                    <div><span class="status-badge {trend_bg}">MA{strat_fast} vs MA{strat_slow}</span></div>
                </div>""", unsafe_allow_html=True)
            
            # 2. 量能
            vol_r = last['Volume'] / last['Vol_MA'] if last['Vol_MA'] > 0 else 0
            v_msg = "量縮觀望"
            v_bg = "bg-gray"
            if vol_r > 1.5: 
                v_msg = "爆量攻擊"
                v_bg = "bg-red"
            elif vol_r > 1.0:
                v_msg = "溫和放量" 
                v_bg = "bg-blue"
            
            with k2:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">量能判讀</div>
                    <div class="metric-value" style="font-size:1.1rem; margin:10px 0;">{vol_r:.1f} 倍均量</div>
                    <div><span class="status-badge {v_bg}">{v_msg}</span></div>
                </div>""", unsafe_allow_html=True)

            # 3. MACD
            m_msg = "多方控盤" if last['Hist'] > 0 else "空方控盤"
            m_bg = "bg-red" if last['Hist'] > 0 else "bg-green"
            with k3:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">MACD</div>
                    <div class="metric-value" style="font-size:1.1rem; margin:10px 0;">{last['MACD']:.2f}</div>
                    <div><span class="status-badge {m_bg}">{m_msg}</span></div>
                </div>""", unsafe_allow_html=True)

            # 4. RSI
            r_val = last['RSI']
            r_msg = "中性區域"
            r_bg = "bg-gray"
            if r_val > 70: r_msg, r_bg = "過熱警戒", "bg-red"
            elif r_val < 30: r_msg, r_bg = "超賣區", "bg-green"
                
            with k4:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">RSI</div>
                    <div class="metric-value" style="font-size:1.1rem; margin:10px 0;">{r_val:.1f}</div>
                    <div><span class="status-badge {r_bg}">{r_msg}</span></div>
                </div>""", unsafe_allow_html=True)

            # 【區塊 C】關鍵均線監控 (修復：使用 HTML 字串拼接避免錯誤)
            st.markdown("#### 📏 關鍵均線監控")
            
            # 組合 HTML
            html_content = '<div class="ma-container">'
            for d in ma_list:
                val = last[f'MA_{d}']
                prev_val = prev[f'MA_{d}']
                # 判斷箭頭與顏色
                arrow = "▲" if val > prev_val else "▼"
                cls = "txt-up" if val > prev_val else "txt-down"
                
                html_content += f"""
                    <div class="ma-box">
                        <div class="ma-label">MA {d}</div>
                        <div class="ma-val {cls}">{val:.2f} {arrow}</div>
                    </div>
                """
            html_content += '</div>'
            st.markdown(html_content, unsafe_allow_html=True)

            # 【區塊 D】圖表 (1年日線, 只顯示 4 條線)
            st.markdown("#### 📉 技術分析 (1年日線)")
            
            df_chart = df.tail(250) 
            
            fig = make_subplots(
                rows=4, cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.03, 
                row_heights=[0.5, 0.15, 0.15, 0.2],
                subplot_titles=("", "", "", "")
            )

            # K線
            fig.add_trace(go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], name='K線', showlegend=False), row=1, col=1)
            
            # 四條均線 (5, 20, 60, 120)
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MA_5'], line=dict(color='#D500F9', width=1), name='MA5 (紫)', showlegend=True), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MA_20'], line=dict(color='#FF6D00', width=1.5), name='MA20 (橘)', showlegend=True), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MA_60'], line=dict(color='#00C853', width=1.5), name='MA60 (綠)', showlegend=True), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MA_120'], line=dict(color='#78909C', width=1.5, dash='dot'), name='MA120 (灰)', showlegend=True), row=1, col=1)

            # 成交量
            colors = ['red' if o > c else 'green' for o, c in zip(df_chart['Open'], df_chart['Close'])]
            fig.add_trace(go.Bar(x=df_chart.index, y=df_chart['Volume'], marker_color=colors, name='Volume', showlegend=False), row=2, col=1)

            # RSI
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['RSI'], line=dict(color='#9C27B0', width=2), name='RSI', showlegend=False), row=3, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

            # MACD
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MACD'], line=dict(color='#2196F3', width=1), name='MACD', showlegend=False), row=4, col=1)
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['Signal'], line=dict(color='#FF5722', width=1), name='Signal', showlegend=False), row=4, col=1)
            fig.add_trace(go.Bar(x=df_chart.index, y=df_chart['Hist'], marker_color=['red' if h < 0 else 'green' for h in df_chart['Hist']], name='Hist', showlegend=False), row=4, col=1)

            fig.update_layout(
                height=1000, 
                margin=dict(l=10, r=10, t=30, b=10),
                xaxis_rangeslider_visible=False,
                dragmode=False,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            fig.update_xaxes(fixedrange=True)
            fig.update_yaxes(fixedrange=True)

            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        else:
            st.error("資料不足，請檢查股票代號。")
    except Exception as e:
        st.error(f"系統忙碌中: {e}")
