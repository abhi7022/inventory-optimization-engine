---
name: ui-designer
description: Expert UI/UX design directives for crafting modern, high-contrast, executive Streamlit dashboards and web layouts.
---

# UI Designer Skill

When generating or refactoring frontend interfaces (Streamlit / HTML / CSS):
1. Layout & Grid:
   - Always enforce wide mode: st.set_page_config(layout="wide").
   - Group related inputs and operational stats inside bordered cards: st.container(border=True).
   - Separate distinct logical steps using st.divider().
   - Hide technical diagnostics, tracebacks, and large raw matrices inside st.expander().
2. Color Palette Hierarchy:
   - Surfaces & Text: Slate / Corporate Navy (#0F172A, #1E293B) with high contrast text.
   - Status Badges:
     - Critical / Threat: #FEE2E2 background, #991B1B text.
     - Reorder / Indent: #FEF3C7 background, #92400E text.
     - Healthy / Normal: #D1FAE5 background, #065F46 text.
3. Typography:
   - Pair metric values with clear baseline descriptions.
