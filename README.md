# The Fair-Value Clienteling Engine

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Audited: Algorithmic Fairness](https://img.shields.io/badge/Audit-EEOC%204%2F5ths%20%7C%20EU%20AI%20Act-green.svg)](model_card.md)

An audited, responsible AI customer lifetime value (CLV) and churn prediction engine designed for luxury and high-end retail clienteling. This project demonstrates how standard CLV models systematically penalize cross-border accounts, conducts an econometric causal audit, and implements a negative-cost bias correction along the **Price-of-Fairness Frontier**.

---

## 📌 Executive Summary

Retail CRM algorithms allocate high-touch outreach, dedicated client advisors, and VIP gifting based on predicted CLV. However, traditional probabilistic models (BG/NBD) place **2.53x higher elasticity on purchase frequency than on monetary spend**.

* **The Bias:** International luxury shoppers who consolidate purchases into high-value bulk orders (averaging £1,149/order vs £379 domestic) are misclassified as disengaged. In the core middle-spend tier (£500–£2,000), international accounts suffer an illegal **Disparate Impact Ratio of 0.682** (< 0.80 regulatory floor) despite outspending UK customers.
* **The Solution:** A post-processing basket purchasing-power recalibration ($\lambda = 0.40$) restores compliance ($\text{DIR} = 0.881$) at a nominal model cost of just **-0.02%**, while **increasing captured real spend by +£11,160**.

---

## 🏗️ Project Architecture & Deliverables

The entire project is engineered to remain **strictly under 10 files** and **under 5 MB total git footprint** for immediate GitHub portability and instant Vercel deployment:

```
├── .gitignore                               # Ignores raw 44MB CSV; keeps repo lightweight (<5MB)
├── README.md                                # Project overview, quickstart & portfolio documentation
├── business_memo.md                         # Executive memo for CMO, CRM & Clienteling leadership
├── model_card.md                            # Formal compliance model card (Mitchell et al., 2019)
├── engine.py                                # Master end-to-end pipeline (Phases 1-9)
├── index.html                               # High-Performance Interactive Web App (Vercel-native)
├── requirements.txt                         # 1-step dependency installation manifest
└── data/
    ├── cleaned_online_retail.parquet        # Cleaned transactional records (392,692 rows)
    └── recalibrated_clienteling_portfolio.parquet # Master customer analytics & fairness table
```

---

## 🔬 The 9 Build Phases

| Phase | Milestone | Methodology & Technical Scope | Key Finding / Output |
| :---: | :--- | :--- | :--- |
| **1** | **Data Cleaning** | Audited 541,909 raw transactions; removed guest checkouts (24.9%), duplicates (1.0%), cancellations (1.6%), and bad prices. | 392,692 clean transactions remaining (72.5%) across 4,338 customers and 37 countries (£8.89M spend). |
| **2** | **RFM Segmentation** | Snapshot date `2011-12-10`; rank quintile scoring (1-5); mapped 10 clienteling tiers. | Top 26.3% (Champions) command **66.5% of all enterprise revenue** (£5.91M); international accounts 32.3% dormant. |
| **3** | **Probabilistic CLV & Uncertainty** | Fitted `BetaGeoFitter` & `GammaGammaFitter` on 2,790 repeat buyers; evaluated **200 Monte Carlo bootstrap refits**. | Mean 6M forward CLV: £1,020 (90% CI: [£991 - £1,045]); international accounts have 74% higher forward CLV. |
| **4** | **Churn Classification** | Derived **90-day inactivity window** from 14,224 empirical repeat cycles (88th percentile); trained Random Forest & Logistic Regression (no target leakage). | Random Forest holdout accuracy: **87.56%**, ROC-AUC: **0.9562**, Churn F1: **0.8035** (purchase velocity drives 41.7% of signal). |
| **5** | **Single-Attribute Fairness** | Evaluated Demographic Parity ($\Delta_{\text{DP}}$) and Disparate Impact Ratio (DIR). | Aggregate DIR passes (1.48), but **Switzerland (-10.0% VIP gap)**, **Portugal (-10.5%)**, and **Spain (-3.6%)** are penalized. |
| **6** | **Causal Check** | Estimated multivariable OLS ($R^2 = 0.898$) controlling for real spend, orders, tenure, unit price, and product mix. | Country coefficients are non-significant ($p > 0.39$); proves disparity is **structural feature-weighting bias** (2.53x frequency elasticity). |
| **7** | **Intersectional Audit** | Crossed Country with Spend Tier (Low $<£500$, Mid £500-£2k, High $>£2k$). | **Mid-Tier International DIR = 0.6824 (Statutory Failure 🚩)**; High-Spend International accounts face **7.17x higher false churn alerts**. |
| **8** | **Price-of-Fairness Frontier** | Post-processing basket recalibration ($\lambda \in [0, 1]$) across top-20% VIP budget ($K = 868$). | **Negative Price of Fairness:** Reaching compliance ($\lambda=0.4$) costs -0.02% model CLV while **gaining +£11,160 in real customer spend**. |
| **9** | **Governance Deliverables** | Executive Business Memo, Compliance Model Card, and Power BI CSV export. | Production-ready deliverables bridging marketing leadership and compliance auditors. |

---

## 🚀 Quickstart & Reproduction

### 1. View Live Web Dashboard (Zero Installation Required)
* **Live on Vercel:** Open the repository on [Vercel](https://vercel.com) to deploy instantly with zero configuration.
* **Run Locally:** Double-click `index.html` (or run `start index.html` in terminal) to launch the interactive platform in any browser.

### 2. Run the Python Pipeline (For Data Scientists)
```bash
pip install -r requirements.txt
python engine.py --all
```

---

## 📊 Power BI Dashboard Fields (`export_powerbi.csv`)

The exported dataset contains 4,338 records with 22 attributes formatted for immediate dashboard visualization:
* `CustomerID`, `Country`, `Region_Cohort` (UK vs International)
* `RFM_Segment`, `Spend_Tier` (Low, Mid, High)
* `Historical_Spend_GBP`, `Total_Orders`, `Spend_Per_Order_GBP`
* `Recency_Days`, `Customer_Tenure_Days`
* `CLV_Raw_Point_GBP`, `CLV_Lower_90_GBP`, `CLV_Upper_90_GBP`, `CLV_Uncertainty_Margin_GBP`
* `CLV_Fair_Corrected_GBP`, `Actual_Churn_Status`, `Predicted_Churn_Probability`, `Churn_Risk_Tier`
* `VIP_Status_Raw`, `VIP_Status_Fair`, `Clienteling_Tier_Movement` (Promoted, Demoted, Maintained)
* `Fairness_Audit_Flag` (Identifies under-selected and devalued jurisdictions)

---

## ⚖️ Governance & Ethical Disclaimers
* **Proxy Attribute Limitation:** `Country` is an operational proxy for cross-border logistics friction and currency dynamics, not an innate personal demographic attribute.
* **Selection Bias:** Dropping guest checkouts (24.9% of transactions) means anonymous purchasers are excluded from clienteling.
* **Licensing:** The dataset is sourced from the UCI Machine Learning Repository (Online Retail). Code is licensed under the MIT License.
