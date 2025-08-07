import pandas as pd
import streamlit as st
import plotly.express as px
import tempfile
import requests
import io
from datetime import datetime
from xhtml2pdf import pisa

st.set_page_config(page_title="Dashboard Penjualan", layout="wide")

# --- FETCH CSV DARI GITHUB DENGAN CACHE ---
GITHUB_CSV_URL = "https://raw.githubusercontent.com/zuied/python-BI/main/dashboard_penjualan/penjualan.csv"

@st.cache_data(ttl=300)
def fetch_github_csv():
    try:
        r = requests.get(GITHUB_CSV_URL)
        if r.status_code == 200:
            return r.content
        else:
            st.warning("⚠️ Gagal mengunduh data dari GitHub.")
            return None
    except Exception as e:
        st.error(f"❌ Error fetch GitHub CSV: {e}")
        return None

csv_content = fetch_github_csv()
df = pd.read_csv(io.BytesIO(csv_content)) if csv_content else pd.DataFrame()

# Tombol manual refresh
if st.button("🔄 Refresh Data dari GitHub"):
    st.cache_data.clear()
    st.rerun()

# --- VALIDASI KOLON ---
if 'tanggal' not in df.columns:
    st.error("❌ File CSV dari GitHub tidak memiliki kolom 'tanggal'. Periksa struktur file.")
    st.stop()

# --- DATA CLEANING ---
df['tanggal'] = pd.to_datetime(df['tanggal'], errors='coerce')
df['qty'] = pd.to_numeric(df['qty'], errors='coerce')
df['harga'] = pd.to_numeric(df['harga'], errors='coerce')

if 'total' not in df.columns or df['total'].dropna().astype(str).str.contains(r'[^0-9]').any():
    df['total'] = df['qty'] * df['harga']
else:
    df['total'] = df['total'].astype(str).str.replace('.', '', regex=False)
    df['total'] = pd.to_numeric(df['total'], errors='coerce')

min_date = df['tanggal'].min()
max_date = df['tanggal'].max()

# --- FILTER TANGGAL ---
tanggal_awal, tanggal_akhir = st.sidebar.date_input(
    "Pilih Rentang Tanggal",
    [min_date, max_date],
    min_value=min_date,
    max_value=max_date
)
df = df[(df['tanggal'] >= pd.to_datetime(tanggal_awal)) & (df['tanggal'] <= pd.to_datetime(tanggal_akhir))]
df = df.dropna(subset=['tanggal'])
df['bulan'] = df['tanggal'].dt.to_period('M').astype(str)

# --- SIDEBAR FILTER ---
st.sidebar.header("📂 Filter Data")
wilayah_options = df['wilayah'].dropna().unique().tolist()
wilayah = st.sidebar.multiselect("Pilih Wilayah", wilayah_options, default=wilayah_options)
kategori_options = df['kategori'].dropna().unique().tolist()
kategori = st.sidebar.multiselect("Pilih Kategori", kategori_options, default=kategori_options)

# --- FILTER DATA ---
df_filter = df[
    df['wilayah'].isin(wilayah) &
    df['kategori'].isin(kategori)
]
df_filter['total'] = pd.to_numeric(df_filter['total'], errors='coerce').fillna(0)

if df_filter.empty:
    st.warning("❗Tidak ada data ditemukan dengan filter yang dipilih.")
    st.stop()

# --- KPI ---
total_penjualan = df_filter['total'].sum()
total_transaksi = len(df_filter)
produk_terlaris = (
    df_filter.groupby('produk')['total'].sum().sort_values(ascending=False).head(1).index[0]
    if not df_filter.empty else "Tidak ada"
)

st.title("📊 Dashboard Penjualan")
col1, col2, col3 = st.columns(3)
col1.metric("💰 Total Penjualan", f"Rp {total_penjualan:,.0f}")
col2.metric("🧾 Jumlah Transaksi", total_transaksi)
col3.metric("🔥 Produk Terlaris", produk_terlaris)

st.markdown("---")

# --- SISA STOK ---
st.markdown("---")
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

# --- GRAFIK ---
penjualan_bulanan = df_filter.groupby('bulan')['total'].sum().reset_index()
fig1 = px.line(penjualan_bulanan, x='bulan', y='total', markers=True, title='📈 Penjualan per Bulan')
st.plotly_chart(fig1, use_container_width=True)

kategori_chart = df_filter.groupby('kategori')['total'].sum().reset_index()
fig2 = px.pie(kategori_chart, names='kategori', values='total', title='📊 Penjualan per Kategori')
st.plotly_chart(fig2, use_container_width=True)

wilayah_chart = df_filter.groupby('wilayah')['total'].sum().reset_index()
fig3 = px.bar(wilayah_chart, x='wilayah', y='total', title='🌍 Penjualan per Wilayah')
st.plotly_chart(fig3, use_container_width=True)

# --- TOP 10 PRODUK ---
df_filter['total'] = pd.to_numeric(df_filter['total'], errors='coerce')
df_filter = df_filter.dropna(subset=['total'])

if df_filter.empty:
    st.warning("Tidak ada data untuk ditampilkan di grafik produk terlaris.")
else:
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

# --- DOWNLOAD ---
st.subheader("⬇️ Download Data")
excel_buffer = io.BytesIO()
df_filter.to_excel(excel_buffer, index=False, sheet_name="Penjualan")
st.download_button(
    label="Download Excel",
    data=excel_buffer.getvalue(),
    file_name="data_penjualan.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# --- EXPORT PDF ---
def df_to_pdf(df_in):
    html = df_in.to_html(index=False)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pisa.CreatePDF(html, dest=tmp)
    return tmp.name

if st.button("Export ke PDF"):
    pdf_file = df_to_pdf(df)
    with open(pdf_file, "rb") as f:
        st.download_button("Download PDF", data=f, file_name="laporan_penjualan.pdf", mime="application/pdf")
