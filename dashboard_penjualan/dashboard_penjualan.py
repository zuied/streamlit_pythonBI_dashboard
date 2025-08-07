import pandas as pd
import streamlit as st
import plotly.express as px
import tempfile
from xhtml2pdf import pisa
import os
import io
from datetime import datetime

# --- CONFIG ---
st.set_page_config(page_title="Dashboard Penjualan", layout="wide")
GITHUB_CSV_URL = "https://raw.githubusercontent.com/zuied/streamlit_pythonBI_dashboard/main/dashboard_penjualan/penjualan.csv"
VERSI_FOLDER = "data_versions"
os.makedirs(VERSI_FOLDER, exist_ok=True)

# --- GITHUB LOADER ---
@st.cache_data(ttl=300)
def load_data_from_github():
    try:
        df = pd.read_csv(GITHUB_CSV_URL)
        return df
    except Exception as e:
        st.error(f"❌ Gagal memuat data dari GitHub: {e}")
        return pd.DataFrame()

# --- REFRESH BUTTON ---
if st.sidebar.button("🔄 Refresh Data dari GitHub"):
    st.cache_data.clear()
    st.rerun()

# --- UPLOAD FILE ---
st.sidebar.markdown("### 📤 Upload File CSV")
if 'last_file' not in st.session_state:
    st.session_state['last_file'] = None

uploaded_file = st.sidebar.file_uploader("Unggah file penjualan.csv", type=["csv"])
if uploaded_file is not None:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"data_{timestamp}.csv"
    file_path = os.path.join(VERSI_FOLDER, filename)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getvalue())
    st.session_state['last_file'] = filename
    st.success(f"✅ File berhasil diunggah sebagai: {filename}")

# --- PILIH SUMBER DATA ---
st.sidebar.markdown("### 📂 Pilih Sumber Data")
file_list = sorted(os.listdir(VERSI_FOLDER), reverse=True)
if st.session_state['last_file'] and st.session_state['last_file'] not in file_list:
    file_list.insert(0, st.session_state['last_file'])

use_github = st.sidebar.checkbox("Gunakan data dari GitHub (default)", value=True)

# --- LOAD DATA ---
if use_github:
    df = load_data_from_github()
    data_source = "GitHub"
else:
    if not file_list:
        st.warning("❗ Belum ada file CSV lokal yang tersedia.")
        st.stop()
    selected_file = st.sidebar.selectbox("Pilih file lokal:", file_list, index=0)
    file_path = os.path.join(VERSI_FOLDER, selected_file)
    df = pd.read_csv(file_path)
    data_source = selected_file

# --- DEBUG CEK DATA FANTA ---
fanta_debug = df[df['produk'].str.contains("Fanta Stroberi 500ml", case=False, na=False)]
st.sidebar.write("🧪 Stok Fanta Stroberi 500ml:", fanta_debug[['produk', 'stok_awal']])

# --- CLEANING ---
df['tanggal'] = pd.to_datetime(df['tanggal'], errors='coerce')
df['qty'] = pd.to_numeric(df['qty'], errors='coerce')
df['harga'] = pd.to_numeric(df['harga'], errors='coerce')

if 'total' not in df.columns or df['total'].dropna().astype(str).str.contains(r'[^0-9]').any():
    df['total'] = df['qty'] * df['harga']
else:
    df['total'] = df['total'].astype(str).str.replace('.', '', regex=False)
    df['total'] = pd.to_numeric(df['total'], errors='coerce')

# --- FILTER TANGGAL ---
min_date = df['tanggal'].min()
max_date = df['tanggal'].max()
tanggal_awal, tanggal_akhir = st.sidebar.date_input(
    "Pilih Rentang Tanggal",
    [min_date, max_date],
    min_value=min_date,
    max_value=max_date
)
df = df[(df['tanggal'] >= pd.to_datetime(tanggal_awal)) & (df['tanggal'] <= pd.to_datetime(tanggal_akhir))]
df = df.dropna(subset=['tanggal'])
df['bulan'] = df['tanggal'].dt.to_period('M').astype(str)

# --- FILTER SIDEBAR ---
st.sidebar.header("📂 Filter Data")
wilayah_options = df['wilayah'].dropna().unique().tolist()
wilayah = st.sidebar.multiselect("Pilih Wilayah", wilayah_options, default=wilayah_options)
kategori_options = df['kategori'].dropna().unique().tolist()
kategori = st.sidebar.multiselect("Pilih Kategori", kategori_options, default=kategori_options)

# --- FILTER DATA ---
df_filter = df[df['wilayah'].isin(wilayah) & df['kategori'].isin(kategori)]
df_filter['total'] = pd.to_numeric(df_filter['total'], errors='coerce').fillna(0)

if df_filter.empty:
    st.warning("❗ Tidak ada data ditemukan dengan filter yang dipilih.")
    st.stop()

# === KPI ===
total_penjualan = df_filter['total'].sum()
total_transaksi = len(df_filter)
produk_terlaris = (
    df_filter.groupby('produk')['total'].sum().sort_values(ascending=False).head(1).index[0]
    if not df_filter.empty else "Tidak ada"
)

st.title("📊 Dashboard Penjualan")
st.caption(f"📁 Sumber Data: {data_source}")
col1, col2, col3 = st.columns(3)
col1.metric("💰 Total Penjualan", f"Rp {total_penjualan:,.0f}")
col2.metric("🧾 Jumlah Transaksi", total_transaksi)
col3.metric("🔥 Produk Terlaris", produk_terlaris)

# === SISA STOK ===
st.subheader("📦 Informasi Sisa Stok per Produk")
terjual = df.groupby('produk')['qty'].sum()
stok_awal = df.groupby('produk')['stok_awal'].first()
sisa_stok = stok_awal - terjual
stok_df = pd.DataFrame({
    'Stok Awal': stok_awal,
    'Terjual': terjual,
    'Sisa Stok': sisa_stok
}).fillna(0).astype(int)

st.dataframe(stok_df)

stok_habis = stok_df[stok_df['Sisa Stok'] <= 5]
if not stok_habis.empty:
    st.warning("⚠️ Ada produk dengan stok menipis (≤ 5 unit)")
    st.dataframe(stok_habis)

# === GRAFIK ===
penjualan_bulanan = df_filter.groupby('bulan')['total'].sum().reset_index()
fig1 = px.line(penjualan_bulanan, x='bulan', y='total', markers=True, title='📈 Penjualan per Bulan')
st.plotly_chart(fig1, use_container_width=True)

kategori_chart = df_filter.groupby('kategori')['total'].sum().reset_index()
fig2 = px.pie(kategori_chart, names='kategori', values='total', title='📊 Penjualan per Kategori')
st.plotly_chart(fig2, use_container_width=True)

wilayah_chart = df_filter.groupby('wilayah')['total'].sum().reset_index()
fig3 = px.bar(wilayah_chart, x='wilayah', y='total', title='🌍 Penjualan per Wilayah')
st.plotly_chart(fig3, use_container_width=True)

# === TOP 10 PRODUK ===
top_produk = (
    df_filter.groupby('produk')['total'].sum()
    .sort_values(ascending=False)
    .head(10)
    .reset_index()
)
fig4 = px.bar(top_produk, x='produk', y='total', title='🏆 Top 10 Produk Terlaris')
fig4.update_traces(texttemplate='%{y:,}', textposition='outside')
fig4.update_layout(
    yaxis_tickformat=',',
    yaxis_title='Total Penjualan (Rp)',
    xaxis_title='Produk',
    title_x=0.5
)
st.plotly_chart(fig4, use_container_width=True)

# === DOWNLOAD EXCEL ===
st.subheader("⬇️ Download Data")
excel_buffer = io.BytesIO()
df_filter.to_excel(excel_buffer, index=False, sheet_name="Penjualan")
st.download_button(
    label="Download Excel",
    data=excel_buffer.getvalue(),
    file_name="data_penjualan.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# === EXPORT PDF ===
def df_to_pdf(df_in):
    html = df_in.to_html(index=False)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pisa.CreatePDF(html, dest=tmp)
    return tmp.name

if st.button("Export ke PDF"):
    pdf_file = df_to_pdf(df_filter)
    with open(pdf_file, "rb") as f:
        st.download_button("Download PDF", data=f, file_name="laporan_penjualan.pdf", mime="application/pdf")
