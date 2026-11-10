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
    .stApp { background-color: #1A5F7A; color: #F1F5F9; }
    .stMetric { background-color: #2C7891; padding: 20px; border-radius: 10px; border: 1px solid #4893A9; box-shadow: 2px 2px 5px rgba(0,0,0,0.3); margin: 10px 0; }
    .stMetric > label { color: #E0E7FF; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; }
    .stMetric > div { color: #FFFFFF; }
    h1, h2 { color: #FFFFFF; }
    .stDataFrame, .stTable { background-color: #2C7891; }
    
    /* Clean button and download button styling */
    div.stButton > button, div.stDownloadButton > button, a.stLinkButton {
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        border: 1px solid #CBD5E1 !important;
        font-weight: 600 !important;
        padding: 10px 20px !important;
        border-radius: 8px !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    div.stButton > button:hover, div.stDownloadButton > button:hover, a.stLinkButton:hover {
        background-color: #F8FAFC !important;
        border-color: #94A3B8 !important;
        color: #0F172A !important;
    }
</style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
SYNONYMS = {
    'Item_Code': ['item_code', 'item', 'item_no', 'item_number', 'sku', 'part_no', 'part_number', 'material', 'material_no', 'material_code'],
    'Description': ['description', 'desc', 'item_description', 'material_description', 'name', 'item_name'],
    'Category': ['category', 'cat', 'item_category', 'type', 'group', 'material_group'],
    'Stores_Physical_Stock': ['stores_physical_stock', 'physical_stock', 'stock', 'current_stock', 'qty_on_hand', 'on_hand', 'inventory'],
    'Unit_Cost': ['unit_cost', 'cost', 'unit_price', 'price', 'rate', 'cost_per_unit'],
    'Supplier_MOQ': ['supplier_moq', 'moq', 'min_order_qty', 'minimum_order_qty'],
    'Pack_Size': ['pack_size', 'pack', 'lot_size', 'order_multiple', 'batch_size'],
    'Default_Lead_Days': ['default_lead_days', 'lead_days', 'lead_time', 'default_lead_time', 'lt_days'],
    'Date': ['date', 'issue_date', 'transaction_date', 'txn_date', 'posted_date'],
    'Qty_Issued': ['qty_issued', 'issued_qty', 'quantity', 'qty', 'consumption', 'usage'],
    'PO_Date': ['po_date', 'order_date', 'purchasing_date', 'creation_date'],
    'GRN_Date': ['grn_date', 'receipt_date', 'received_date', 'delivery_date', 'gr_date'],
    'Open_Pending_Qty': ['open_pending_qty', 'pending_qty', 'open_qty', 'qty_on_order', 'in_transit_qty', 'open_po_qty']
}

def get_user_column_mapping(df, expected_cols, file_name):
    st.write(f"### Map your columns for {file_name}")
    mapping = {}
    cols = list(df.columns)
    
    for expected in expected_cols:
        syns = SYNONYMS.get(expected, [expected.lower()])
        default_idx = 0
        
        # 1. Exact match (case insensitive, ignoring spaces/underscores)
        found = False
        for i, col in enumerate(cols):
            clean_col = col.strip().lower().replace(" ", "_")
            if clean_col in syns:
                default_idx = i
                found = True
                break
        
        # 2. Substring match if exact match failed
        if not found:
            for i, col in enumerate(cols):
                clean_col = col.strip().lower().replace(" ", "_")
                if any(syn in clean_col for syn in syns):
                    default_idx = i
                    break

        selection = st.selectbox(f"Select column for: **{expected}**", cols, index=default_idx, key=f"{file_name}_{expected}")
        mapping[expected] = selection
    
    # Check duplicate mapped columns
    mapped_selected = list(mapping.values())
    if len(mapped_selected) != len(set(mapped_selected)):
        st.warning(f"⚠️ Warning in {file_name}: Some fields are mapped to the same uploaded column. Please verify dropdown selections.")
        
    return df.rename(columns={v: k for k, v in mapping.items()})


def calculate_inventory_metrics(df_master, df_issues, df_po, csl_param, h_cost_pct, po_cost):
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
    
    # Calculate Annual Demand and ACV first to determine ABC classification
    final_df['Annual_Demand'] = final_df['mu_D'] * 365
    final_df['ACV'] = final_df['Annual_Demand'] * final_df['Unit_Cost']
    final_df = final_df.sort_values('ACV', ascending=False).reset_index(drop=True)
    final_df['Cum_ACV_Pct'] = final_df['ACV'].cumsum() / final_df['ACV'].sum()
    final_df['ABC_Class'] = final_df['Cum_ACV_Pct'].apply(lambda p: 'A' if p <= 0.7 else ('B' if p <= 0.9 else 'C'))

    # Map each item's ABC classification to its respective target CSL
    def get_target_csl_decimal(row):
        cls = row['ABC_Class']
        if isinstance(csl_param, dict):
            return csl_param.get(cls, 0.95)
        else:
            return float(csl_param)

    final_df['Target_CSL_Decimal'] = final_df.apply(get_target_csl_decimal, axis=1)
    final_df['Target_CSL'] = round(final_df['Target_CSL_Decimal'] * 100.0, 2)
    final_df['Z_Score'] = final_df['Target_CSL_Decimal'].apply(lambda x: norm.ppf(x))

    # Apply item-level Z-score to the dual-stochastic safety stock formula:
    # SS = Z * sqrt(mu_L * sigma_D^2 + mu_D^2 * sigma_L^2)
    final_df['Safety_Stock'] = np.ceil(final_df['Z_Score'] * np.sqrt(final_df['mu_L'] * (final_df['sigma_D']**2) + (final_df['mu_D']**2) * (final_df['sigma_L']**2))).fillna(0)
    final_df['ROP'] = np.ceil(final_df['mu_D'] * final_df['mu_L'] + final_df['Safety_Stock'])
    
    final_df['Raw_EOQ'] = np.sqrt((2 * po_cost * final_df['Annual_Demand']) / (h_cost_pct * final_df['Unit_Cost']))
    final_df['Optimal_Order_Qty'] = final_df.apply(lambda r: max(r['Supplier_MOQ'], math.ceil(r['Raw_EOQ'] / r['Pack_Size']) * r['Pack_Size']), axis=1)
    
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

enable_abc_csl = st.sidebar.toggle("Enable ABC Tiered Service Levels", value=False)

if enable_abc_csl:
    st.sidebar.markdown("#### Tiered CSL Targets")
    csl_a_val = st.sidebar.slider("Class A Target CSL %", 85.0, 99.9, 98.0, 0.5)
    csl_b_val = st.sidebar.slider("Class B Target CSL %", 80.0, 99.0, 95.0, 0.5)
    csl_c_val = st.sidebar.slider("Class C Target CSL %", 70.0, 98.0, 90.0, 0.5)
    csl_dict = {
        'A': csl_a_val / 100.0,
        'B': csl_b_val / 100.0,
        'C': csl_c_val / 100.0
    }
    st.sidebar.success(f"🎯 **ABC Tiered CSL Enabled:**\n* Class A: {csl_a_val}%\n* Class B: {csl_b_val}%\n* Class C: {csl_c_val}%")
    csl_param = csl_dict
else:
    csl_value = st.sidebar.slider("Cycle Service Level (CSL) %", 85.0, 99.9, 95.0, 0.1)
    csl = csl_value / 100.0
    csl_dict = {
        'A': csl,
        'B': csl,
        'C': csl
    }
    csl_param = csl_dict

    # Dynamic explanation based on the chosen CSL
    if csl_value >= 98:
        st.sidebar.success(f"🎯 **High Service Level ({csl_value}%):** Minimized stockout risk, but requires higher safety stock investment.")
    elif csl_value >= 90:
        st.sidebar.info(f"⚖️ **Balanced Service Level ({csl_value}%):** A good trade-off between stock availability and holding costs.")
    else:
        st.sidebar.warning(f"⚠️ **Lean Service Level ({csl_value}%):** Reduced capital investment, but higher risk of occasional stockouts.")

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
    st.info("Please upload the corresponding files to each section below:")
    c1, c2, c3 = st.columns(3)
    f_m = c1.file_uploader("Upload Item Master", type=['csv', 'xlsx'], help="Upload your Item Master/SKU list file here.")
    f_i = c2.file_uploader("Upload MTN Issues", type=['csv', 'xlsx'], help="Upload your Material Issues/Consumption history file here.")
    f_p = c3.file_uploader("Upload PO/GRN Register", type=['csv', 'xlsx'], help="Upload your Purchase Order and Goods Received Note register here.")
    
    st.markdown("""
    <style>
    /* Improve visibility of upload area text */
    [data-testid="stFileUploader"] {
        background-color: #2C7891 !important;
        border: 1px solid #4893A9 !important;
        border-radius: 8px;
    }
    [data-testid="stFileUploader"] label {
        color: #FFFFFF !important;
        font-weight: bold;
    }
    [data-testid="stFileUploader"] span {
        color: #E0E7FF !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
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
        results = calculate_inventory_metrics(df_master, df_issues, df_po, csl_param, holding_cost_pct, po_admin_cost)
        st.subheader("📊 Inventory vs. Safety Stock Analysis")
        fig = px.bar(results, x='Item_Code', y=['Stores_Physical_Stock', 'Safety_Stock'], barmode='group')
        st.plotly_chart(fig, use_container_width=True)
        st.subheader("Inventory Action Triage")
        def color_status(val):
            badge_styles = {
                'CRITICAL STOCKOUT THREAT': {'bg': '#FEE2E2', 'text': '#991B1B'},
                'RELEASE PURCHASE ORDER': {'bg': '#FEF3C7', 'text': '#92400E'},
                'EXPEDITE IN-TRANSIT GRN': {'bg': '#FEF3C7', 'text': '#92400E'},
                'HEALTHY INVENTORY': {'bg': '#D1FAE5', 'text': '#065F46'},
            }
            style = badge_styles.get(val, {'bg': '#FFFFFF', 'text': '#1E293B'})
            return f'background-color: {style["bg"]}; color: {style["text"]}; font-weight: bold; border-radius: 4px;'
        
        results_display = results.rename(columns={'mu_D': 'Avg Daily Demand', 'sigma_D': 'Demand Volatility', 'mu_L': 'Avg Lead Time (Days)', 'sigma_L': 'Lead Time Volatility', 'Safety_Stock': 'Recommended Safety Stock', 'ROP': 'Reorder Point', 'Optimal_Order_Qty': 'Optimal Order Qty', 'Target_CSL': 'Target CSL (%)', 'Z_Score': 'Z-Score'})
        cols = ['Item_Code', 'Description', 'ABC_Class', 'Target CSL (%)', 'Z-Score', 'Stores_Physical_Stock', 'Recommended Safety Stock', 'Reorder Point', 'Optimal Order Qty', 'Action_Status']
        
        with st.container(border=True):
            st.dataframe(results_display[cols].style.map(color_status, subset=['Action_Status']), use_container_width=True)
            
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            results_display.to_excel(writer, sheet_name='Inventory_Optimization', index=False)
            workbook, worksheet = writer.book, writer.sheets['Inventory_Optimization']
            
            header_format = workbook.add_format({
                'bold': True, 
                'bg_color': '#1F4E78', 
                'font_color': 'white', 
                'border': 1,
                'align': 'center',
                'valign': 'vcenter'
            })
            header_format.set_font_size(12)
            
            # Status colors matching UI
            status_colors = {
                'CRITICAL STOCKOUT THREAT': {'bg': '#FEE2E2', 'text': '#991B1B'},
                'RELEASE PURCHASE ORDER': {'bg': '#FEF3C7', 'text': '#92400E'},
                'EXPEDITE IN-TRANSIT GRN': {'bg': '#FEF3C7', 'text': '#92400E'},
                'HEALTHY INVENTORY': {'bg': '#D1FAE5', 'text': '#065F46'},
            }
            
            # Zebra striping formats
            row_format_white = workbook.add_format({'border': 1, 'border_color': '#E2E8F0'})
            row_format_gray = workbook.add_format({'bg_color': '#F8FAFC', 'border': 1, 'border_color': '#E2E8F0'})
            
            for col_num, value in enumerate(results_display.columns.values):
                worksheet.write(0, col_num, value, header_format)
                worksheet.set_column(col_num, col_num, len(str(value)) + 4)
            
            for row_num, (index, row) in enumerate(results_display.iterrows()):
                status = row['Action_Status']
                status_fmt = workbook.add_format({
                    'bg_color': status_colors[status]['bg'], 
                    'font_color': status_colors[status]['text'],
                    'border': 1,
                    'border_color': '#E2E8F0'
                })
                
                # Apply zebra striping to non-status columns
                row_fmt = row_format_gray if row_num % 2 == 1 else row_format_white
                
                for col_num in range(len(results_display.columns)):
                    col_name = results_display.columns[col_num]
                    if col_name == 'Action_Status':
                        worksheet.write(row_num + 1, col_num, status, status_fmt)
                    else:
                        worksheet.write(row_num + 1, col_num, row[col_name], row_fmt)

        st.divider()
        st.subheader("📝 We Value Your Feedback")
        st.link_button("Share Your Honest Review", "https://docs.google.com/forms/d/e/1FAIpQLSee7lV13AZ4594w2ZmzvB4mfUOMCOLPBbhQss-I37ng_gkksA/viewform?usp=sf_link")
        st.download_button("📥 Download Optimization Report", buf.getvalue(), "Inventory_Optimization_Report.xlsx")

with tab2:
    f_all = st.file_uploader("3-sheet Workbook", type=['xlsx'])
    if f_all:
        xls = pd.ExcelFile(f_all)
        s = xls.sheet_names
        df_master, df_issues, df_po = [pd.read_excel(xls, sheet_name=s[i]) for i in range(3)]
