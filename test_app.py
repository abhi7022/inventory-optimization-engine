import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import norm
import io
import math
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

# --- PAGE CONFIG ---
st.set_page_config(page_title="RM Inventory Optimization Engine", layout="wide", page_icon="🏭")

# High-polish modern SaaS styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .stApp { 
        background-color: #0F172A; 
        color: #F8FAFC; 
    }
    
    /* Clean Top KPI Cards */
    .kpi-container {
        display: flex;
        gap: 16px;
        margin-bottom: 24px;
    }
    .kpi-card {
        flex: 1;
        background: #1E293B;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px 24px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
        transition: transform 0.15s ease, border-color 0.15s ease;
    }
    .kpi-card:hover {
        border-color: #0284C7;
        transform: translateY(-2px);
    }
    .kpi-title {
        color: #94A3B8;
        font-size: 13px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 8px;
    }
    .kpi-value {
        color: #FFFFFF;
        font-size: 28px;
        font-weight: 700;
        line-height: 1.2;
    }
    .kpi-badge {
        display: inline-block;
        margin-top: 10px;
        font-size: 12px;
        font-weight: 600;
        padding: 3px 10px;
        border-radius: 20px;
    }
    .badge-red { background: rgba(239, 68, 68, 0.2); color: #F87171; border: 1px solid rgba(239, 68, 68, 0.4); }
    .badge-amber { background: rgba(245, 158, 11, 0.2); color: #FBBF24; border: 1px solid rgba(245, 158, 11, 0.4); }
    .badge-green { background: rgba(16, 185, 129, 0.2); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.4); }

    /* Modern Table Wrapper */
    .stDataFrame {
        border: 1px solid #334155;
        border-radius: 8px;
        overflow: hidden;
    }
    
    /* Buttons */
    div.stButton > button, div.stDownloadButton > button, a.stLinkButton {
        background-color: #0284C7 !important;
        color: #FFFFFF !important;
        border: none !important;
        font-weight: 600 !important;
        padding: 10px 24px !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 6px -1px rgba(2, 132, 199, 0.3) !important;
    }
    div.stButton > button:hover, div.stDownloadButton > button:hover, a.stLinkButton:hover {
        background-color: #0369A1 !important;
    }
    
    /* Upload Boxes */
    [data-testid="stFileUploader"] {
        background-color: #1E293B !important;
        border: 1px dashed #475569 !important;
        border-radius: 10px;
        padding: 10px;
    }
    [data-testid="stFileUploader"] label {
        color: #F8FAFC !important;
        font-weight: 600;
    }

    /* Advisory Box */
    .consult-banner {
        background: linear-gradient(135deg, #0F766E 0%, #134E4A 100%);
        border: 1px solid #2DD4BF;
        border-radius: 12px;
        padding: 22px 28px;
        margin-top: 32px;
        color: #FFFFFF;
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
    st.write(f"#### {file_name}")
    mapping = {}
    cols = list(df.columns)
    
    for expected in expected_cols:
        syns = SYNONYMS.get(expected, [expected.lower()])
        default_idx = 0
        found = False
        for i, col in enumerate(cols):
            clean_col = col.strip().lower().replace(" ", "_")
            if clean_col in syns:
                default_idx = i
                found = True
                break
        if not found:
            for i, col in enumerate(cols):
                clean_col = col.strip().lower().replace(" ", "_")
                if any(syn in clean_col for syn in syns):
                    default_idx = i
                    break

        selection = st.selectbox(f"**{expected}**", cols, index=default_idx, key=f"{file_name}_{expected}")
        mapping[expected] = selection
        
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
    
    final_df['Annual_Demand'] = final_df['mu_D'] * 365
    final_df['ACV'] = final_df['Annual_Demand'] * final_df['Unit_Cost']
    final_df = final_df.sort_values('ACV', ascending=False).reset_index(drop=True)
    final_df['Cum_ACV_Pct'] = final_df['ACV'].cumsum() / final_df['ACV'].sum()
    final_df['ABC_Class'] = final_df['Cum_ACV_Pct'].apply(lambda p: 'A' if p <= 0.7 else ('B' if p <= 0.9 else 'C'))

    def get_target_csl_decimal(row):
        cls = row['ABC_Class']
        return csl_param.get(cls, 0.95) if isinstance(csl_param, dict) else float(csl_param)

    final_df['Target_CSL_Decimal'] = final_df.apply(get_target_csl_decimal, axis=1)
    final_df['Target_CSL'] = round(final_df['Target_CSL_Decimal'] * 100.0, 1)
    final_df['Z_Score'] = final_df['Target_CSL_Decimal'].apply(lambda x: round(norm.ppf(x), 2))

    # Dual-stochastic safety stock
    final_df['Safety_Stock'] = np.ceil(
        final_df['Z_Score'] * np.sqrt(
            final_df['mu_L'] * (final_df['sigma_D']**2) + (final_df['mu_D']**2) * (final_df['sigma_L']**2)
        )
    ).fillna(0).astype(int)
    
    final_df['ROP'] = np.ceil(final_df['mu_D'] * final_df['mu_L'] + final_df['Safety_Stock']).astype(int)
    
    final_df['Raw_EOQ'] = np.sqrt((2 * po_cost * final_df['Annual_Demand']) / (h_cost_pct * final_df['Unit_Cost']))
    final_df['Optimal_Order_Qty'] = final_df.apply(
        lambda r: int(max(r['Supplier_MOQ'], math.ceil(r['Raw_EOQ'] / (r['Pack_Size'] or 1)) * (r['Pack_Size'] or 1))), 
        axis=1
    )
    
    open_po = df_po.groupby('Item_Code')['Open_Pending_Qty'].sum().reset_index()
    final_df = final_df.merge(open_po, on='Item_Code', how='left')
    final_df['Open_Pending_Qty'] = final_df['Open_Pending_Qty'].fillna(0).astype(int)
    
    def get_status(row):
        phys, ss, rop = row['Stores_Physical_Stock'], row['Safety_Stock'], row['ROP']
        net = phys + row['Open_Pending_Qty']
        if phys < ss: return "CRITICAL STOCKOUT THREAT"
        if net <= rop: return "RELEASE PURCHASE ORDER"
        if phys <= rop and net > rop: return "EXPEDITE IN-TRANSIT GRN"
        return "HEALTHY INVENTORY"

    final_df['Action_Status'] = final_df.apply(get_status, axis=1)
    
    # Financial Working Capital
    final_df['Excess_Qty'] = (final_df['Stores_Physical_Stock'] - (final_df['ROP'] + final_df['Safety_Stock'])).clip(lower=0).astype(int)
    final_df['Excess_Capital_Locked'] = final_df['Excess_Qty'] * final_df['Unit_Cost']
    final_df['Order_Spend_Required'] = np.where(
        final_df['Action_Status'].isin(['CRITICAL STOCKOUT THREAT', 'RELEASE PURCHASE ORDER']),
        final_df['Optimal_Order_Qty'] * final_df['Unit_Cost'],
        0.0
    )
    
    # Stock Health Ratio for non-distorted visualization
    final_df['Stock_Health_Ratio'] = np.where(
        final_df['ROP'] > 0,
        np.round((final_df['Stores_Physical_Stock'] / final_df['ROP']) * 100, 1),
        100.0
    )

    return final_df

# --- HEADER & DATA SECURITY ---
st.title("🏭 Plant Raw Material Inventory Optimization Engine")

st.info(
    "🔒 **100% Client-Side Privacy Guarantee:** All calculations run strictly in ephemeral memory (RAM) "
    "during your active browser session. Uploaded files, item rates, and vendor registers "
    "are never stored, logged, or saved to any external database or disk. Closing this tab clears all data."
)

# --- SIDEBAR ---
st.sidebar.header("⚙️ Optimization Parameters")
enable_abc_csl = st.sidebar.toggle("Enable ABC Tiered Service Levels", value=False)

if enable_abc_csl:
    csl_a_val = st.sidebar.slider("Class A Target CSL %", 85.0, 99.9, 98.0, 0.5)
    csl_b_val = st.sidebar.slider("Class B Target CSL %", 80.0, 99.0, 95.0, 0.5)
    csl_c_val = st.sidebar.slider("Class C Target CSL %", 70.0, 98.0, 90.0, 0.5)
    csl_param = {'A': csl_a_val / 100.0, 'B': csl_b_val / 100.0, 'C': csl_c_val / 100.0}
else:
    csl_value = st.sidebar.slider("Cycle Service Level (CSL) %", 85.0, 99.9, 95.0, 0.1)
    csl_param = {'A': csl_value / 100.0, 'B': csl_value / 100.0, 'C': csl_value / 100.0}

holding_cost_pct = st.sidebar.number_input("Holding Cost % (Annual)", 5.0, 50.0, 20.0) / 100.0
po_admin_cost = st.sidebar.number_input("Fixed PO Admin Cost (₹ / $)", 1.0, 5000.0, 50.0)

# --- FILE UPLOADS ---
with st.expander("📖 Step-by-Step Data Onboarding Guide", expanded=False):
    g1, g2, g3 = st.columns(3)
    g1.markdown("**1. Item Master:** SKU, Description, Physical Stock, Cost, MOQ, Pack Size, Lead Days.")
    g2.markdown("**2. MTN Issues:** Item Code, Date of Issue, Qty Issued.")
    g3.markdown("**3. PO/GRN Register:** Item Code, PO Date, GRN Date, Pending Qty.")

tab1, tab2 = st.tabs(["📂 Multi-File Upload", "📘 Single Workbook Upload"])
df_master, df_issues, df_po = None, None, None

with tab1:
    c1, c2, c3 = st.columns(3)
    f_m = c1.file_uploader("Upload Item Master", type=['csv', 'xlsx'])
    f_i = c2.file_uploader("Upload MTN Issues", type=['csv', 'xlsx'])
    f_p = c3.file_uploader("Upload PO/GRN Register", type=['csv', 'xlsx'])
    if f_m and f_i and f_p:
        df_master = pd.read_csv(f_m) if f_m.name.endswith('.csv') else pd.read_excel(f_m)
        df_issues = pd.read_csv(f_i) if f_i.name.endswith('.csv') else pd.read_excel(f_i)
        df_po = pd.read_csv(f_p) if f_p.name.endswith('.csv') else pd.read_excel(f_p)

with tab2:
    f_all = st.file_uploader("Upload 3-Sheet Workbook", type=['xlsx'])
    if f_all:
        xls = pd.ExcelFile(f_all)
        if len(xls.sheet_names) >= 3:
            df_master = pd.read_excel(xls, sheet_name=0)
            df_issues = pd.read_excel(xls, sheet_name=1)
            df_po = pd.read_excel(xls, sheet_name=2)

# --- EXECUTION ---
if df_master is not None and df_issues is not None and df_po is not None:
    st.subheader("🛠️ Column Mapping Assistant")
    with st.expander("Verify Column Mappings", expanded=True):
        m1, m2, m3 = st.columns(3)
        with m1: df_master = get_user_column_mapping(df_master, ['Item_Code', 'Description', 'Category', 'Stores_Physical_Stock', 'Unit_Cost', 'Supplier_MOQ', 'Pack_Size', 'Default_Lead_Days'], "Item Master")
        with m2: df_issues = get_user_column_mapping(df_issues, ['Item_Code', 'Date', 'Qty_Issued'], "MTN Issues")
        with m3: df_po = get_user_column_mapping(df_po, ['Item_Code', 'PO_Date', 'GRN_Date', 'Open_Pending_Qty'], "PO Register")

    if st.button("🚀 Run Optimization Engine", type="primary"):
        with st.spinner("Crunching inventory statistics and working capital models..."):
            results = calculate_inventory_metrics(df_master, df_issues, df_po, csl_param, holding_cost_pct, po_admin_cost)
            
            # --- 1. CRISP WORKING CAPITAL KPI HERO CARDS ---
            st.markdown("---")
            st.markdown("### 💼 Working Capital & Risk Executive Summary")
            
            crit_count = len(results[results['Action_Status'] == 'CRITICAL STOCKOUT THREAT'])
            order_count = len(results[results['Action_Status'] == 'RELEASE PURCHASE ORDER'])
            total_action_needed = crit_count + order_count
            total_po_spend = results['Order_Spend_Required'].sum()
            total_locked_capital = results['Excess_Capital_Locked'].sum()
            
            kpi_html = f"""
            <div class="kpi-container">
                <div class="kpi-card">
                    <div class="kpi-title">⚠️ Action Required SKUs</div>
                    <div class="kpi-value">{total_action_needed} <span style="font-size:16px; font-weight:500; color:#94A3B8;">Items</span></div>
                    <span class="kpi-badge badge-red">{crit_count} Stockout Threats</span>
                    <span class="kpi-badge badge-amber">{order_count} Reorder Triggers</span>
                </div>
                <div class="kpi-card">
                    <div class="kpi-title">💳 Immediate Procurement Spend</div>
                    <div class="kpi-value">₹{total_po_spend:,.2f}</div>
                    <span class="kpi-badge badge-amber">PO Capital Required Today</span>
                </div>
                <div class="kpi-card">
                    <div class="kpi-title">🔓 Idle Capital Locked in Excess Stock</div>
                    <div class="kpi-value">₹{total_locked_capital:,.2f}</div>
                    <span class="kpi-badge badge-green">Recoverable Free Cash</span>
                </div>
            </div>
            """
            st.markdown(kpi_html, unsafe_allow_html=True)
            
            # --- 2. CLEAN ACTION TRIAGE TABLE ---
            st.markdown("### 🎯 Inventory Action Triage Matrix")
            
            def highlight_status(val):
                colors = {
                    'CRITICAL STOCKOUT THREAT': 'background-color: #7F1D1D; color: #FCA5A5; font-weight: bold;',
                    'RELEASE PURCHASE ORDER': 'background-color: #78350F; color: #FDE68A; font-weight: bold;',
                    'EXPEDITE IN-TRANSIT GRN': 'background-color: #1E3A8A; color: #BFDBFE; font-weight: bold;',
                    'HEALTHY INVENTORY': 'background-color: #064E3B; color: #6EE7B7; font-weight: bold;',
                }
                return colors.get(val, '')

            # Format integers cleanly without decimals
            display_df = results[[
                'Item_Code', 'Description', 'ABC_Class', 'Stores_Physical_Stock', 
                'Open_Pending_Qty', 'Safety_Stock', 'ROP', 
                'Optimal_Order_Qty', 'Action_Status'
            ]].copy()
            
            display_df = display_df.rename(columns={
                'Safety_Stock': 'Recommended Safety Stock',
                'ROP': 'Reorder Point',
                'Optimal_Order_Qty': 'Optimal Order Qty'
            })
            
            st.dataframe(
                display_df.style.map(highlight_status, subset=['Action_Status']),
                use_container_width=True
            )
            
            # --- 3. HIGH-RESOLUTION DUAL CHARTS ---
            st.markdown("---")
            with st.expander("📊 Visual Analytics: Stock Health vs. ROP Buffer", expanded=True):
                c_tab1, c_tab2 = st.tabs(["⚡ Normalized Stock Health (% of ROP)", "📦 Absolute Unit Comparison"])
                
                with c_tab1:
                    # Ratio chart solves the distortion where FST-102 swamps small items
                    fig_ratio = px.bar(
                        results,
                        x='Item_Code',
                        y='Stock_Health_Ratio',
                        color='Action_Status',
                        color_discrete_map={
                            'CRITICAL STOCKOUT THREAT': '#EF4444',
                            'RELEASE PURCHASE ORDER': '#F59E0B',
                            'EXPEDITE IN-TRANSIT GRN': '#3B82F6',
                            'HEALTHY INVENTORY': '#10B981'
                        },
                        title="Stock Health Index (% of Reorder Point Covered by Physical Stock)",
                        labels={'Stock_Health_Ratio': 'Stock / ROP (%)', 'Item_Code': 'SKU'}
                    )
                    fig_ratio.add_hline(y=100, line_dash="dash", line_color="#F8FAFC", annotation_text="100% ROP Threshold")
                    fig_ratio.update_layout(
                        paper_bgcolor='#1E293B',
                        plot_bgcolor='#1E293B',
                        font=dict(color='#F8FAFC'),
                        height=420
                    )
                    st.plotly_chart(fig_ratio, use_container_width=True)
                
                with c_tab2:
                    fig_units = go.Figure()
                    fig_units.add_trace(go.Bar(x=results['Item_Code'], y=results['Stores_Physical_Stock'], name='Physical Stock', marker_color='#38BDF8'))
                    fig_units.add_trace(go.Bar(x=results['Item_Code'], y=results['Safety_Stock'], name='Safety Stock', marker_color='#F43F5E'))
                    fig_units.add_trace(go.Bar(x=results['Item_Code'], y=results['ROP'], name='Reorder Point', marker_color='#FBBF24'))
                    fig_units.update_layout(
                        barmode='group',
                        paper_bgcolor='#1E293B',
                        plot_bgcolor='#1E293B',
                        font=dict(color='#F8FAFC'),
                        title="Physical Units vs. Safety Buffer & ROP",
                        height=420
                    )
                    st.plotly_chart(fig_units, use_container_width=True)

            # --- 4. EXCEL EXPORT & ADVISORY CTA ---
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                results.to_excel(writer, sheet_name='Inventory_Optimization', index=False)
                wb, ws = writer.book, writer.sheets['Inventory_Optimization']
                h_fmt = wb.add_format({'bold': True, 'bg_color': '#0F172A', 'font_color': '#FFFFFF', 'border': 1})
                for col_idx, val in enumerate(results.columns):
                    ws.write(0, col_idx, val, h_fmt)
                    ws.set_column(col_idx, col_idx, max(len(str(val)) + 4, 12))

            st.divider()
            d1, d2 = st.columns([1, 1])
            with d1:
                st.download_button(
                    "📥 Download Formatted Audit Report (Excel)",
                    data=buf.getvalue(),
                    file_name=f"Inventory_Optimization_Report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            with d2:
                st.link_button("📝 Share Feedback & Feature Request", "https://docs.google.com/forms/d/e/1FAIpQLSee7lV13AZ4594w2ZmzvB4mfUOMCOLPBbhQss-I37ng_gkksA/viewform?usp=sf_link")

            st.markdown("""
            <div class="consult-banner">
                <h4 style="margin:0 0 8px 0; color:#FFFFFF;">🤝 Want a Custom Plant or Warehouse Inventory Audit?</h4>
                <p style="margin:0; font-size:14px; color:#E0E7FF; line-height:1.5;">
                    Dealing with supplier delays, dead stock, or want automated Tally / ERP synchronization built for your operations? 
                    Get a 1-on-1 expert diagnostic to optimize working capital and service levels.
                </p>
            </div>
            """, unsafe_allow_html=True)