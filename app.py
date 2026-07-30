import streamlit as st
import pandas as pd
import plotly.express as px

# --- PENGATURAN HALAMAN ---
st.set_page_config(page_title="PFI Mega Life Automation Dashboard", layout="wide", page_icon="📊")

# --- 1. FUNGSI LOAD & CLEAN DATA (ETL PIPELINE) ---
@st.cache_data
def load_and_clean_data():
    try:
        # Load 3 Sheet dari Excel
        leads = pd.read_excel('data.xlsx', sheet_name='Data Leads')
        seller = pd.read_excel('data.xlsx', sheet_name='Data Seller')
        branch = pd.read_excel('data.xlsx', sheet_name='Data Branch')
        
        # Rename Kolom berdasarkan urutan index (Menghindari error nama kolom sistem yang berantakan)
        leads.columns = ['Leads_ID', 'Creation_Date', 'IS_Name', 'RH_Name', 'Branch_Code', 'Seller', 'Customer_Name', 'Jenis_Leads']
        seller.columns = ['NIP', 'JobTitle', 'Branch_Name_Seller', 'Area_Name_Seller', 'Regional_Name_Seller', 'Seller_Name']
        branch.columns = ['Branch_Code', 'Branch_Name', 'Area_Name', 'Regional_Name', 'BranchClass']
        
        # Formatting Tanggal
        leads['Creation_Date'] = pd.to_datetime(leads['Creation_Date'], errors='coerce')
        
        # 🚨 DATA STANDARDIZATION: Menghilangkan anomali '.0' pada Branch Code 🚨
        leads['Branch_Code'] = leads['Branch_Code'].astype(str).str.replace('.0', '', regex=False)
        branch['Branch_Code'] = branch['Branch_Code'].astype(str).str.replace('.0', '', regex=False)
        
        # 🚨 DATA STANDARDIZATION: Menyamakan format nama Seller (Trim & Uppercase) 🚨
        leads['Seller'] = leads['Seller'].astype(str).str.strip().str.upper()
        seller['Seller_Name'] = seller['Seller_Name'].astype(str).str.strip().str.upper()
        
        # MERGE DATA (Star Schema Logic: Fact Table -> Dimension Tables)
        df = pd.merge(leads, branch, on='Branch_Code', how='left', suffixes=('_leads', '_branch'))
        df = pd.merge(df, seller, left_on='Seller', right_on='Seller_Name', how='left')
        
        return df
    except Exception as e:
        st.error(f"Error membaca file: {e}. Pastikan file bernama 'data.xlsx'")
        return pd.DataFrame()

df = load_and_clean_data()

if not df.empty:
    # --- JUDUL DASHBOARD ---
    st.title("📊 PFI Mega Life: Bancassurance Automation Dashboard")
    st.markdown("**Analisis Distribusi Leads, Workload Ratio, & Lead-to-Role Alignment | Juli 2026**")

    # --- 2. SIDEBAR FILTERS (INTERACTIVE SLICERS) ---
    st.sidebar.header("🔍 Filter Konteks Bisnis")
    
    regions = sorted(df['Regional_Name'].dropna().unique().tolist())
    sel_region = st.sidebar.multiselect("Pilih Regional:", regions, default=regions)
    
    lead_types = sorted(df['Jenis_Leads'].dropna().unique().tolist())
    sel_lead = st.sidebar.multiselect("Pilih Jenis Leads:", lead_types, default=lead_types)
    
    job_titles = sorted(df['JobTitle'].dropna().unique().tolist())
    sel_job = st.sidebar.multiselect("Pilih Jabatan Seller:", job_titles, default=job_titles)

    # Apply Filter ke Dataframe
    df_filt = df[
        (df['Regional_Name'].isin(sel_region)) & 
        (df['Jenis_Leads'].isin(sel_lead)) & 
        (df['JobTitle'].isin(sel_job))
    ]

    # --- 3. KPI CARDS (METRIK UTAMA) ---
    c1, c2, c3 = st.columns(3)
    total_leads = len(df_filt)
    active_sellers = df_filt['Seller_Name'].nunique()
    avg_wl = total_leads / max(1, active_sellers) # Mencegah divide by zero
    
    c1.metric("Total Leads Masuk", f"{total_leads:,}")
    c2.metric("Total Seller Aktif", f"{active_sellers}")
    c3.metric("Rasio Beban Kerja (Leads/Seller)", f"{avg_wl:.1f}")

    st.markdown("---")

    # --- 4. VISUALISASI DATA ---
    colA, colB = st.columns(2)
    with colA:
        st.subheader("Distribusi Leads per Kelas Cabang")
        fig1 = px.bar(df_filt, x='BranchClass', color='BranchClass', 
                      title="Apakah Cabang Kecil (S/XS) Kehujanan Leads?",
                      color_discrete_sequence=px.colors.qualitative.Set2,
                      category_orders={'BranchClass': ['XL', 'L', 'M', 'S', 'XS']})
        st.plotly_chart(fig1, use_container_width=True)

    with colB:
        st.subheader("Komposisi Jenis Leads")
        fig2 = px.pie(df_filt, names='Jenis_Leads', hole=0.4,
                      title="Dominasi Bank Leads vs Cross-Sell/Renewal",
                      color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Tren Harian Penciptaan Leads")
    daily = df_filt.groupby(df_filt['Creation_Date'].dt.date).size().reset_index(name='Total')
    fig3 = px.line(daily, x='Creation_Date', y='Total', markers=True, title="Kapan Leads Paling Banyak Masuk?", line_shape='spline')
    st.plotly_chart(fig3, use_container_width=True)

    # LEADERBOARD SELLER
    st.subheader("🏆 Top 15 Seller dengan Beban Kerja Tertinggi (Rawan Overload)")
    top_sell = df_filt.groupby(['Seller_Name', 'JobTitle', 'Branch_Name']).size().reset_index(name='Total Leads')
    top_sell = top_sell.sort_values(by='Total Leads', ascending=False).head(15)
    st.dataframe(top_sell, use_container_width=True, hide_index=True)

    # --- 5. DYNAMIC BUSINESS INSIGHTS (THE KILLER FEATURE) ---
    
    # Logic Insight 1: Top 2 Seller
    seller_wl = df_filt.groupby('Seller_Name').size().reset_index(name='Total')
    seller_wl = seller_wl.sort_values('Total', ascending=False)
    top_sellers = seller_wl['Seller_Name'].head(2).tolist()
    
    if len(top_sellers) >= 2:
        dynamic_sellers = f"*{top_sellers[0].title()}* dan *{top_sellers[1].title()}*"
    elif len(top_sellers) == 1:
        dynamic_sellers = f"*{top_sellers[0].title()}*"
    else:
        dynamic_sellers = "*beberapa seller*"

    # Logic Insight 2: Rasio Beban Kerja per Branch Class (Auto-Routing)
    class_metrics = df_filt.groupby('BranchClass').agg(
        Total=('Leads_ID', 'count'),
        Sellers=('Seller_Name', 'nunique')
    ).reset_index()
    
    class_metrics['Sellers'] = class_metrics['Sellers'].replace(0, 1)
    class_metrics['Ratio'] = class_metrics['Total'] / class_metrics['Sellers']
    
    if not class_metrics.empty:
        overloaded_class = class_metrics.loc[class_metrics['Ratio'].idxmax(), 'BranchClass']
        overloaded_ratio = class_metrics['Ratio'].max()
        underloaded_class = class_metrics.loc[class_metrics['Ratio'].idxmin(), 'BranchClass']
    else:
        overloaded_class, underloaded_class, overloaded_ratio = "Tertentu", "Lainnya", 0

    # Logic Insight 3: Lead-to-Role Alignment (RFRM vs MFRM)
    if total_leads > 0:
        top_lead = df_filt['Jenis_Leads'].value_counts().index[0]
        top_lead_pct = (df_filt['Jenis_Leads'].value_counts().iloc[0] / total_leads) * 100
        top_job = df_filt['JobTitle'].value_counts().index[0]
        top_area = df_filt['Area_Name'].value_counts().index[0]
        
        # Context-Aware Advice berdasarkan Jabatan
        if top_job == 'MFRM':
            role_advice = f"Karena didominasi oleh **MFRM (Mega First / Priority)**, pastikan *{top_lead}* yang masuk adalah nasabah *High-Net-Worth*. Jika ini adalah *Bank Leads* reguler, terjadi inefisiensi kapasitas. Sistem harus mem-bypass MFRM dan melemparnya ke antrian RFRM."
        else:
            role_advice = f"Karena didominasi oleh **RFRM (Retail)**, optimalkan *script cross-selling* produk mass-market agar konversi *{top_lead}* meningkat sebelum menjadi *cold lead*."
    else:
        top_lead, top_lead_pct, top_area, top_job, role_advice = "Data Kosong", 0, "Area Tertentu", "Seller", "Tidak ada data."

    # Tampilkan Insight Dinamis ke Layar
    st.success(f"""
    💡 **Actionable Business Insights & Rekomendasi Automasi (Real-Time Context-Aware):**
    
    1. **Workload Imbalance (SDM):** Terdeteksi seller seperti {dynamic_sellers} menampung volume leads yang sangat tinggi (anomali) dibandingkan rekan-rekannya di area yang sama berdasarkan filter yang Anda pilih.
    
    2. **Rekomendasi Auto-Routing (Spill-Over System):** Berdasarkan rasio beban kerja saat ini, **Cabang Kelas {overloaded_class}** mengalami *overload* (rata-rata **{overloaded_ratio:.1f} leads/seller**). 
    👉 *Sistem Automasi:* Disarankan membuat *rule-based routing* di mana jika *queue* di Kelas {overloaded_class} penuh, sistem otomatis melempar (*spill-over*) leads ke **Cabang Kelas {underloaded_class}** yang saat ini rasio bebannya lebih rendah dalam regional yang sama.
    
    3. **Lead-to-Role Alignment & Trigger API:** Pada filter saat ini, **{top_lead}** mendominasi sebesar **{top_lead_pct:.1f}%** dan paling banyak dipegang oleh jabatan **{top_job}** di **{top_area}**. 
    👉 *Analisis Strategis:* {role_advice}
    👉 *Sistem Automasi:* Buat *Trigger API* (Email/WA Blast otomatis) yang mengirimkan *daily reminder* berisi daftar prospek prioritas ke para {top_job} di {top_area} guna mempercepat *closing rate*.
    """)

else:
    st.warning("Data tidak ditemukan atau file belum dimuat dengan benar.")