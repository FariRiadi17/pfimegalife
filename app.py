import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- PENGATURAN HALAMAN ---
st.set_page_config(page_title="PFI Mega Life - Branch Performance Dashboard", layout="wide", page_icon="📊")

# --- 1. FUNGSI LOAD & CLEAN DATA (ETL PIPELINE) ---
@st.cache_data
def load_and_clean_data():
    try:
        # Load 3 Sheet dari Excel
        leads = pd.read_excel('data.xlsx', sheet_name='Data Leads')
        seller = pd.read_excel('data.xlsx', sheet_name='Data Seller')
        branch = pd.read_excel('data.xlsx', sheet_name='Data Branch')

        # Rename Kolom berdasarkan urutan index
        leads.columns = ['Leads_ID', 'Creation_Date', 'IS_Name', 'RH_Name', 'Branch_Code', 'Seller', 'Customer_Name', 'Jenis_Leads']
        seller.columns = ['NIP', 'JobTitle', 'Branch_Name_Seller', 'Area_Name_Seller', 'Regional_Name_Seller', 'Seller_Name']
        branch.columns = ['Branch_Code', 'Branch_Name', 'Area_Name', 'Regional_Name', 'BranchClass']

        # Formatting Tanggal
        leads['Creation_Date'] = pd.to_datetime(leads['Creation_Date'], errors='coerce')

        # 🚨 DATA STANDARDIZATION 🚨
        leads['Leads_ID'] = leads['Leads_ID'].astype(str).str.replace('.0', '', regex=False).str.strip()
        leads['Branch_Code'] = leads['Branch_Code'].astype(str).str.replace('.0', '', regex=False).str.strip()
        branch['Branch_Code'] = branch['Branch_Code'].astype(str).str.replace('.0', '', regex=False).str.strip()

        leads['Seller'] = leads['Seller'].astype(str).str.strip().str.upper()
        seller['Seller_Name'] = seller['Seller_Name'].astype(str).str.strip().str.upper()

        # MERGE DATA
        df = pd.merge(leads, branch, on='Branch_Code', how='left', suffixes=('_leads', '_branch'))
        df = pd.merge(df, seller, left_on='Seller', right_on='Seller_Name', how='left')
        
        return df, branch
    except Exception as e:
        st.error(f"Error membaca file: {e}. Pastikan file bernama 'data.xlsx' dan memiliki 3 sheet yang sesuai.")
        return pd.DataFrame(), pd.DataFrame()

df, master_branch = load_and_clean_data()

if not df.empty:
    # --- JUDUL DASHBOARD ---
    st.title("📊 PFI Mega Life: Branch Performance Intelligence")
    st.markdown("Analisis Performa Branch, Distribusi Leads, & Workload Ratio | **Q4 2025 - Sekarang**")

        # ====================================================================
    # --- 2. FILTER TANGGAL (Q4 2025 - SEKARANG) - FIXED ---
    # ====================================================================
    st.sidebar.header("📅 Rentang Periode Analisis")
    
    import datetime
    
    # Ambil tanggal min dan max dari data (gunakan dropna agar aman dari error NaT)
    valid_dates = df['Creation_Date'].dropna()
    if not valid_dates.empty:
        min_date = valid_dates.min().date()
        max_date = valid_dates.max().date()
    else:
        # Fallback jika tidak ada tanggal valid
        min_date = datetime.date.today()
        max_date = datetime.date.today()

    # Target default start adalah 1 Oktober 2025
    target_start = datetime.date(2025, 10, 1)
    
    # 🚨 FIX: Pastikan default_start TIDAK LEBIH KECIL dari min_date data
    # Jika data pertama kali muncul di November 2025, default_start otomatis geser ke November.
    default_start = max(min_date, target_start)
    default_end = max_date
    
    # Fallback jaga-jaga jika default_start > default_end (misal data kosong/sangat aneh)
    if default_start > default_end:
        default_start = min_date
        default_end = max_date

    date_range = st.sidebar.date_input(
        "Pilih Periode:",
        value=(default_start, default_end),
        min_value=min_date,
        max_value=max_date
    )
    
    if len(date_range) == 2:
        start_date, end_date = date_range
        df = df[(df['Creation_Date'].dt.date >= start_date) & (df['Creation_Date'].dt.date <= end_date)]
    # ====================================================================
    # --- 3. CASCADING FILTERS (Region -> Area -> Branch) ---
    # ====================================================================
    st.sidebar.header("🔍 Filter Hierarki Wilayah")
    
    # Level 1: Region
    regions = sorted(df['Regional_Name'].dropna().unique().tolist())
    sel_region = st.sidebar.multiselect("🏢 Pilih Regional:", regions, default=regions)
    
    # Level 2: Area (tergantung Region yang dipilih)
    df_region = df[df['Regional_Name'].isin(sel_region)]
    areas = sorted(df_region['Area_Name'].dropna().unique().tolist())
    sel_area = st.sidebar.multiselect("📍 Pilih Area:", areas, default=areas)
    
    # Level 3: Branch (tergantung Area yang dipilih)
    df_area = df_region[df_region['Area_Name'].isin(sel_area)]
    branches = sorted(df_area['Branch_Name'].dropna().unique().tolist())
    sel_branch = st.sidebar.multiselect("🏬 Pilih Branch:", branches, default=branches)
    
    # Apply Filter Final
    df_filt = df_area[df_area['Branch_Name'].isin(sel_branch)]

    # ====================================================================
    # --- 4. KPI CARDS (METRIK UTAMA) ---
    # ====================================================================
    c1, c2, c3, c4 = st.columns(4)
    total_leads = len(df_filt)
    active_sellers = df_filt['Seller_Name'].nunique()
    total_branches = df_filt['Branch_Name'].nunique()
    avg_wl = total_leads / max(1, active_sellers)
    
    c1.metric("📥 Total Leads Masuk", f"{total_leads:,}")
    c2.metric("👤 Total Seller Aktif", f"{active_sellers}")
    c3.metric("🏬 Branch Aktif", f"{total_branches}")
    c4.metric("⚖️ Rasio Beban Kerja", f"{avg_wl:.1f} leads/seller")
    
    st.markdown("---")

    # ====================================================================
    # --- 5. CHART: TOTAL LEADS, SELLER AKTIF, RASIO BEBAN KERJA ---
    # ====================================================================
    st.subheader("📈 Tren Metrik Utama (Bulanan)")
    
    # Agregasi bulanan
    df_filt_copy = df_filt.copy()
    df_filt_copy['Month'] = df_filt_copy['Creation_Date'].dt.to_period('M')
    
    monthly_metrics = df_filt_copy.groupby('Month').agg(
        Total_Leads=('Leads_ID', 'count'),
        Active_Sellers=('Seller_Name', 'nunique')
    ).reset_index()
    monthly_metrics['Month'] = monthly_metrics['Month'].astype(str)
    monthly_metrics['Workload_Ratio'] = monthly_metrics['Total_Leads'] / monthly_metrics['Active_Sellers'].replace(0, 1)
    
    col_chart1, col_chart2, col_chart3 = st.columns(3)
    
    with col_chart1:
        fig_leads = px.bar(monthly_metrics, x='Month', y='Total_Leads', 
                          title="Total Leads per Bulan",
                          color_discrete_sequence=['#636EFA'])
        st.plotly_chart(fig_leads, use_container_width=True)
    
    with col_chart2:
        fig_sellers = px.line(monthly_metrics, x='Month', y='Active_Sellers', 
                             title="Seller Aktif per Bulan",
                             markers=True, color_discrete_sequence=['#EF553B'])
        st.plotly_chart(fig_sellers, use_container_width=True)
    
    with col_chart3:
        fig_ratio = px.bar(monthly_metrics, x='Month', y='Workload_Ratio', 
                          title="Rasio Beban Kerja per Bulan",
                          color_discrete_sequence=['#00CC96'])
        st.plotly_chart(fig_ratio, use_container_width=True)

    st.markdown("---")

    # ====================================================================
    # --- 6. ANALISIS PER BRANCH: TOP 10 SELLER & LEADS ---
    # ====================================================================
    st.header("🏆 Analisis Performa (Berdasarkan Filter)")
    
    tab1, tab2, tab3 = st.tabs(["👑 Top 10 Seller", "📊 Top 10 Branch by Leads", "⚠️ Branch Tanpa Leads"])
    
    with tab1:
        st.subheader("Top 10 Seller dengan Leads Terbanyak")
        top_sellers = df_filt.groupby(['Seller_Name', 'Branch_Name', 'JobTitle']).agg(
            Total_Leads=('Leads_ID', 'count')
        ).reset_index().sort_values('Total_Leads', ascending=False).head(10)
        
        fig_top_seller = px.bar(top_sellers, x='Seller_Name', y='Total_Leads',
                               color='Branch_Name',
                               title="Top 10 Seller Produktif",
                               labels={'Seller_Name': 'Nama Seller', 'Total_Leads': 'Jumlah Leads'},
                               text='Total_Leads')
        fig_top_seller.update_traces(textposition='outside')
        st.plotly_chart(fig_top_seller, use_container_width=True)
        st.dataframe(top_sellers.rename(columns={
            'Seller_Name': 'Nama Seller', 'Branch_Name': 'Cabang', 
            'JobTitle': 'Jabatan', 'Total_Leads': 'Total Leads'
        }), use_container_width=True, hide_index=True)
    
    with tab2:
        st.subheader("Top 10 Branch dengan Leads Terbanyak")
        top_branches = df_filt.groupby(['Branch_Name', 'Area_Name', 'Regional_Name']).agg(
            Total_Leads=('Leads_ID', 'count'),
            Active_Sellers=('Seller_Name', 'nunique')
        ).reset_index()
        top_branches['Workload_Ratio'] = (top_branches['Total_Leads'] / top_branches['Active_Sellers'].replace(0, 1)).round(1)
        top_branches = top_branches.sort_values('Total_Leads', ascending=False).head(10)
        
        fig_top_branch = px.bar(top_branches, x='Branch_Name', y='Total_Leads',
                               color='Area_Name',
                               title="Top 10 Branch Penghasil Leads",
                               labels={'Branch_Name': 'Cabang', 'Total_Leads': 'Jumlah Leads'},
                               text='Total_Leads')
        fig_top_branch.update_traces(textposition='outside')
        st.plotly_chart(fig_top_branch, use_container_width=True)
        st.dataframe(top_branches.rename(columns={
            'Branch_Name': 'Cabang', 'Area_Name': 'Area', 'Regional_Name': 'Regional',
            'Total_Leads': 'Total Leads', 'Active_Sellers': 'Seller Aktif',
            'Workload_Ratio': 'Rasio Beban Kerja'
        }), use_container_width=True, hide_index=True)
    
    with tab3:
        st.subheader("⚠️ Branch yang Belum Menghasilkan Leads (Zero-Performance Branches)")
        
        # Cari branch yang ada di master data tapi tidak ada leads-nya di filter saat ini
        active_branch_codes = df_filt['Branch_Code'].dropna().unique()
        all_branches_in_filter = master_branch[
            (master_branch['Regional_Name'].isin(sel_region)) &
            (master_branch['Area_Name'].isin(sel_area)) &
            (master_branch['Branch_Name'].isin(sel_branch))
        ]
        
        zero_leads_branches = all_branches_in_filter[~all_branches_in_filter['Branch_Code'].isin(active_branch_codes)]
        
        if not zero_leads_branches.empty:
            st.warning(f"⚠️ Ditemukan **{len(zero_leads_branches)} branch** yang belum menghasilkan leads sama sekali pada periode & filter yang dipilih.")
            st.dataframe(zero_leads_branches.rename(columns={
                'Branch_Code': 'Kode Cabang', 'Branch_Name': 'Nama Cabang',
                'Area_Name': 'Area', 'Regional_Name': 'Regional', 'BranchClass': 'Kelas Cabang'
            }), use_container_width=True, hide_index=True)
            
            # Evaluasi & Rekomendasi
            st.markdown("### 💡 Evaluasi & Rekomendasi Strategis untuk Zero-Performance Branches:")
            
            # Analisis kelas cabang yang tidak menghasilkan leads
            class_dist = zero_leads_branches['BranchClass'].value_counts()
            top_class = class_dist.index[0] if not class_dist.empty else "Berbagai Kelas"
            
            st.error(f"""
            **🔍 Root Cause Analysis:**
            1. **Dominansi Kelas Cabang:** Mayoritas branch tanpa leads adalah kelas **{top_class}**. Ini mengindikasikan bahwa cabang dengan kelas ini mungkin memiliki keterbatasan SDM atau akses ke database nasabah.
            
            **🎯 Action Plan (Evaluasi):**
            2. **Audit Ketersediaan Seller:** Pastikan branch-branch ini memiliki seller aktif (RFRM/MFRM) yang memang bertugas. Jika tidak ada seller, leads tidak akan pernah tercipta.
            3. **Cek Distribusi Leads Manual:** Apakah branch ini dilewati dalam sistem auto-routing? Jika ya, sistem perlu di-rekonfigurasi agar branch kelas {top_class} tetap mendapatkan alokasi leads minimal.
            4. **Program Stimulus Leads:** Berikan *forced allocation* minimal 5-10 leads/bulan ke branch zero-performance untuk menguji potensi pasar di area tersebut.
            5. **Evaluasi Branch Class:** Jika setelah 3 bulan berturut-turut tetap zero-leads, pertimbangkan *re-classification* atau merger dengan branch terdekat.
            """)
        else:
            st.success("✅ **Selamat!** Semua branch dalam filter yang dipilih telah menghasilkan leads. Tidak ada zero-performance branch.")

    # ====================================================================
    # --- 7. VISUALISASI TAMBAHAN (DISTRIBUSI) ---
    # ====================================================================
    st.markdown("---")
    st.header("🗺️ Distribusi Geografis & Komposisi")
    
    colA, colB = st.columns(2)
    with colA:
        st.subheader("Distribusi Leads per Kelas Cabang")
        fig_class = px.bar(df_filt, x='BranchClass', color='BranchClass',
                          title="Apakah Cabang Kecil (S/XS) Kehujanan Leads?",
                          category_orders={'BranchClass': ['XL', 'L', 'M', 'S', 'XS']},
                          color_discrete_sequence=px.colors.qualitative.Set2)
        st.plotly_chart(fig_class, use_container_width=True)
    
    with colB:
        st.subheader("Komposisi Jenis Leads")
        fig_pie = px.pie(df_filt, names='Jenis_Leads', hole=0.4,
                        title="Dominasi Bank Leads vs Cross-Sell/Renewal",
                        color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig_pie, use_container_width=True)

    # ====================================================================
    # --- 8. DYNAMIC BUSINESS INSIGHTS ---
    # ====================================================================
    st.markdown("---")
    st.header("💡 Dynamic Business Insights (Context-Aware)")
    
    if total_leads > 0:
        # Insight 1: Top Performer
        top_performer = df_filt.groupby('Seller_Name').size().idxmax()
        top_performer_count = df_filt.groupby('Seller_Name').size().max()
        
        # Insight 2: Branch dengan rasio tertinggi
        branch_ratio = df_filt.groupby('Branch_Name').agg(
            Leads=('Leads_ID', 'count'),
            Sellers=('Seller_Name', 'nunique')
        ).reset_index()
        branch_ratio['Ratio'] = branch_ratio['Leads'] / branch_ratio['Sellers'].replace(0, 1)
        top_ratio_branch = branch_ratio.loc[branch_ratio['Ratio'].idxmax()]
        
        # Insight 3: Jenis leads dominan
        top_lead_type = df_filt['Jenis_Leads'].value_counts().index[0]
        top_lead_pct = (df_filt['Jenis_Leads'].value_counts().iloc[0] / total_leads) * 100
        
        st.success(f"""
        **🎯 Key Takeaways (Periode {start_date} s/d {end_date}):**
        
        1. **Top Performer:** Seller **{top_performer}** memimpin dengan **{top_performer_count} leads**. Analisis script/approach-nya untuk direplikasi ke seller lain.
        
        2. **Workload Imbalance:** Branch **{top_ratio_branch['Branch_Name']}** memiliki rasio tertinggi ({top_ratio_branch['Ratio']:.1f} leads/seller). Pertimbangkan redistribusi leads ke branch dengan rasio lebih rendah.
        
        3. **Lead Type Dominance:** **{top_lead_type}** mendominasi sebesar **{top_lead_pct:.1f}%**. 
        👉 *Rekomendasi:* Pastikan produk yang ditawarkan sesuai dengan profil nasabah dari jenis leads ini untuk memaksimalkan *conversion rate*.
        
        4. **Zero-Performance Alert:** {f'Terdapat {len(zero_leads_branches)} branch yang perlu perhatian khusus (lihat tab "Branch Tanpa Leads").' if not zero_leads_branches.empty else 'Semua branch aktif menghasilkan leads. Pertahankan momentum ini!'}
        """)
    else:
        st.warning("⚠️ Tidak ada data leads pada filter & periode yang dipilih.")

else:
    st.warning("⚠️ Data tidak ditemukan atau file belum dimuat dengan benar. Pastikan file bernama 'data.xlsx'.")