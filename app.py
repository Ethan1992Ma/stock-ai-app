import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import google.generativeai as genai
from ta.trend import SMAIndicator, MACD
from ta.momentum import RSIIndicator
from datetime import datetime, timedelta

# --- 1. 網頁設定 ---
st.set_page_config(page_title="AI 智能操盤戰情室 (VIP Gemini版)", layout="wide", initial_sidebar_state="expanded")

# --- 全域配色 ---
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

# --- CSS 美化 ---
st.markdown(f"""
    <style>
    :root {{ --primary-color: #ff4b4b; --background-color: #f8f9fa; --secondary-background-color: #ffffff; --text-color: #000000; --font: sans-serif; }}
    .stApp {{ background-color: #f8f9fa; }}
    h1, h2, h3, h4, h5, h6, p, div, label, li, span {{ color: #000000 !important; }}
    .stTextInput > label, .stNumberInput > label, .stRadio > label {{ color: #000000 !important; }}
    
    .txt-up-vip {{ color: {COLOR_UP} !important; font-weight: bold; }}
    .txt-down-vip {{ color: {COLOR_DOWN} !important; font-weight: bold; }}
    .txt-gray-vip {{ color: {COLOR_NEUTRAL} !important; }}
    
    .metric-card {{ background-color: #ffffff; padding: 15px; border-radius: 12px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 10px; border: 1px solid #f0f0f0; }}
    .metric-title {{ color: #6c757d !important; font-size: 0.85rem; font-weight: 700; margin-bottom: 2px; }}
    .metric-value {{ font-size: 1.6rem; font-weight: 800; color: #212529 !important; }}
    .metric-sub {{ font-size: 0.85rem; margin-top: 2px; }} 
    
    .ai-summary-card {{ background-color: #fff; padding: 20px; border-radius: 15px; border: 1px solid #e0e0e0; border-left: 5px solid #9C27B0; margin-top: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
    .ai-title {{ font-weight: bold; font-size: 1.2rem; color: #6a1b9a !important; margin-bottom: 10px; display: flex; align-items: center; }}
    .ai-content {{ font-size: 1rem; color: #333 !important; line-height: 1.6; white-space: pre-line; }}
    
    .chart-container {{ background-color: #ffffff; padding: 10px; border-radius: 10px; margin-bottom: 15px; }}
    </style>
    """, unsafe_allow_html=True)

# --- 2. 數據抓取 (加強版：快取 + 防斷檔) ---
@st.cache_data(ttl=60)
def fetch_stock_data_cached(ticker):
    try:
        stock = yf.Ticker(ticker)
        
        # 1. 抓日線 (長線趨勢)
        df = stock.history(period="1y")
        
        # 2. 抓分時線 (防呆邏輯：抓 5 天，取最後一天)
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

def fetch_exchange_rate():
    return 32.5 # 簡化範例，實際可抓

# --- 3. Gemini AI 分析函數 ---
def get_gemini_analysis(api_key, ticker, data_summary):
    if not api_key:
        return "⚠️ 請先在側邊欄輸入 Gemini API Key"
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        你是一位華爾街頂級交易員，請根據以下 {ticker} 的技術數據，用繁體中文給出一段專業、犀利且有溫度的短評 (約 150 字)。
        
        【技術數據】
        - 現價: {data_summary['price']}
        - 趨勢狀態: {data_summary['trend']}
        - RSI (14): {data_summary['rsi']:.1f} ({data_summary['rsi_status']})
        - MACD狀態: {data_summary['macd_status']}
        - 成交量狀態: {data_summary['vol_status']}
        
        【回答要求】
        1. 先講結論 (多/空/盤整)。
        2. 分析關鍵風險或機會 (例如 RSI 過熱或 MACD 背離)。
        3. 給出操作建議 (例如「拉回均線佈局」或「嚴設停損」)。
        4. 語氣要像資深前輩，不要像機器人。
        """
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ AI 分析失敗: {str(e)}"

# --- 4. 局部刷新元件 ---
@st.fragment
def render_calculator(price, rate, q_type):
    # (此處保持你原本的計算機代碼，為節省篇幅省略，請貼回原本的代碼)
    st.info("🧮 交易計算機 (功能同前，省略以節省篇幅)")

# --- 5. 主程式 ---
with st.sidebar:
    st.header("⚙️ 設定")
    ticker_input = st.text_input("股票代號", "TSLA").upper()
    gemini_key = st.text_input("Gemini API Key", type="password", placeholder="貼上你的 Key")
    st.caption("[取得免費 API Key](https://aistudio.google.com/app/apikey)")
    
    if st.button("🔄 刷新"):
        st.cache_data.clear()
        st.rerun()

if ticker_input:
    # 呼叫 Cache 函數
    df, df_intra, info, quote_type = fetch_stock_data_cached(ticker_input)
    exchange_rate = fetch_exchange_rate()

    if not df.empty:
        # --- 指標計算 ---
        df['MA_5'] = SMAIndicator(df['Close'], window=5).sma_indicator()
        df['MA_20'] = SMAIndicator(df['Close'], window=20).sma_indicator()
        df['RSI'] = RSIIndicator(df['Close'], window=14).rsi()
        macd = MACD(df['Close'])
        df['MACD'] = macd.macd()
        df['Signal'] = macd.macd_signal()
        df['Hist'] = macd.macd_diff()
        
        # 取得最新一筆資料
        last = df.iloc[-1]
        curr_price = last['Close']
        
        # 簡易狀態判斷 (給 AI 用)
        rsi_stat = "過熱" if last['RSI'] > 70 else "超賣" if last['RSI'] < 30 else "中性"
        trend_stat = "多頭排列" if last['Close'] > last['MA_5'] > last['MA_20'] else "空頭排列" if last['Close'] < last['MA_5'] < last['MA_20'] else "盤整"
        macd_stat = "金叉向上" if last['Hist'] > 0 else "死叉向下"
        
        # --- 介面開始 ---
        st.markdown(f"### 🚀 {ticker_input} 戰情室")
        
        # 分頁
        tab1, tab2 = st.tabs(["📊 走勢分析", "🤖 AI 觀點"])
        
        with tab1:
            # --- 迷你走勢圖 (Sparkline) ---
            # 這裡解決 X 軸時間與斷檔問題
            
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown("##### 📈 即時資金流向 (含盤前/盤後)")
                if not df_intra.empty:
                    fig_spark = go.Figure()
                    
                    # 畫線
                    fig_spark.add_trace(go.Scatter(
                        x=df_intra.index, 
                        y=df_intra['Close'], 
                        mode='lines', 
                        line=dict(color=COLOR_UP if df_intra['Close'].iloc[-1] >= df_intra['Open'].iloc[0] else COLOR_DOWN, width=2),
                        fill='tozeroy',
                        fillcolor=f"rgba({(5, 154, 129) if df_intra['Close'].iloc[-1] >= df_intra['Open'].iloc[0] else (242, 54, 69)}, 0.1)"
                    ))

                    # 設定 X 軸關鍵時間點 (台灣時間)
                    # 17:00 (盤前), 22:30 (開盤), 05:00 (收盤), 09:00 (盤後)
                    # 這裡只顯示小時:分鐘
                    fig_spark.update_xaxes(
                        tickformat="%H:%M",  # 只顯示 22:30 這種格式
                        showgrid=True,
                        gridcolor='#eee',
                        # 強制顯示特定的 ticks 比較困難，因為資料點不一定剛好在那一秒
                        # 改用 dtick 來讓它每隔固定時間顯示，或者讓 Plotly 自動處理但格式化為台灣時間
                    )

                    fig_spark.update_layout(
                        height=200,
                        margin=dict(l=0, r=0, t=10, b=20),
                        paper_bgcolor='white',
                        plot_bgcolor='white',
                        xaxis=dict(type='date'), # Plotly 會自動解析 datetime index
                        yaxis=dict(showgrid=False, visible=True, side='right') # 價格軸放右邊
                    )
                    st.plotly_chart(fig_spark, use_container_width=True, config={'displayModeBar': False})
                else:
                    st.warning("暫無即時走勢資料")

            with c2:
                # 顯示基本數據
                chg = curr_price - df.iloc[-2]['Close']
                pct = (chg / df.iloc[-2]['Close']) * 100
                color_cls = "txt-up-vip" if chg >= 0 else "txt-down-vip"
                
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">最新成交價</div>
                    <div class="metric-value {color_cls}">${curr_price:.2f}</div>
                    <div class="metric-sub {color_cls}">{chg:+.2f} ({pct:+.2f}%)</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">RSI 強弱</div>
                    <div class="metric-value">{last['RSI']:.1f}</div>
                    <div class="metric-sub">{rsi_stat}</div>
                </div>
                """, unsafe_allow_html=True)

            # --- 技術分析圖 (MACD / K線) ---
            # 這裡使用 df (日線)，所以不會有斷檔問題
            st.markdown("---")
            st.markdown("##### 📉 日線趨勢 & MACD")
            
            # (這裡可以放原本的 K線圖與 MACD 圖代碼，略)
            # 確保 MACD 柱狀體顏色邏輯正確
            
            fig_macd = go.Figure()
            # 為了讓顏色正確，我們需要建立一個顏色陣列
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
            
            fig_macd.update_layout(height=250, margin=dict(l=0,r=0,t=20,b=20), paper_bgcolor='white', plot_bgcolor='white')
            st.plotly_chart(fig_macd, use_container_width=True)

        with tab2:
            st.subheader("🤖 Gemini 戰情分析")
            if st.button("✨ 產生 AI 分析報告"):
                if not gemini_key:
                    st.error("請在側邊欄輸入 API Key")
                else:
                    with st.spinner("AI 正在思考市場邏輯..."):
                        # 準備數據包
                        data_summary = {
                            "price": f"{curr_price:.2f}",
                            "trend": trend_stat,
                            "rsi": last['RSI'],
                            "rsi_status": rsi_stat,
                            "macd_status": macd_stat,
                            "vol_status": "量增" if last['Volume'] > df['Volume'].mean() else "量縮" # 簡易判斷
                        }
                        
                        # 呼叫 API
                        analysis_text = get_gemini_analysis(gemini_key, ticker_input, data_summary)
                        
                        st.markdown(f"""
                        <div class="ai-summary-card">
                            <div class="ai-title">🧠 Gemini 觀點</div>
                            <div class="ai-content">{analysis_text}</div>
                        </div>
                        """, unsafe_allow_html=True)

    else:
        st.error("查無資料")