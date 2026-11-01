# RM Inventory Optimization Engine - User Documentation

## Overview
The RM Inventory Optimization Engine is a professional-grade tool designed to assist manufacturing plants in optimizing their Raw Material (RM) inventory. By utilizing dual-stochastic demand and lead-time modeling, it helps procurement teams reduce stockout risks, optimize safety stock levels, and minimize annual holding costs.

---

## 1. Prerequisites
- **Python 3.10+** installed on your system.
- **Dependencies**: The application requires `streamlit`, `pandas`, `numpy`, `scipy`, and `xlsxwriter`. Install them via:
  ```bash
  pip install -r requirements.txt
  ```

---

## 2. Data Preparation
To ensure accurate optimization, prepare your data in three separate formats or a single workbook (Excel/CSV):

### A. Item Master (`template_item_master_stock.csv`)
*   **Item_Code**: Unique SKU.
*   **Description**: Brief description.
*   **Category**: Classification (e.g., Fasteners, Raw Materials).
*   **Stores_Physical_Stock**: Current stock on hand.
*   **Unit_Cost**: Cost per unit.
*   **Supplier_MOQ**: Minimum Order Quantity.
*   **Pack_Size**: Ordering increment size.
*   **Default_Lead_Days**: Estimated lead time in days.

### B. MTN Issues (`template_store_issues_mtn.csv`)
*   **Item_Code**: Corresponding SKU.
*   **Date**: Date of issuance.
*   **Qty_Issued**: Quantity consumed on that date.

### C. PO/GRN Register (`template_po_grn_register.csv`)
*   **Item_Code**: Corresponding SKU.
*   **PO_Date**: Date order was placed.
*   **GRN_Date**: Date received (leave empty for open orders).
*   **Open_Pending_Qty**: Remaining quantity to be received.

---

## 3. How to Run
1. Navigate to the project directory.
2. Launch the application:
   ```bash
   streamlit run app.py
   ```
3. Open your browser to the URL displayed in the terminal (usually `http://localhost:8501`).

---

## 4. Operational Guide
- **Optimization Parameters (Sidebar)**:
  - **Cycle Service Level (CSL)**: Set your target service level (85%–99.9%). Higher levels require higher safety stock.
  - **Holding Cost %**: Annual cost to hold inventory.
  - **PO Admin Cost**: The fixed cost associated with placing a purchase order.
- **Triage Statuses**:
  - **CRITICAL STOCKOUT THREAT**: Physical stock is below Safety Stock.
  - **RELEASE PURCHASE ORDER**: Net stock (Phys + Open) is below ROP.
  - **EXPEDITE IN-TRANSIT GRN**: Physical is below ROP, but incoming orders will fix it.
  - **HEALTHY INVENTORY**: Stock levels are sufficient.

---

## 5. Deployment for Commercial Use
*   **Cloud Hosting**: You can deploy this app to [Streamlit Community Cloud](https://share.streamlit.io/) for free by connecting your GitHub repository.
*   **Containerization**: For enterprise use, wrap the app in a **Docker** container to ensure consistent environment performance.
*   **Security**: Implement user authentication if handling sensitive plant supply chain data.
