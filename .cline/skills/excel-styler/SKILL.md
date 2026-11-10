---
name: excel-styler
description: Generates executive-ready, audit-grade Excel (.xlsx) workbooks with openpyxl, complete with custom palettes, zebra-striping, and auto-column fitting.
---

# Excel Styler Skill

When writing Python code that exports or formats an Excel workbook:
1. Header Rows:
   - Dark Navy fill (#1F4E78), bold white text, height 26pt, centered vertically and horizontally.
2. Data Rows & Grid:
   - Thin light-gray cell borders (#E2E8F0).
   - Subtle zebra striping on alternating rows (#F8FAFC vs #FFFFFF).
3. Number Formatting:
   - Currency: "$#,##0.00" or "?#,##0.00"
   - Whole numbers / inventory units: #,##0
   - Percentages / service levels: 0.0%
4. Auto-Fit Widths:
   - Automatically iterate through columns and set width to max length + 4 to prevent clipped text or ### errors.
