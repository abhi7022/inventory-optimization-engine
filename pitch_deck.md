# Plant RM Inventory Optimization Engine

## 1. Value Proposition
* **Problem**: Overstocking eats capital; stockouts stop production lines.
* **Solution**: A dual-stochastic engine that dynamically models lead-time variability and demand volatility.
* **Impact**: Reduce safety stock by 15-25% while simultaneously decreasing stockout frequency.

## 2. Key Engine Features
* **Dual-Stochastic Modeling**: Safety Stock = $Z \times \sqrt{\mu_L \sigma_D^2 + \mu_D^2 \sigma_L^2}$.
* **Constrained EOQ**: Automated ordering that respects real-world MOQs and Pack Sizes.
* **Triage-Driven Workflow**:
    * 🔴 **Critical**: Physical < SS
    * 🟠 **Release PO**: (Physical + Open) <= ROP
    * 🔵 **Expedite**: Physical <= ROP, but incoming GRN solves it
    * 🟢 **Healthy**: Everything is in check

## 3. The Workflow
1. **Upload**: Drop-in Excel/CSV support for Master, MTN, and PO register files.
2. **Optimize**: Real-time dashboard with KPI tracking.
3. **Execute**: Export a fully formatted Action Plan sheet for your procurement team.

---
*Built for Scale | Intelligent Inventory | Precision Manufacturing*
