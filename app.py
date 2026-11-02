import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import norm
import io
import math
from datetime import datetime
import plotly.express as px

# --- PAGE CONFIG ---
st.set_page_config(page_title="RM Inventory Optimization Engine", layout="wide")

# Modern UI styling
st.markdown("""
<style>
    .stApp { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 10px; border: 1px solid #e1e4e8; box-shadow: 2px 2px 5px #eeeeee; }
    h1, h2 { color: #2E86C1; }
</style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def get_user_column_mapping(df, expected_cols, file_name):
    st.write(f"### Map your columns for {file_name}")
    mapping = {}
    cols = list(df.columns)
    for expected in expected_cols:
        default_idx = 0
        for i, col in enumerate(cols):
            if any(synonym in col.lower() for synonym in expected.lower().split('_')):
                default_idx = i
                break
        selection = st.selectbox(f"Select column for: **{expected}**", cols, index=default_idx, key=f"{file_name}_{expected}")
        mapping[expected] = selection
    return df.rename(columns={v: k for k, v in mapping.items()})

def calculate_inventory_metrics(df_master, df_issues, df_po, csl, h_cost_pct, po_cost):
    df_issues['Date'] = pd.to_datetime(df_issues['Date'])
    daily_demand = df_issues.groupby(['Item_Code', 'Date'])['Qty_Issued'].sum().reset_index()
    min_date, max_date = daily_demand['Date'].min(), daily_demand['Date'].max()
    all_dates = pd.date_range(min_date, max_date)
    
    demand_stats = []
    for item in df_master['Item_Code'].unique():
        item_demand = daily_demand[daily_demand['Item_Code'] == item].set_index('Date')['Qty_Issued']
        item_demand = item_demand.reindex(all_dates, fill_value=0)
        demand_stats.append({'Item_Code': item, 'mu_D': item_demand.mean(), 'sigma_D': item_demand.std()})
    df_demand_stats = pd.DataFrame(demand_stats)

    df_po['PO_Date'] = pd.to_datetime(df_po['PO_Date'])
    df_po['GRN_Date'] = pd.to_datetime(df_po['GRN_Date'])
    df_comp = df_po[df_po['GRN_Date'].notna()].copy()
    df_comp['LT'] = (df_comp['GRN_Date'] - df_comp['PO_Date']).dt.days
    
    lt_stats = []
    for item in df_master['Item_Code'].unique():
        item_lt = df_comp[df_comp['Item_Code'] == item]['LT']
        if not item_lt.empty:
            lt_stats.append({'Item_Code': item, 'mu_L': item_lt.mean(), 'sigma_L': item_lt.std() if len(item_lt) > 1 else 0})
        else:
            def_lt = df_master[df_master['Item_Code'] == item]['Default_Lead_Days'].values[0]
            lt_stats.append({'Item_Code': item, 'mu_L': float(def_lt), 'sigma_L': 0.0})
    df_lt_stats = pd.DataFrame(lt_stats)

    final_df = df_master.merge(df_demand_stats, on='Item_Code', how='left').merge(df_lt_stats, on='Item_Code', how='left')
    final_df[['mu_D', 'sigma_D']] = final_df[['mu_D', 'sigma_D']].fillna(0)
    
    z = norm.ppf(csl)
    final_df['Safety_Stock'] = np.ceil(z * np.sqrt(final_df['mu_L'] * (final_df['sigma_D']**2) + (final_df['mu_D']**2) * (final_df['sigma_L']**2))).fillna(0)
    final_df['ROP'] = np.ceil(final_df['mu_D'] * final_df['mu_L'] + final_df['Safety_Stock'])
    final_df['Annual_Demand'] = final_df['mu_D'] * 365
    final_df['Raw_EOQ'] = np.sqrt((2 * po_cost * final_df['Annual_Demand']) / (h_cost_pct * final_df['Unit_Cost']))
    final_df['Optimal_Order_Qty'] = final_df.apply(lambda r: max(r['Supplier_MOQ'], math.ceil(r['Raw_EOQ'] / r['Pack_Size']) * r['Pack_Size']), axis=1)
    
    final_df['ACV'] = final_df['Annual_Demand'] * final_df['Unit_Cost']
    final_df = final_df.sort_values('ACV', ascending=False)
    final_df['Cum_ACV_Pct'] = final_df['ACV'].cumsum() / final_df['ACV'].sum()
    final_df['ABC_Class'] = final_df['Cum_ACV_Pct'].apply(lambda p: 'A' if p <= 0.7 else ('B' if p <= 0.9 else 'C'))
    
    open_po = df_po.groupby('Item_Code')['Open_Pending_Qty'].sum().reset_index()
    final_df = final_df.merge(open_po, on='Item_Code', how='left')
    final_df['Open_Pending_Qty'] = final_df['Open_Pending_Qty'].fillna(0)
    
    def get_status(row):
        phys, ss, rop = row['Stores_Physical_Stock'], row['Safety_Stock'], row['ROP']
        net = phys + row['Open_Pending_Qty']
        if phys < ss: return "CRITICAL STOCKOUT THREAT"
        if net <= rop: return "RELEASE PURCHASE ORDER"
        if phys <= rop and net > rop: return "EXPEDITE IN-TRANSIT GRN"
        return "HEALTHY INVENTORY"

    final_df['Action_Status'] = final_df.apply(get_status, axis=1)
    return final_df

st.title("🏭 Plant Raw Material (RM) Inventory Optimization Engine")

# --- SIDEBAR CONTROLS ---
st.sidebar.header("Optimization Parameters")
csl = st.sidebar.slider("Cycle Service Level (CSL)", 85.0, 99.9, 95.0, 0.1) / 100.0
holding_cost_pct = st.sidebar.number_input("Holding Cost % (Annual)", 5.0, 50.0, 20.0) / 100.0
po_admin_cost = st.sidebar.number_input("Fixed PO Admin Cost ($)", 1.0, 1000.0, 50.0)

with st.sidebar.expander("💡 Cost Parameter Guide"):
    st.markdown("""
    **Understanding the Engine Metrics:**
    *   **Avg Daily Demand (mu_D)**: The average quantity consumed each day.
    *   **Demand Volatility (sigma_D)**: The standard deviation in daily usage.
    *   **Avg Lead Time (mu_L)**: Average days taken from PO issuance to material arrival.
    *   **Lead Time Volatility (sigma_L)**: The consistency of your suppliers.
    *   **Recommended Safety Stock**: Buffer stock kept to mitigate demand/lead time spikes.
    *   **Reorder Point (ROP)**: When stock hits this level, place a new PO.

    ---

    **Holding Cost % Calculation:**
    Holding Cost % = Capital Rate + Storage Costs + Insurance & Waste
    *   *Rule of Thumb for small factories*: **18% to 25%** per year (Default: **20%**).

    **Fixed PO Admin Cost ($) Calculation:**
    PO Cost = (Purchasing Dept Salaries + Software Costs) / Total POs per Year
    *   *Typical Range*: **$30 to $100 per PO** (Default: **$50**).
    """)

# --- ONBOARDING & DATA GUIDE ---
with st.expander("📖 Step-by-Step Data Onboarding Guide", expanded=False):
    st.markdown("### How to Prepare and Upload Your Data")
    g1, g2, g3 = st.columns(3)
    with g1:
        st.markdown("#### 1. Item Master")
        st.write("* SKU/Part#, Description, Current Stock, Unit Cost, MOQ, Pack Size, Lead Time.")
    with g2:
        st.markdown("#### 2. MTN Issues")
        st.write("* Item Code, Date, Qty Issued.")
    with g3:
        st.markdown("#### 3. PO/GRN Register")
        st.write("* Item Code, PO Date, GRN Date, Pending Qty.")
    st.info("💡 Map your column headers using the assistant below after uploading.")

# --- UI INPUT TABS ---
tab1, tab2 = st.tabs(["📂 Multi-File Upload", "📘 Single Workbook Upload"])
df_master, df_issues, df_po = None, None, None

with tab1:
    c1, c2, c3 = st.columns(3)
    f_m = c1.file_uploader("Item Master", type=['csv', 'xlsx'])
    f_i = c2.file_uploader("MTN Issues", type=['csv', 'xlsx'])
    f_p = c3.file_uploader("PO/GRN Register", type=['csv', 'xlsx'])
    if f_m and f_i and f_p:
        df_master = pd.read_csv(f_m) if f_m.name.endswith('.csv') else pd.read_excel(f_m)
        df_issues = pd.read_csv(f_i) if f_i.name.endswith('.csv') else pd.read_excel(f_i)
        df_po = pd.read_csv(f_p) if f_p.name.endswith('.csv') else pd.read_excel(f_p)

if df_master is not None and df_issues is not None and df_po is not None:
    st.subheader("🛠️ Column Mapping Assistant")
    with st.expander("Configure Column Mappings", expanded=True):
        m1, m2, m3 = st.columns(3)
        with m1: df_master = get_user_column_mapping(df_master, ['Item_Code', 'Description', 'Category', 'Stores_Physical_Stock', 'Unit_Cost', 'Supplier_MOQ', 'Pack_Size', 'Default_Lead_Days'], "Item Master")
        with m2: df_issues = get_user_column_mapping(df_issues, ['Item_Code', 'Date', 'Qty_Issued'], "MTN Issues")
        with m3: df_po = get_user_column_mapping(df_po, ['Item_Code', 'PO_Date', 'GRN_Date', 'Open_Pending_Qty'], "PO/GRN Register")

    if st.button("🚀 Run Optimization Engine"):
        results = calculate_inventory_metrics(df_master, df_issues, df_po, csl, holding_cost_pct, po_admin_cost)
        st.subheader("📊 Inventory vs. Safety Stock Analysis")
        fig = px.bar(results, x='Item_Code', y=['Stores_Physical_Stock', 'Safety_Stock'], barmode='group')
        st.plotly_chart(fig, use_container_width=True)
        st.subheader("Inventory Action Triage")
        def color_status(val):
            colors = {'CRITICAL STOCKOUT THREAT': '#FF4B4B', 'RELEASE PURCHASE ORDER': '#FFA500', 'EXPEDITE IN-TRANSIT GRN': '#2E86C1', 'HEALTHY INVENTORY': '#28A745'}
            return f'background-color: {colors.get(val, "#FFFFFF")}; color: #FFFFFF; font-weight: bold; border-radius: 4px;'
        results_display = results.rename(columns={'mu_D': 'Avg Daily Demand', 'sigma_D': 'Demand Volatility', 'mu_L': 'Avg Lead Time (Days)', 'sigma_L': 'Lead Time Volatility', 'Safety_Stock': 'Recommended Safety Stock', 'ROP': 'Reorder Point', 'Optimal_Order_Qty': 'Optimal Order Qty'})
        cols = ['Item_Code', 'Description', 'ABC_Class', 'Stores_Physical_Stock', 'Recommended Safety Stock', 'Reorder Point', 'Optimal Order Qty', 'Action_Status']
        st.dataframe(results_display[cols].style.map(color_status, subset=['Action_Status']), width=1500)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            results_display.to_excel(writer, sheet_name='Inventory_Optimization', index=False)
            workbook, worksheet = writer.book, writer.sheets['Inventory_Optimization']
            header_format = workbook.add_format({'bold': True, 'bg_color': '#2E86C1', 'font_color': 'white', 'border': 1})
            status_formats = {s: workbook.add_format({'bg_color': c, 'font_color': 'white'}) for s, c in {'CRITICAL STOCKOUT THREAT': '#FF4B4B', 'RELEASE PURCHASE ORDER': '#FFA500', 'EXPEDITE IN-TRANSIT GRN': '#2E86C1', 'HEALTHY INVENTORY': '#28A745'}.items()}
            for col_num, value in enumerate(results_display.columns.values): worksheet.write(0, col_num, value, header_format); worksheet.set_column(col_num, col_num, 15)
            for row_num, status in enumerate(results_display['Action_Status']): 
                if status in status_formats: worksheet.write(row_num + 1, len(results_display.columns) - 1, status, status_formats[status])
        st.divider()
        st.subheader("📝 We Value Your Feedback")
        st.link_button("Share Your Honest Review", "https://docs.google.com/forms/d/e/1FAIpQLSee7lV13AZ4594w2ZmzvB4mfUOMCOLPBbhQss-I37ng_gkksA/viewform?usp=sf_link")
        st.download_button("📥 Download Beautiful Report", buf.getvalue(), "Inventory_Optimization_Report.xlsx")

with tab2:
    f_all = st.file_uploader("3-sheet Workbook", type=['xlsx'])
    if f_all:
        xls = pd.ExcelFile(f_all)
        s = xls.sheet_names
        df_master, df_issues, df_po = [pd.read_excel(xls, sheet_name=s[i]) for i in range(3)]
