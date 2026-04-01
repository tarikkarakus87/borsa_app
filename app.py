import streamlit as st
from isyatirimhisse import fetch_stock_data
import pandas as pd
import sqlite3
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 1. VERİTABANI VE KOMİSYON İŞLEMLERİ ---
DB_FILE = "pms_data.db"
COMMISSION_RATE = 0.0020 # %0.20 (Binde 2)

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS bankroll (id INTEGER PRIMARY KEY, balance REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS portfolio (ticker TEXT PRIMARY KEY, avg_price REAL, quantity INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT, type TEXT, price REAL, qty INTEGER, date TEXT)''')
    c.execute("SELECT COUNT(*) FROM bankroll")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO bankroll (id, balance) VALUES (1, 10000.0)")
    conn.commit()
    conn.close()

def get_bankroll():
    conn = sqlite3.connect(DB_FILE)
    try:
        res = pd.read_sql_query("SELECT balance FROM bankroll WHERE id=1", conn)
        if res.empty:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO bankroll (id, balance) VALUES (1, 10000.0)")
            conn.commit()
            return 10000.0
        val = res['balance'].iloc[0]
        return float(val) if val is not None else 10000.0
    except Exception:
        return 10000.0
    finally:
        conn.close()

def update_bankroll(new_balance):
    if new_balance is None: return
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("INSERT OR REPLACE INTO bankroll (id, balance) VALUES (1, ?)", (float(new_balance),))
        conn.commit()
    except: pass
    finally: conn.close()

def get_portfolio():
    conn = sqlite3.connect(DB_FILE)
    try:
        df = pd.read_sql_query("SELECT * FROM portfolio", conn)
        return df
    except Exception:
        return pd.DataFrame(columns=['ticker', 'avg_price', 'quantity'])
    finally:
        conn.close()

def get_transactions(ticker, t_type=None):
    conn = sqlite3.connect(DB_FILE)
    try:
        query = "SELECT id, type as 'İşlem', price as 'Fiyat', qty as 'Adet', date as 'Tarih' FROM transactions WHERE ticker=?"
        params = [ticker]
        if t_type:
            query += " AND type=?"
            params.append(t_type)
        query += " ORDER BY id DESC"
        df = pd.read_sql_query(query, conn, params=params)
        return df
    except:
        return pd.DataFrame()
    finally:
        conn.close()

def get_all_history():
    conn = sqlite3.connect(DB_FILE)
    try:
        df = pd.read_sql_query("""
            SELECT id as 'ID', date as 'Tarih', ticker as 'Hisse', type as 'İşlem', 
                   qty as 'Adet', price as 'Fiyat', (qty * price) as 'Toplam Tutar' 
            FROM transactions ORDER BY id DESC
        """, conn)
        return df
    except:
        return pd.DataFrame()
    finally:
        conn.close()

# YENİ FONKSİYONLAR: Silme ve Yeniden Hesaplama
def recalculate_portfolio(ticker):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        # Kalan tüm işlemleri çek
        df_t = pd.read_sql_query("SELECT type, price, qty FROM transactions WHERE ticker=?", conn, params=(ticker,))
        if df_t.empty:
            c.execute("DELETE FROM portfolio WHERE ticker=?", (ticker,))
        else:
            buys = df_t[df_t['type'] == 'AL']
            sells = df_t[df_t['type'] == 'SAT']
            
            total_buy_qty = buys['qty'].sum()
            total_sell_qty = sells['qty'].sum()
            total_qty = total_buy_qty - total_sell_qty
            
            if total_qty <= 0:
                c.execute("DELETE FROM portfolio WHERE ticker=?", (ticker,))
            else:
                # Ortalama maliyete AL komisyonunu dahil ediyoruz (%0.2)
                total_buy_cost = (buys['price'] * buys['qty'] * (1 + COMMISSION_RATE)).sum()
                avg_price = total_buy_cost / total_buy_qty
                c.execute("INSERT OR REPLACE INTO portfolio (ticker, avg_price, quantity) VALUES (?, ?, ?)", 
                          (ticker, float(avg_price), int(total_qty)))
        conn.commit()
    except Exception as e:
        st.error(f"Pesportföy Yeniden Hesaplama Hatası: {e}")
    finally:
        conn.close()

def delete_transaction(t_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        # Önce işlemi verisini al (Kasa iadesi için)
        c.execute("SELECT ticker, type, price, qty FROM transactions WHERE id=?", (t_id,))
        row = c.fetchone()
        if not row: return
        
        ticker, t_type, price, qty = row
        current_bankroll = get_bankroll()
        
        # Kasa Telafisi (Komisyonlarla birlikte iade/düşüm)
        if t_type == "AL":
            # Alırken ödenen tutar + komisyon kasaya geri döner
            update_bankroll(current_bankroll + (price * qty * (1 + COMMISSION_RATE)))
        else:
            # Satarken kasaya giren net tutar (komisyon çıktıktan sonraki halide) kasadan geri düşülür
            update_bankroll(current_bankroll - (price * qty * (1 - COMMISSION_RATE)))
            
        # İşlemi sil
        c.execute("DELETE FROM transactions WHERE id=?", (t_id,))
        conn.commit()
        conn.close()
        
        # Portföyü o hisse için yeniden hesapla
        recalculate_portfolio(ticker)
        st.success(f"İşlem {t_id} silindi ve bakiye/maliyet hesapları güncellendi.")
        st.rerun()
    except Exception as e:
        st.error(f"Silme Hatası: {e}")
        if conn: conn.close()

def add_to_portfolio(ticker, price, qty):
    if None in [ticker, price, qty] or pd.isnull(price) or pd.isnull(qty): return
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        now = datetime.now().strftime("%d-%m-%Y %H:%M")
        c.execute("INSERT INTO transactions (ticker, type, price, qty, date) VALUES (?, ?, ?, ?, ?)", (ticker, "AL", float(price), int(qty), now))
        conn.commit()
        conn.close()
        recalculate_portfolio(ticker) # Her işlemden sonra yeniden hesapla
    except Exception as e:
        st.error(f"Ekleme Hatası: {e}")

def sell_from_portfolio(ticker, sell_price, sell_qty):
    if None in [ticker, sell_price, sell_qty] or pd.isnull(sell_price) or pd.isnull(sell_qty): return 0, 0, "Hata"
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        now = datetime.now().strftime("%d-%m-%Y %H:%M")
        c.execute("INSERT INTO transactions (ticker, type, price, qty, date) VALUES (?, ?, ?, ?, ?)", (ticker, "SAT", float(sell_price), int(sell_qty), now))
        conn.commit()
        conn.close()
        recalculate_portfolio(ticker)
        return 0, 0, None
    except Exception as e:
        return 0, 0, f"Satış Hatası: {e}"

# --- 2. HİSSE LİSTESİ VE ANALİZ MOTORU ---
BIST_LIST = [
    "THYAO.IS", "ASELS.IS", "TUPRS.IS", "KCHOL.IS", "AKBNK.IS", "ISCTR.IS", "EREGL.IS", "SAHOL.IS", 
    "BIMAS.IS", "SISE.IS", "ARCLK.IS", "YKBNK.IS", "GARAN.IS", "PETKM.IS", "HEKTS.IS", "SASA.IS", 
    "KOZAL.IS", "PGSUS.IS", "EKGYO.IS", "ODAS.IS", "TOASO.IS", "FROTO.IS", "HALKB.IS", "VAKBN.IS", 
    "DOHOL.IS", "TTKOM.IS", "TCELL.IS", "ENKAI.IS", "GUBRF.IS", "ALARK.IS", "MGROS.IS", "SOKM.IS", 
    "TAVHL.IS", "TKFEN.IS", "ULKER.IS", "VESTL.IS", "ZOREN.IS", "DOAS.IS", "ENJSA.IS", "OYAKC.IS"
]

def calculate_indicators(df):
    if df.empty: return df
    try:
        close = df['Close']
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).ewm(com=13, min_periods=14).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(com=13, min_periods=14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / loss)))
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        df['MACD'] = ema12 - ema26
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MA20'] = close.rolling(window=20).mean()
        df['STD20'] = close.rolling(window=20).std()
        df['Upper_BB'] = df['MA20'] + (df['STD20'] * 2)
        df['Lower_BB'] = df['MA20'] - (df['STD20'] * 2)
        df['Vol_SMA20'] = df['Volume'].rolling(window=20).mean()
    except: pass
    return df

# --- 3. ARAYÜZ (STREAMLIT) ---
st.set_page_config(page_title="BIST PMS & Analiz", page_icon="💼", layout="wide")
init_db()

st.markdown("""
<style>
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; }
    .signal-box { padding: 25px; border-radius: 12px; text-align: center; font-weight: bold; font-size: 32px; margin-bottom: 20px; color: white; }
    .al { background-color: #27ae60; border: 2px solid #2ecc71; box-shadow: 0 0 15px #27ae60; }
    .sat { background-color: #c0392b; border: 2px solid #e74c3c; box-shadow: 0 0 15px #c0392b; }
    .tut { background-color: #2c3e50; border: 2px solid #95a5a6; color: #ecf0f1; }
    .reason-box { background-color: #1e2130; padding: 15px; border-radius: 10px; margin-top: -10px; margin-bottom: 25px; border-left: 5px solid #3498db; }
    .delete-btn { color: #e74c3c; cursor: pointer; }
</style>
""", unsafe_allow_html=True)

# SIDEBAR
st.sidebar.title("💰 Kasa ve Portföy")

if st.sidebar.button("🔄 Verileri Yenile"):
    st.cache_data.clear()
    st.rerun()

bankroll = get_bankroll()
portfolio_df = get_portfolio()
st.sidebar.metric("Ana Kasa Bakiyesi", f"{bankroll:,.2f} TL")

if not portfolio_df.empty:
    st.sidebar.markdown("### 📦 Mevcut Portföy")
    for _, row in portfolio_df.iterrows():
        try:
            ticker = row['ticker']
            qty = int(row['quantity'])
            avg_p = float(row['avg_price'])
            if qty > 0:
                with st.sidebar.expander(f"**{ticker}** | {qty} Adet | Ort: {avg_p:.2f} TL"):
                    history = get_transactions(ticker, t_type="AL")
                    if not history.empty:
                        # Sidebar silme butonları
                        for _, t in history.iterrows():
                            c1, c2 = st.columns([4, 1])
                            c1.caption(f"{t['Tarih']}: {int(t['Adet'])} Adet @ {t['Fiyat']:.2f}")
                            if c2.button("❌", key=f"del_side_{t['id']}"):
                                delete_transaction(t['id'])
                    else: st.write("Alış kaydı bulunamadı.")
        except: continue

st.sidebar.markdown("---")
new_fund = st.sidebar.number_input("Bütçeyi Güncelle", value=float(bankroll))
if st.sidebar.button("Kasayı Kaydet"):
    update_bankroll(new_fund)
    st.rerun()

# ANA EKRAN SEKMELERİ
tab1, tab2 = st.tabs(["📈 Analiz ve Sinyaller", "📜 Tüm İşlem Geçmişi"])

with tab1:
    st.title("🚀 Borsa Analiz ve Portföy Yönetimi")
    col1, col2 = st.columns([2, 1])
    with col1:
        selected_ticker = st.selectbox("Popüler Hisseler", BIST_LIST, index=0)
    with col2:
        manual_ticker = st.text_input("Listede Yoksa Manuel Girin:").upper()
    
    stock_ticker = manual_ticker if manual_ticker else selected_ticker

    try:
        # Hisse sembolündeki .IS uzantısını temizle (İş Yatırım formatı)
        clean_ticker = stock_ticker.replace(".IS", "")
        
        # Tarih Formatı: DD-MM-YYYY (İş Yatırım İsteği)
        end_str = datetime.now().strftime('%d-%m-%Y')
        start_str = (datetime.now() - timedelta(days=3*365)).strftime('%d-%m-%Y')
        
        # Veriyi İş Yatırım'dan çek (Yeni versiyon: fetch_stock_data)
        data = fetch_stock_data(
            symbols=clean_ticker,
            start_date=start_str,
            end_date=end_str
        )
        
        if data is not None and not data.empty:
            # İş Yatırım sütunlarını standart isimlere çevir (Final Mapping)
            mapping = {
                'HGDG_KAPANIS': 'Close',
                'HGDG_MIN': 'Low',
                'HGDG_MAX': 'High',
                'HGDG_HACIM': 'Volume',
                'HGDG_TARIH': 'Date'
            }
            data = data.rename(columns=mapping)
            
            # Tarih sütununu datetime formatına çevir ve index yap
            if 'Date' in data.columns:
                data['Date'] = pd.to_datetime(data['Date'])
                data = data.set_index('Date')
            
            # Analiz kodlarının hata vermemesi için eksik sütunları (Open vb.) doldur
            if 'Open' not in data.columns:
                data['Open'] = data['Close']
            
            # Eğer tarih zaten index olarak geliyorsa ismini Date yap
            data.index.name = 'Date'
            
            # Eksik verileri temizle
            data = data.dropna(subset=['Close'])

        if data is None or data.empty:
            st.warning(f"{stock_ticker} için veri bulunamadı (İş Yatırım).")
        else:
            df = calculate_indicators(data)
            df_valid = df.replace(0, pd.NA).dropna(subset=['Close'])
            if df_valid.empty:
                st.error("Geçerli fiyat verisi bulunamadı.")
                st.stop()
            curr = df_valid.iloc[-1]
            prev = df_valid.iloc[-2] if len(df_valid) > 1 else curr
            
            def safe_f(val): return float(val) if pd.notnull(val) else 0.0
            price, rsi, macd = safe_f(curr['Close']), safe_f(curr['RSI']), safe_f(curr['MACD'])
            sig, vol, vol_avg = safe_f(curr['MACD_Signal']), safe_f(curr['Volume']), safe_f(curr['Vol_SMA20'])
            upper_bb = safe_f(curr['Upper_BB'])

            is_owned = stock_ticker in portfolio_df['ticker'].values
            decision, reasons = "TUT", []
            rsi_rising = rsi > safe_f(prev['RSI'])
            ma20 = safe_f(curr['MA20'])
            
            # Risk Yönetimi: %3 Kar Marjı Filtresi
            potential_profit_pct = ((upper_bb - price) / price) * 100 if price > 0 else 0
            
            if (macd > sig) and (30 <= rsi <= 50) and rsi_rising and (vol > vol_avg):
                if is_owned: 
                    decision, reasons = "TUT", [f"Detaylı Analiz: Bot şu an AL sinyali üretiyor (RSI: {rsi:.2f}, MACD pozitif, Hacim onaylı) ancak hisse zaten portföyünüzde olduğu için yeni alım planlanmadı. Mevcut pozisyonu korumaya devam edin."]
                elif potential_profit_pct < 3.0:
                    decision = "TUT"
                    reasons.append(f"Detaylı Analiz: MACD ve RSI olumlu olsa da, Bollinger Üst Bandına olan potansiyel kâr marjı (%{potential_profit_pct:.2f}) minimum %3 sınırının altında. İşlem maliyetlerini (komisyon/kayma) kurtarmayacağı için risk/ödül oranı yetersiz, bekleyin.")
                else:
                    decision = "AL"
                    plan_tl = bankroll * 0.10
                    limit_p = price * 1.02
                    qty_p = int(plan_tl / limit_p) if limit_p > 0 else 0
                    reasons.append(f"Detaylı Analiz: MACD pozitif, RSI ({rsi:.2f}) ivmeleniyor ve Hacim ({vol:,.0f}) onaylı. Hedeflenen kâr marjı (%{potential_profit_pct:.2f}) %3 sınırının üzerinde olduğu için sinyal onaylandı. Kasa %10 ({plan_tl:.2f} TL) ile {qty_p} adet alım planlanabilir.")
            elif (price >= upper_bb) or (rsi > 70) or (macd < sig):
                decision = "SAT"
                if price >= upper_bb: reasons.append(f"Detaylı Analiz: Güncel fiyat ({price:.2f} TL), Bollinger Üst Bandına ({upper_bb:.2f} TL) ulaştı/aştı. Kâr realizasyonu zamanı gelmiş olabilir.")
                if rsi > 70: reasons.append(f"Detaylı Analiz: RSI ({rsi:.2f}) aşırı alım bölgesinde. Geri çekilme riski yüksek.")
                if macd < sig: reasons.append(f"Detaylı Analiz: MACD negatife döndü, momentum kaybı yaşanıyor.")
            else: 
                decision = "TUT"
                missed = []
                if vol <= vol_avg: missed.append("Hacim yetersiz")
                if rsi > 50: missed.append("RSI 50 üstü (Geç)")
                if rsi < 30: missed.append("RSI 30 altı (Erken)")
                reasons.append(f"Detaylı Analiz: Kararsız Piyasa. {(' + '.join(missed)) if missed else 'Net kırılım yok'}. Fiyat Orta Bant ({ma20:.2f} TL) civarında yön arıyor. Beklemede kalın.")

            c1, c2 = st.columns([1, 2])
            with c1: st.metric(f"{stock_ticker}", f"{price:.2f} TL", f"{((price-safe_f(prev['Close']))/safe_f(prev['Close'])*100):.2f}%")
            with c2:
                st.markdown(f'<div class="signal-box {decision.lower()}">{decision} SİNYALİ</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="reason-box"><b>📝 Kapsamlı Analiz Raporu:</b><br>{"<br>".join(reasons)}</div>', unsafe_allow_html=True)

            st.markdown("---")
            tt1, tt2 = st.tabs(["🛒 Alım Kaydet", "💰 Satış Kaydet"])
            with tt1:
                with st.form("buy_form"):
                    bq = st.number_input("Adet", min_value=1, step=1)
                    bp = st.number_input("Fiyat", value=price)
                    if st.form_submit_button("ALIMI TAMAMLA"):
                        total_cost = (bp * bq) * (1 + COMMISSION_RATE)
                        if bp > 0 and total_cost <= bankroll:
                            add_to_portfolio(stock_ticker, bp, bq)
                            update_bankroll(bankroll - total_cost)
                            st.success(f"{stock_ticker} için {bq} adet {bp:.2f} TL fiyattan alım yapıldı. Komisyon dahil maliyet: {total_cost:.2f} TL.")
                            st.rerun()
                        else: st.error(f"Bakiye yetersiz! Gereken tutar (Komisyon dahil): {total_cost:.2f} TL.")
            with tt2:
                if is_owned:
                    curr_q = int(portfolio_df[portfolio_df['ticker']==stock_ticker]['quantity'].iloc[0])
                    with st.form("sell_form"):
                        sq = st.number_input("Satılacak Adet", min_value=1, max_value=curr_q, value=curr_q)
                        sp = st.number_input("Fiyat", value=price)
                        if st.form_submit_button("SATIŞI TAMAMLA"):
                            _, _, err = sell_from_portfolio(stock_ticker, sp, sq)
                            if not err:
                                total_return = (sp * sq) * (1 - COMMISSION_RATE)
                                update_bankroll(bankroll + total_return)
                                st.success(f"Satış yapıldı. Komisyon kesildikten sonra kasaya giren: {total_return:.2f} TL.")
                                st.rerun()
                            else: st.error(err)
                else: st.info("Hisse portföyde yok.")

            # --- GRAFİKLER ---
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05, 
                               row_heights=[0.5, 0.25, 0.25],
                               subplot_titles=("Fiyat & Bollinger Bantlar", "RSI (14)", "MACD"))
            
            # 1. Fiyat & Bollinger
            fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name='Fiyat', line=dict(color='#3498db')), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['Upper_BB'], name='BB Üst', line=dict(color='#e74c3c', dash='dot')), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['Lower_BB'], name='BB Alt', line=dict(color='#2ecc71', dash='dot')), row=1, col=1)
            
            # 2. RSI
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI', line=dict(color='#9b59b6')), row=2, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
            
            # 3. MACD
            # Histogram
            fig.add_trace(go.Bar(x=df.index, y=df['MACD'] - df['MACD_Signal'], name='Histogram', marker_color='gray'), row=3, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], name='MACD', line=dict(color='#f1c40f')), row=3, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MACD_Signal'], name='Sinyal', line=dict(color='#ecf0f1')), row=3, col=1)

            fig.update_layout(height=800, template="plotly_dark", showlegend=True, margin=dict(l=20, r=20, t=50, b=20))
            
            # Zaman Filtreleri (Range Selector)
            fig.update_xaxes(
                rangeslider_visible=False,
                rangeselector=dict(
                    buttons=list([
                        dict(count=1, label="1A", step="month", stepmode="backward"),
                        dict(count=3, label="3A", step="month", stepmode="backward"),
                        dict(count=6, label="6A", step="month", stepmode="backward"),
                        dict(count=1, label="1Y", step="year", stepmode="backward"),
                        dict(count=3, label="3Y", step="year", stepmode="backward"),
                        dict(step="all", label="Tümü")
                    ]),
                    bgcolor="#1e2130",
                    activecolor="#3498db",
                    font=dict(color="white", size=11)
                ),
                row=1, col=1
            )
            
            st.plotly_chart(fig, use_container_width=True)

    except Exception as e: st.error(f"Sistem Hatası: {str(e)}")

with tab2:
    st.subheader("📜 Tüm İşlem Geçmişi")
    hist_df = get_all_history()
    if not hist_df.empty:
        st.dataframe(hist_df, use_container_width=True, hide_index=True)
        # Tab 2 silme alanı
        st.markdown("---")
        st.write("🗑️ **İşlem Sil**")
        del_id = st.selectbox("Silinecek İşlem ID Seçin", hist_df['ID'].tolist())
        if st.button("Seçili İşlemi Kalıcı Olarak Sil"):
            delete_transaction(del_id)
    else: st.info("İşlem kaydı yok.")

st.sidebar.markdown("---")
st.sidebar.caption("v2.6 | İşlem Silme Özelliği Aktif")
