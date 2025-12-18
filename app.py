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
    
    /* 漂亮的資訊卡片 */
    .metric-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 10px;
        border: 1px solid #f0f0f0;
        position: relative;
    }
    .metric-title { color: #6c757d; font-size: 0.9rem; font-weight: 700; margin-bottom: 5px; }
    .metric-value { font-size: 1.8rem; font-weight: 800; color: #212529; }
    .metric-sub { font-size: 0.9rem; color: #888; margin-top: 5px; }
    
    /* 當日走勢專用樣式 */
    .intra-info { 
        display: flex; 
        justify-content: space-between; 
        font-size: 0.8rem; 
        color: #aaa; 
        margin-top: 5px; 
        margin-bottom: 5px;
    }

    /* AI 總結卡片樣式 */
    .ai-summary-card {
        background-color: #e3f2fd;
        padding: 20px;
        border-radius: 15px;
        border-left: 5px solid #2196f3;
        margin-top: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    .ai-title { font-weight: bold; font-size: 1.2rem; color: #0d47a1; margin-bottom: 10px; display: flex; align-items: center; }
    .ai-content { font-size: 1rem; color: #333; line-height: 1.6; }

    /* 均線監控容器 */
    .ma-container {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        background-color: #ffffff;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border: 1px solid #f0f0f0;
        margin-bottom: 20px;
    }
    .ma-box {
        flex: 1 1 100px;
        text-align: center;
        padding: 10px;
        background-color: #f8f9fa;
        border-radius: 10px;
        border: 1px solid #dee2e6;
    }
    .ma-label { font-size: 0.8rem; font-weight: bold; color: #666; margin-bottom: 5px; }
    .ma-val { font-size: 1.1rem; font-weight: 800; }
    
    /* 顏色定義 */
    .txt-up { color: #ff4b4b; }
    .txt-down { color: #21c354; }
    
    /* 狀態標籤 */
    .status-badge { 
        padding: 4px 8px; 
        border-radius: 6px; 
        font-size: 0.85rem; 
        font-weight: bold; 
        color: white; 
        display: inline-block; 
        margin-top: 8px;
    }
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
    # 歷史資料 (2年)
    df = stock.history(period="2y")
    # 當日走勢資料 (1天, 5分K)
    df_intra = stock.history(period="1d", interval="5m")
    info = stock.info
    return df, df_intra, info

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
        df, df_intra, info = get_stock_data(ticker_input)
        
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

            # 最新數據
            last = df.iloc[-1]
            prev = df.iloc[-2]
            change = last['Close'] - prev['Close']
            pct_change = (change / prev['Close']) * 100
            price_color = "#ff4b4b" if change > 0 else "#21c354"
            
            # --- 版面顯示 ---
            st.markdown(f"### 📱 {info.get('longName', ticker_input)} ({ticker_input})")
            st.caption(f"目前策略：{strat_desc}")

            # 【區塊 A】基本面與價格 (當日走勢修復版)
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                # 準備當日走勢圖
                fig_spark = go.Figure()
                
                if not df_intra.empty:
                    day_open = df_intra['Open'].iloc[0]
                    day_close = df_intra['Close'].iloc[-1]
                    day_high = df_intra['High'].max()
                    day_low = df_intra['Low'].min()
                    
                    spark_color = '#ff4b4b' if day_close >= day_open else '#21c354'
                    fill_color = f"rgba({255 if day_close>=day_open else 33}, {75 if day_close>=day_open else 195}, {75 if day_close>=day_open else 84}, 0.1)"
                    
                    # 繪製走勢
                    fig_spark.add_trace(go.Scatter(
                        x=df_intra.index, y=df_intra['Close'],
                        mode='lines',
                        line=dict(color=spark_color, width=2),
                        fill='tozeroy', 
                        fillcolor=fill_color
                    ))
                    
                    # 關鍵修復：動態設定 Y 軸範圍，避免變成直線
                    # 稍微上下留白 1% 讓圖形好看
                    y_min = day_low * 0.999
                    y_max = day_high * 1.001
                    
                    fig_spark.update_layout(
                        height=80, # 高度增加
                        margin=dict(l=0, r=0, t=5, b=5),
                        xaxis=dict(visible=False),
                        yaxis=dict(visible=False, range=[y_min, y_max]), # 強制範圍
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        showlegend=False,
                        dragmode=False
                    )
                    
                    # 生成 HTML
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-title">最新股價</div>
                        <div class="metric-value" style="color:{price_color}">{last['Close']:.2f}</div>
                        <div class="metric-sub">
                            {('+' if change > 0 else '')}{change:.2f} ({pct_change:.2f}%)
                        </div>
                        <div class="intra-info">
                            <span>H: {day_high:.2f}</span>
                            <span>L: {day_low:.2f}</span>
                        </div>
                    </div>""", unsafe_allow_html=True)
                    # 插入圖表 (為了讓它在卡片內，使用 margin-top 負值技巧或直接顯示)
                    st.plotly_chart(fig_spark, use_container_width=True, config={'displayModeBar': False})
                else:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-title">最新股價</div>
                        <div class="metric-value" style="color:{price_color}">{last['Close']:.2f}</div>
                        <div class="metric-sub">休市或無當日資料</div>
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

            # 【區塊 B】AI 訊號卡片
            st.markdown("#### 🤖 策略訊號解讀")
            k1, k2, k3, k4 = st.columns(4)
            
            trend_status = "盤整"
            rsi_status = "中性"
            vol_status = "一般"
            macd_status = "不明"

            # 1. 趨勢
            trend_msg = "💤 睡覺行情 (盤整)"
            trend_bg = "bg-gray"
            trend_desc = "多空不明，建議觀望"
            if last['Close'] > strat_fast_val > strat_slow_val:
                trend_msg = "🚀 火力全開！(多頭)"
                trend_bg = "bg-red"
                trend_desc = "均線向上，順勢操作"
                trend_status = "多頭"
            elif last['Close'] < strat_fast_val < strat_slow_val:
                trend_msg = "🐻 熊出沒注意 (空頭)"
                trend_bg = "bg-green"
                trend_desc = "均線蓋頭，保守為宜"
                trend_status = "空頭"
            
            with k1:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">趨勢訊號</div>
                    <div class="metric-value" style="font-size:1.3rem;">{trend_msg}</div>
                    <div><span class="status-badge {trend_bg}">MA{strat_fast} vs MA{strat_slow}</span></div>
                    <div class="metric-sub">{trend_desc}</div>
                </div>""", unsafe_allow_html=True)
            
            # 2. 量能
            vol_r = last['Volume'] / last['Vol_MA'] if last['Vol_MA'] > 0 else 0
            v_msg = "❄️ 冷冷清清"
            v_bg = "bg-gray"
            if vol_r > 1.5: 
                v_msg = "🔥 資金派對 (爆量)"
                v_bg = "bg-red"
                vol_status = "爆量"
            elif vol_r > 1.0:
                v_msg = "💧 人氣回溫" 
                v_bg = "bg-blue"
                vol_status = "溫和"
            
            with k2:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">量能判讀</div>
                    <div class="metric-value" style="font-size:1.3rem;">{v_msg}</div>
                    <div><span class="status-badge {v_bg}">{vol_r:.1f} 倍均量</span></div>
                    <div class="metric-sub">成交量活躍度分析</div>
                </div>""", unsafe_allow_html=True)

            # 3. MACD
            m_msg = "🐂 牛軍集結" if last['Hist'] > 0 else "📉 空軍壓境"
            m_bg = "bg-red" if last['Hist'] > 0 else "bg-green"
            macd_status = "多方" if last['Hist'] > 0 else "空方"
            with k3:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">MACD 趨勢</div>
                    <div class="metric-value" style="font-size:1.3rem;">{m_msg}</div>
                    <div><span class="status-badge {m_bg}">數值: {last['MACD']:.2f}</span></div>
                    <div class="metric-sub">籌碼動能方向</div>
                </div>""", unsafe_allow_html=True)

            # 4. RSI
            r_val = last['RSI']
            r_msg = "⚖️ 多空拔河"
            r_bg = "bg-gray"
            if r_val > 70: 
                r_msg = "🔥 太燙了！(過熱)" 
                r_bg = "bg-red"
                rsi_status = "過熱"
            elif r_val < 30: 
                r_msg = "🧊 跌過頭囉 (超賣)"
                r_bg = "bg-green"
                rsi_status = "超賣"
                
            with k4:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">RSI 強弱</div>
                    <div class="metric-value" style="font-size:1.3rem;">{r_msg}</div>
                    <div><span class="status-badge {r_bg}">數值: {r_val:.1f}</span></div>
                    <div class="metric-sub">乖離率判斷</div>
                </div>""", unsafe_allow_html=True)

            # 【區塊 C】關鍵均線監控
            st.markdown("#### 📏 關鍵均線監控")
            ma_html_inner = ""
            for d in ma_list:
                val = last[f'MA_{d}']
                prev_val = prev[f'MA_{d}']
                arrow = "▲" if val > prev_val else "▼"
                cls = "txt-up" if val > prev_val else "txt-down"
                ma_html_inner += f'<div class="ma-box"><div class="ma-label">MA {d}</div><div class="ma-val {cls}">{val:.2f} {arrow}</div></div>'
            st.markdown(f'<div class="ma-container">{ma_html_inner}</div>', unsafe_allow_html=True)

            # 【區塊 D】圖表
            st.markdown("#### 📉 技術分析 (1年日線)")
            df_chart = df.tail(250) 
            fig = make_subplots(
                rows=4, cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.03, 
                row_heights=[0.5, 0.15, 0.15, 0.2],
                subplot_titles=("", "", "", "")
            )
            fig.add_trace(go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], name='K線', showlegend=False), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MA_5'], line=dict(color='#D500F9', width=1), name='MA5 (紫)', showlegend=True), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MA_20'], line=dict(color='#FF6D00', width=1.5), name='MA20 (橘)', showlegend=True), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MA_60'], line=dict(color='#00C853', width=1.5), name='MA60 (綠)', showlegend=True), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MA_120'], line=dict(color='#78909C', width=1.5, dash='dot'), name='MA120 (灰)', showlegend=True), row=1, col=1)
            colors = ['red' if o > c else 'green' for o, c in zip(df_chart['Open'], df_chart['Close'])]
            fig.add_trace(go.Bar(x=df_chart.index, y=df_chart['Volume'], marker_color=colors, name='Volume', showlegend=False), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['RSI'], line=dict(color='#9C27B0', width=2), name='RSI', showlegend=False), row=3, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MACD'], line=dict(color='#2196F3', width=1), name='MACD', showlegend=False), row=4, col=1)
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['Signal'], line=dict(color='#FF5722', width=1), name='Signal', showlegend=False), row=4, col=1)
            fig.add_trace(go.Bar(x=df_chart.index, y=df_chart['Hist'], marker_color=['red' if h < 0 else 'green' for h in df_chart['Hist']], name='Hist', showlegend=False), row=4, col=1)
            fig.update_layout(height=1000, margin=dict(l=10, r=10, t=30, b=10), xaxis_rangeslider_visible=False, dragmode=False, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            fig.update_xaxes(fixedrange=True)
            fig.update_yaxes(fixedrange=True)
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

            # 【區塊 E】AI 綜合判讀
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
            
            st.markdown(f"""
            <div class="ai-summary-card">
                <div class="ai-title">🤖 AI 綜合判讀報告</div>
                <div class="ai-content">
                    {ai_suggestion}<br><br>
                    <b>關鍵數據摘要：</b><br>
                    • 趨勢：{trend_status}<br>
                    • 量能：{vol_status} ({vol_r:.1f}倍)<br>
                    • 籌碼 (MACD)：{macd_status}<br>
                    • 強弱 (RSI)：{r_val:.1f} ({rsi_status})
                </div>
            </div>
            """, unsafe_allow_html=True)

        else:
            st.error("資料不足，請檢查股票代號。")
    except Exception as e:
        st.error(f"系統忙碌中: {e}")
