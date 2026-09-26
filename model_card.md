# Model Card: The Fair-Value Clienteling Engine

**Version:** 1.0.0  
**Date:** September 2026  
**Auditor / Developer:** Senior Model-Risk & Responsible AI Analytics Function  
**Governance Framework:** Aligned with Mitchell et al. (2019) Model Cards, EU AI Act Risk Assessment, and US EEOC 4/5ths Disparate Impact Doctrine.

---

## 1. Model Details

* **Model Family:** Hybrid Probabilistic Life-Cycle & Supervised Risk Engine.
* **Component 1 (Transaction Cadence):** Beta-Geometric / Negative Binomial Distribution (BG/NBD) via `lifetimes` library ($r = 0.6692, \alpha = 56.1511, a \approx 0, b \approx 0$).
* **Component 2 (Monetary Spend):** Gamma-Gamma Submodel ($p = 2.1108, q = 3.4373, v = 479.6191$).
* **Component 3 (Uncertainty Estimation):** 200-iteration Bootstrapped Monte Carlo Resampling (90% Empirical Confidence Intervals).
* **Component 4 (Churn Classification):** Random Forest Classifier (100 estimators, max depth = 5) and Standardized Logistic Regression.
* **Component 5 (Fairness Post-Processor):** Empirical Basket-Value Recalibration along the Price-of-Fairness Frontier ($\lambda \in [0.0, 1.0]$).

---

## 2. Intended Use

* **Primary Intended Uses:**
  * Prioritizing high-touch luxury clienteling invitations, bespoke gifting, and dedicated client-advisor allocation based on 6-month forward CLV.
  * Detecting accounts at risk of defection (90-day inactivity threshold) to trigger proactive service recovery.
  * Establishing transparent, auditable compliance documentation for marketing and model-risk committees.
* **Out-of-Scope / Prohibited Uses:**
  * Automated denial of service, credit underwriting, pricing discrimination, or algorithmic cancellation of accounts.
  * Direct extrapolation to contractual subscription businesses (the model is strictly engineered for non-contractual e-commerce).
  * Sole reliance on raw point estimates without review of the accompanying 90% confidence margin.

---

## 3. Factors, Demographic Proxies & Subgroups

* **Protected / Sensitive Attribute:** `Country` (37 international jurisdictions, grouped into UK vs. International, and individual national markets).
* **Critical Limitation of Proxy Attribute:** `Country` serves as an operational proxy for cross-border logistics friction, regional purchasing power, and currency exposure. It is **not** an individualized demographic or racial attribute. Model-risk auditors must recognize that country-level proxies capture institutional logistics differences rather than innate consumer traits.
* **Intersectional Dimensions:** `Country` $\times$ `Historical Spend Tier` (Low: $< £500$, Mid: £500–£2,000, High: $> £2,000$).

---

## 4. Training Data & Preprocessing Integrity

* **Source Dataset:** UCI Machine Learning Repository "Online Retail" (Transactions from Dec 2010 to Dec 2011).
* **Data Cleaning & Exclusion Audit:**
  * Raw Ingested Records: **541,909**
  * Excluded — Missing `CustomerID`: **135,080 rows (24.93%)**
  * Excluded — Duplicate Invoices: **5,225 rows (0.96%)**
  * Excluded — Cancellations & Returns: **8,872 rows (1.64%)**
  * Excluded — Zero/Negative Prices: **40 rows (0.01%)**
  * **Final Clean Dataset:** **392,692 rows (72.46% remaining)** across **4,338 unique identified customers** and **37 countries** (£8,887,208.89 gross revenue).
* **Known Data Limitations & Selection Bias:**
  * Dropping 24.93% of records due to absent `CustomerID` creates an inherent selection bias: anonymous guest checkouts are systematically invisible to the clienteling engine.
  * Geographic Distribution is heavily imbalanced: UK represents **90.36% of all customers** ($N = 3,920$), with international markets having much smaller sample sizes (Germany: 94, France: 87, Spain: 28, Switzerland: 20, Portugal: 19).

---

## 5. Quantitative Performance Summary

### 5.1. Churn Classification Performance (25% Stratified Holdout Test Set / 1,085 Customers)

Evaluated at the default decision threshold ($\tau = 0.50$):

| Metric | Random Forest (Selected Model) | Logistic Regression |
| :--- | :---: | :---: |
| **ROC-AUC** | **0.9562** | 0.9387 |
| **Accuracy** | **87.56%** | 86.45% |
| **Active Class (0) Precision / Recall** | 88.68% / 93.22% | 90.68% / 88.80% |
| **Churn Class (1) Precision / Recall** | 84.92% / 76.24% | 78.51% / 81.77% |
| **Churn Class (1) F1-Score** | **0.8035** | 0.8011 |
| **Confusion Matrix (TN / FP / FN / TP)** | 674 / 49 / 86 / 276 | 642 / 81 / 66 / 296 |

### 5.2. Probabilistic CLV Distribution (4,338 Customers, 200 Bootstraps)

* **Mean 6-Month Forward CLV:** £1,020.36 (Median: £503.40, Max: £117,388.40)
* **Average 90% Confidence Interval Range:** [£991.28 – £1,045.31] (Mean CI Width: £54.04, Max CI Width: £19,167.36)
* **Relative Uncertainty:** Mean 7.2%, Median 7.6%, Max 27.9%

---

## 6. Algorithmic Fairness & Subgroup Audit Findings

### 6.1. Single-Attribute Audit (Phase 5)
* Aggregate International Disparate Impact Ratio: $\text{DIR} = 1.4755$ (Passes 80% rule on surface).
* Granular Country Penalties:
  * **Switzerland ($N=20$):** Actual top-tier spenders = 40.0%; Model VIP rate = 30.0% (**-10.0% penalty**); CLV-to-spend ratio = 0.325 (vs UK 0.512).
  * **Portugal ($N=19$):** Actual top-tier spenders = 31.6%; Model VIP rate = 21.1% (**-10.5% penalty**).
  * **Spain ($N=28$):** Model VIP rate = 21.4% vs 25.0% actual; Churn over-predicted by +3.57%.

### 6.2. Econometric Causal Attribution (Phase 6)
* Multivariable regression controlling for spend, orders, tenure, and product category mix proves that country coefficients are statistically non-significant ($p = 0.392$ for Switzerland, $p = 0.450$ for Spain).
* **Verdict:** The disparity is **not** active country prejudice, but **structural feature-weighting bias**: the BG/NBD architecture places **2.53x higher elasticity on purchase frequency ($\beta = +0.8405$) than on spend ($\beta = +0.3318$)**, severely penalizing cross-border shoppers who consolidate high-value purchases into fewer shipments.

### 6.3. Intersectional Audit (Phase 7)
* **Mid-Spend Tier (£500–£2k, 1,678 customers):**
  * UK VIP Selection = 9.48% | International VIP Selection = 6.47%
  * **Within-Tier Disparate Impact Ratio = 0.6824 (STATUTORY BREACH of the 0.80 Four-Fifths Rule 🚩)**.
* **High-Spend Tier (>£2k, 896 customers):**
  * UK Churn Alert Rate = 1.05% | International Churn Alert Rate = 7.52% (**7.17x Relative Churn Burden on International 🚩**).

---

## 7. Bias Mitigation: The Price of Fairness Frontier (Phase 8)

* **Recalibration Policy:**
  $$\text{CLV}_{\text{Fair}} = \text{CLV}_{\text{Raw}} \times \left[1 + \lambda \cdot \text{Basket Purchasing Power Index}\right]$$
* **The Trade-off Curve:**

| Policy ($\lambda$) | Mid-Tier DIR | Compliance Status | Theoretical Model CLV Forgone | Net Realized Customer Spend Gained | Accounts Promoted |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **0.0 (Uncorrected)** | **0.6824** | **FAIL ($< 0.80$)** | £0.00 (0.00%) | £0.00 | 0 |
| **0.4 (Recommended)** | **0.8808** | **PASS ($\ge 0.80$)** | **-£670.94 (-0.02%)** | **+£2,793.87** | **8 accounts** |
| **1.0 (Full Parity)** | **1.3240** | **PASS ($\ge 0.80$)** | **-£3,723.44 (-0.13%)** | **+£11,159.86** | **19 accounts** |

* **Auditor Conclusion:** Correcting the bias yields a **negative price of fairness** in realized commercial terms. The 19 promoted accounts average **£2,258.23 in spend (£1,149 per order)** compared to **£1,670.87 (£379 per order)** for the displaced accounts, generating a net gain of **+£11,159.86 in captured purchasing power**.

---

## 8. Governance Recommendations & Monitoring Protocol

1. **Mandatory Threshold Policy:** Deploy $\lambda = 0.40$ as the production operating baseline for VIP clienteling allocations.
2. **Confidence Margin Governance:** Prohibit personal client advisor commitments on accounts where the 90% confidence width exceeds 25% of point CLV without manual tenure verification.
3. **Continuous Auditing:** Re-run intersectional within-tier disparate impact checks every fiscal quarter using `export_powerbi.csv` to ensure no sub-group DIR falls below 0.80 as customer acquisition scales.

---
*Approved by Model Governance & Responsible AI Review Board*
