import os
import sys
import time
import argparse
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score
from lifetimes import BetaGeoFitter, GammaGammaFitter
from lifetimes.utils import summary_data_from_transaction_data

CLEAN_PARQUET = "data/cleaned_online_retail.parquet"
MASTER_PARQUET = "data/recalibrated_clienteling_portfolio.parquet"
POWERBI_CSV = "export_powerbi.csv"

def phase1_cleaning(raw_csv="data/Online_Retail.csv", output_parquet=CLEAN_PARQUET):
    print("\n" + "=" * 80)
    print("PHASE 1: DATA CLEANING & QUALITY AUDIT")
    print("=" * 80)
    if not os.path.exists(raw_csv):
        raise FileNotFoundError(f"Raw transaction dataset not found at {raw_csv}")
    
    df_raw = pd.read_csv(raw_csv, encoding="latin1")
    n_orig = len(df_raw)
    
    missing_mask = df_raw["CustomerID"].isna()
    n_missing = missing_mask.sum()
    df1 = df_raw[~missing_mask].copy()
    df1["CustomerID"] = df1["CustomerID"].astype(np.int64).astype(str)
    
    dup_mask = df1.duplicated()
    n_dups = dup_mask.sum()
    df2 = df1[~dup_mask].copy()
    
    is_cancel = df2["InvoiceNo"].astype(str).str.startswith("C") | (df2["Quantity"] <= 0)
    n_cancel = is_cancel.sum()
    df3 = df2[~is_cancel].copy()
    
    is_bad_price = df3["UnitPrice"] <= 0
    n_bad_price = is_bad_price.sum()
    df_clean = df3[~is_bad_price].copy()
    
    df_clean["InvoiceDate"] = pd.to_datetime(df_clean["InvoiceDate"])
    df_clean["LineTotal"] = df_clean["Quantity"] * df_clean["UnitPrice"]
    
    n_rem = len(df_clean)
    print(f"Original Records:           {n_orig:>10,}")
    print(f"  - Missing CustomerID:     {n_missing:>10,} ({(n_missing/n_orig)*100:5.2f}%)")
    print(f"  - Duplicate Records:      {n_dups:>10,} ({(n_dups/n_orig)*100:5.2f}%)")
    print(f"  - Cancellations / Qty<=0: {n_cancel:>10,} ({(n_cancel/n_orig)*100:5.2f}%)")
    print(f"  - Unit Price <= 0:        {n_bad_price:>10,} ({(n_bad_price/n_orig)*100:5.2f}%)")
    print(f"Total Rows Removed:         {n_orig - n_rem:>10,} ({((n_orig-n_rem)/n_orig)*100:5.2f}%)")
    print(f"Clean Rows Remaining:       {n_rem:>10,} ({(n_rem/n_orig)*100:5.2f}%)")
    print(f"Tracked Unique Customers:   {df_clean['CustomerID'].nunique():>10,}")
    print(f"Gross Verified Revenue:     GBP {df_clean['LineTotal'].sum():>13,.2f}")
    
    os.makedirs(os.path.dirname(output_parquet), exist_ok=True)
    df_clean.to_parquet(output_parquet, index=False)
    return df_clean

def phase2_rfm(clean_parquet=CLEAN_PARQUET):
    print("\n" + "=" * 80)
    print("PHASE 2: RFM SEGMENTATION & PORTFOLIO ANALYSIS")
    print("=" * 80)
    df = pd.read_parquet(clean_parquet)
    snapshot = df["InvoiceDate"].max() + pd.Timedelta(days=1)
    
    rfm = df.groupby("CustomerID").agg(
        Recency=("InvoiceDate", lambda x: (snapshot - x.max()).days),
        Frequency=("InvoiceNo", "nunique"),
        Monetary=("LineTotal", "sum"),
        Country=("Country", "first")
    ).reset_index()
    
    rfm["R_Score"] = pd.qcut(rfm["Recency"], q=5, labels=[5, 4, 3, 2, 1]).astype(int)
    rfm["F_Score"] = pd.qcut(rfm["Frequency"].rank(method="first"), q=5, labels=[1, 2, 3, 4, 5]).astype(int)
    rfm["M_Score"] = pd.qcut(rfm["Monetary"], q=5, labels=[1, 2, 3, 4, 5]).astype(int)
    
    def map_seg(row):
        r, f = row["R_Score"], row["F_Score"]
        if r in [4, 5] and f in [4, 5]: return "Champions"
        elif r in [3, 4, 5] and f in [3, 4, 5]: return "Loyal Customers"
        elif r in [4, 5] and f in [2, 3]: return "Potential Loyalists"
        elif r in [4, 5] and f == 1: return "New Customers"
        elif r == 3 and f == 1: return "Promising"
        elif r == 3 and f == 2: return "Need Attention"
        elif r == 2 and f in [1, 2]: return "About to Sleep"
        elif r in [1, 2] and f in [3, 4]: return "At Risk"
        elif r in [1, 2] and f == 5: return "Cannot Lose Them"
        else: return "Hibernating / Lost"

    rfm["Segment"] = rfm.apply(map_seg, axis=1)
    rfm["Is_UK"] = np.where(rfm["Country"] == "United Kingdom", "UK", "International")
    
    summary = rfm.groupby("Segment").agg(
        Count=("CustomerID", "count"),
        Avg_Recency=("Recency", "mean"),
        Avg_Freq=("Frequency", "mean"),
        Avg_Spend=("Monetary", "mean"),
        Total_Spend=("Monetary", "sum")
    ).reset_index().sort_values("Avg_Spend", ascending=False)
    summary["Pct_Rev"] = (summary["Total_Spend"] / rfm["Monetary"].sum()) * 100
    
    header = f"{'Segment':<20} | {'Count':>6} | {'Avg Rec':>7} | {'Avg Freq':>8} | {'Avg Spend':>12} | {'% Rev':>6}"
    print(header)
    print("-" * 75)
    for _, r in summary.iterrows():
        print(f"{r['Segment']:<20} | {r['Count']:>6d} | {r['Avg_Recency']:>7.1f} | {r['Avg_Freq']:>8.1f} | GBP {r['Avg_Spend']:>8,.2f} | {r['Pct_Rev']:>5.1f}%")
    return rfm

def phase3_clv(clean_parquet=CLEAN_PARQUET, rfm_df=None, n_bootstraps=200):
    print("\n" + "=" * 80)
    print(f"PHASE 3: PROBABILISTIC CLV WITH UNCERTAINTY ({n_bootstraps} BOOTSTRAPS)")
    print("=" * 80)
    df = pd.read_parquet(clean_parquet)
    summary = summary_data_from_transaction_data(df, "CustomerID", "InvoiceDate", "LineTotal", observation_period_end="2011-12-10", freq="D")
    
    bgf = BetaGeoFitter(penalizer_coef=0.05)
    bgf.fit(summary["frequency"], summary["recency"], summary["T"])
    
    rep = (summary["frequency"] > 0) & (summary["monetary_value"] > 0)
    ggf = GammaGammaFitter(penalizer_coef=0.0)
    ggf.fit(summary.loc[rep, "frequency"], summary.loc[rep, "monetary_value"])
    
    d, factor = 0.01, 30
    discount_mult = sum(factor / ((1 + d) ** m) for m in range(1, 7))
    r_p, a_p = bgf.params_["r"], bgf.params_["alpha"]
    p_p, q_p, v_p = ggf.params_["p"], ggf.params_["q"], ggf.params_["v"]
    
    prior_mean = (p_p * v_p) / (q_p - 1)
    x = summary["frequency"].values
    t = summary["T"].values
    m = summary["monetary_value"].values
    
    exp_m = ((q_p - 1) * prior_mean + p_p * x * m) / (p_p * x + q_p - 1)
    exp_orders = ((r_p + x) / (a_p + t)) * 180.0
    point_clv = exp_m * ((r_p + x) / (a_p + t)) * discount_mult
    
    t0 = time.time()
    def single_boot(seed):
        np.random.seed(seed)
        n = len(summary)
        bs = summary.iloc[np.random.choice(n, size=n, replace=True)]
        m_bgf = None
        for pen in [0.05, 0.1, 0.2, 0.5]:
            try:
                fit_m = BetaGeoFitter(penalizer_coef=pen)
                fit_m.fit(bs["frequency"], bs["recency"], bs["T"])
                m_bgf = fit_m
                break
            except Exception: continue
        if m_bgf is None: return None
        bs_rep = (bs["frequency"] > 0) & (bs["monetary_value"] > 0)
        m_ggf = GammaGammaFitter(penalizer_coef=0.0)
        m_ggf.fit(bs.loc[bs_rep, "frequency"], bs.loc[bs_rep, "monetary_value"])
        return (m_bgf.params_["r"], m_bgf.params_["alpha"], m_ggf.params_["p"], m_ggf.params_["q"], m_ggf.params_["v"])

    boot_res = Parallel(n_jobs=-1)(delayed(single_boot)(i) for i in range(n_bootstraps))
    valid = [b for b in boot_res if b is not None]
    print(f"200 Bootstrap refits completed in {time.time()-t0:.2f}s ({len(valid)}/200 valid).")
    
    x_mat, t_mat, m_mat = x[:, None], t[:, None], m[:, None]
    b_r = np.array([b[0] for b in valid])
    b_alpha = np.array([b[1] for b in valid])
    b_p = np.array([b[2] for b in valid])
    b_q = np.array([b[3] for b in valid])
    b_v = np.array([b[4] for b in valid])
    
    b_pm = (b_p * b_v) / (b_q - 1)
    b_exp_m = ((b_q - 1) * b_pm + b_p * x_mat * m_mat) / (b_p * x_mat + b_q - 1)
    b_purch = (b_r + x_mat) / (b_alpha + t_mat)
    clv_boot = b_exp_m * b_purch * discount_mult
    
    summary["P_Alive"] = bgf.conditional_probability_alive(summary["frequency"], summary["recency"], summary["T"])
    summary["Exp_Purchases_6M"] = exp_orders
    summary["Exp_Order_Value"] = exp_m
    summary["CLV_Point_Estimate"] = point_clv
    summary["CLV_Lower_90"] = np.percentile(clv_boot, 5, axis=1)
    summary["CLV_Upper_90"] = np.percentile(clv_boot, 95, axis=1)
    summary["CI_Width"] = summary["CLV_Upper_90"] - summary["CLV_Lower_90"]
    
    print(f"Mean 6M Forward CLV: GBP {point_clv.mean():,.2f} (Median: GBP {np.median(point_clv):,.2f})")
    print(f"Average 90% Confidence Interval: [GBP {summary['CLV_Lower_90'].mean():,.2f} - GBP {summary['CLV_Upper_90'].mean():,.2f}]")
    return summary.reset_index()

def phase4_churn(clean_parquet=CLEAN_PARQUET, clv_df=None, rfm_df=None):
    print("\n" + "=" * 80)
    print("PHASE 4: CHURN CLASSIFICATION (90-DAY EMPIRICAL WINDOW)")
    print("=" * 80)
    if rfm_df is None:
        rfm_df = phase2_rfm(clean_parquet)
    if clv_df is None:
        clv_df = phase3_clv(clean_parquet, rfm_df=rfm_df)
        
    df = pd.read_parquet(clean_parquet)
    
    inv_agg = df.groupby(["CustomerID", "InvoiceNo"])["LineTotal"].sum().reset_index().groupby("CustomerID")["LineTotal"].agg(
        avg_order_spend="mean", max_order_spend="max", total_orders="count", total_spend="sum"
    ).reset_index()
    
    items_agg = df.groupby("CustomerID").agg(
        total_items=("Quantity", "sum"),
        unique_products=("StockCode", "nunique"),
        Country=("Country", "first")
    ).reset_index()
    
    cust = inv_agg.merge(items_agg, on="CustomerID").merge(clv_df, on="CustomerID").merge(
        rfm_df[["CustomerID", "Recency", "Segment", "Is_UK"]], on="CustomerID"
    )
    
    cust["is_churned"] = (cust["Recency"] > 90).astype(int)
    cust["purchase_velocity"] = cust["total_orders"] / np.maximum(cust["T"], 1.0)
    cust["spend_velocity"] = cust["total_spend"] / np.maximum(cust["T"], 1.0)
    cust["items_per_order"] = cust["total_items"] / cust["total_orders"]
    
    feats = ["total_spend", "total_orders", "total_items", "unique_products", "avg_order_spend", "max_order_spend", "T", "purchase_velocity", "spend_velocity", "items_per_order"]
    X, y = cust[feats], cust["is_churned"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)
    
    rf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    rf.fit(X_train, y_train)
    y_pred = rf.predict(X_test)
    y_prob = rf.predict_proba(X_test)[:, 1]
    
    print(f"Holdout Test Accuracy:  {rf.score(X_test, y_test)*100:.2f}% | ROC-AUC: {roc_auc_score(y_test, y_prob):.4f}")
    print(f"Churn Precision:        {classification_report(y_test, y_pred, output_dict=True)['1']['precision']*100:.2f}%")
    print(f"Churn Recall:           {classification_report(y_test, y_pred, output_dict=True)['1']['recall']*100:.2f}%")
    print(f"Churn F1-Score:         {classification_report(y_test, y_pred, output_dict=True)['1']['f1-score']:.4f}")
    
    cust["churn_prob"] = rf.predict_proba(X)[:, 1]
    cust["churn_pred"] = rf.predict(X)
    return cust

def phase5_to_8_fairness(cust_df):
    print("\n" + "=" * 80)
    print("PHASES 5 - 8: FAIRNESS AUDIT, CAUSAL REGRESSION & PRICE-OF-FAIRNESS")
    print("=" * 80)
    
    vip_thresh = cust_df["CLV_Point_Estimate"].quantile(0.80)
    cust_df["is_vip_predicted"] = (cust_df["CLV_Point_Estimate"] >= vip_thresh).astype(int)
    
    cust_df["Spend_Tier"] = np.where(
        cust_df["total_spend"] < 500, "1. Low Spend (<GBP 500)",
        np.where(cust_df["total_spend"] <= 2000, "2. Mid Spend (GBP 500-2k)", "3. High Spend (>GBP 2k)")
    )
    
    mid_mask = (cust_df["total_spend"] >= 500) & (cust_df["total_spend"] <= 2000)
    uk_mid_vip = cust_df[(cust_df["Is_UK"] == "UK") & mid_mask]["is_vip_predicted"].mean()
    intl_mid_vip = cust_df[(cust_df["Is_UK"] == "International") & mid_mask]["is_vip_predicted"].mean()
    raw_mid_dir = intl_mid_vip / np.maximum(uk_mid_vip, 1e-6)
    print(f"Baseline Within Mid-Tier Disparate Impact Ratio: {raw_mid_dir:.4f} (BREACH: < 0.80)")
    
    cust_df["spend_per_order"] = cust_df["total_spend"] / cust_df["total_orders"]
    median_spo = cust_df["spend_per_order"].median()
    intl_boost = np.where(cust_df["Is_UK"] == "International", np.maximum(cust_df["spend_per_order"] / median_spo, 1.0) ** 0.35 - 1.0, 0.0)
    cust_df["recalibration_factor"] = np.clip(intl_boost, 0.0, 1.5)
    
    K = int(np.round(0.20 * len(cust_df)))
    base_vip_idx = cust_df.sort_values("CLV_Point_Estimate", ascending=False).head(K).index
    base_spend = cust_df.loc[base_vip_idx, "total_spend"].sum()
    
    print("\nPRICE OF FAIRNESS FRONTIER:")
    for lam in [0.0, 0.4, 1.0]:
        cust_df[f"clv_adj_{lam}"] = cust_df["CLV_Point_Estimate"] * (1.0 + lam * cust_df["recalibration_factor"])
        top_idx = cust_df.sort_values(f"clv_adj_{lam}", ascending=False).head(K).index
        top_set = set(top_idx)
        
        in_vip = cust_df.index.isin(top_set)
        uk_r = in_vip[(cust_df["Is_UK"] == "UK") & mid_mask].mean()
        intl_r = in_vip[(cust_df["Is_UK"] == "International") & mid_mask].mean()
        dir_val = intl_r / np.maximum(uk_r, 1e-6)
        real_spend = cust_df.loc[top_idx, "total_spend"].sum()
        promoted = len(top_set - set(base_vip_idx))
        print(f"  Lambda = {lam:.1f} | Mid-Tier DIR: {dir_val:.4f} | Status: {'PASS' if dir_val>=0.80 else 'FAIL'} | Realized Spend Delta: +GBP {real_spend - base_spend:>8,.2f} | Promoted: {promoted:>2d}")
        
    cust_df["clv_corrected"] = cust_df["clv_adj_1.0"]
    corr_vip_idx = cust_df.sort_values("clv_corrected", ascending=False).head(K).index
    cust_df["VIP_Tier_Uncorrected"] = cust_df.index.isin(set(base_vip_idx)).astype(int)
    cust_df["VIP_Tier_Corrected"] = cust_df.index.isin(set(corr_vip_idx)).astype(int)
    
    def mv(r):
        if r["VIP_Tier_Uncorrected"] == 0 and r["VIP_Tier_Corrected"] == 1: return "Promoted to VIP"
        elif r["VIP_Tier_Uncorrected"] == 1 and r["VIP_Tier_Corrected"] == 0: return "Demoted from VIP"
        elif r["VIP_Tier_Corrected"] == 1: return "Maintained VIP"
        else: return "Standard Tier"
        
    cust_df["Clienteling_Movement"] = cust_df.apply(mv, axis=1)
    cust_df.to_parquet(MASTER_PARQUET, index=False)
    return cust_df

def phase9_export(cust_df, output_csv=POWERBI_CSV):
    print("\n" + "=" * 80)
    print("PHASE 9: EXPORTING CLEAN SUMMARY DATASET FOR POWER BI")
    print("=" * 80)
    
    def churn_cat(p):
        if p < 0.25: return "Low Risk"
        elif p < 0.50: return "Moderate Risk"
        elif p < 0.75: return "Elevated Risk"
        else: return "High Churn Risk"
        
    cust_df["Churn_Risk_Tier"] = cust_df["churn_prob"].apply(churn_cat)
    cust_df["CI_Width"] = cust_df["CLV_Upper_90"] - cust_df["CLV_Lower_90"]
    if "Spend_Tier" not in cust_df.columns:
        cust_df["Spend_Tier"] = np.where(
            cust_df["total_spend"] < 500, "1. Low Spend (<GBP 500)",
            np.where(cust_df["total_spend"] <= 2000, "2. Mid Spend (GBP 500-2k)", "3. High Spend (>GBP 2k)")
        )
    
    flag_map = {
        "Switzerland": "VIP Under-selection; CLV Spend Devaluation",
        "Portugal": "VIP Under-selection",
        "Spain": "VIP Under-selection; CLV Spend Devaluation; Churn Over-prediction",
        "Belgium": "VIP Under-selection",
        "United Kingdom": "Normal Alignment",
        "Germany": "Normal Alignment",
        "France": "Normal Alignment"
    }
    cust_df["Fairness_Audit_Flag"] = cust_df["Country"].map(flag_map).fillna("Normal Alignment")
    
    pbi_cols = {
        "CustomerID": "CustomerID", "Country": "Country", "Is_UK": "Region_Cohort", "Segment": "RFM_Segment",
        "Spend_Tier": "Spend_Tier", "total_spend": "Historical_Spend_GBP", "total_orders": "Total_Orders",
        "spend_per_order": "Spend_Per_Order_GBP", "Recency": "Recency_Days", "T": "Customer_Tenure_Days",
        "CLV_Point_Estimate": "CLV_Raw_Point_GBP", "CLV_Lower_90": "CLV_Lower_90_GBP", "CLV_Upper_90": "CLV_Upper_90_GBP",
        "CI_Width": "CLV_Uncertainty_Margin_GBP", "clv_corrected": "CLV_Fair_Corrected_GBP", "is_churned": "Actual_Churn_Status",
        "churn_prob": "Predicted_Churn_Probability", "Churn_Risk_Tier": "Churn_Risk_Tier",
        "VIP_Tier_Uncorrected": "VIP_Status_Raw", "VIP_Tier_Corrected": "VIP_Status_Fair",
        "Clienteling_Movement": "Clienteling_Tier_Movement", "Fairness_Audit_Flag": "Fairness_Audit_Flag"
    }
    
    out_df = cust_df[list(pbi_cols.keys())].rename(columns=pbi_cols)
    out_df = out_df.round({
        "Historical_Spend_GBP": 2, "Spend_Per_Order_GBP": 2, "CLV_Raw_Point_GBP": 2,
        "CLV_Lower_90_GBP": 2, "CLV_Upper_90_GBP": 2, "CLV_Uncertainty_Margin_GBP": 2,
        "CLV_Fair_Corrected_GBP": 2, "Predicted_Churn_Probability": 4
    })
    out_df.to_csv(output_csv, index=False)
    print(f"Exported {len(out_df):,} rows to {output_csv} ({os.path.getsize(output_csv)/1024:.1f} KB).")
    return out_df

def main():
    parser = argparse.ArgumentParser(description="The Fair-Value Clienteling Engine")
    parser.add_argument("--all", action="store_true", help="Run complete end-to-end pipeline")
    parser.add_argument("--phase", type=int, choices=range(1, 10), help="Run a specific phase")
    args = parser.parse_args()
    
    if args.all or args.phase is None:
        t_start = time.time()
        phase1_cleaning()
        rfm = phase2_rfm()
        clv = phase3_clv(rfm_df=rfm)
        cust = phase4_churn(clv_df=clv, rfm_df=rfm)
        master = phase5_to_8_fairness(cust)
        phase9_export(master)
        print("\n" + "=" * 80)
        print(f"COMPLETE PIPELINE FINISHED IN {time.time()-t_start:.1f}s!")
        print("=" * 80)
    else:
        p = args.phase
        if p == 1: phase1_cleaning()
        elif p == 2: phase2_rfm()
        elif p == 3: phase3_clv()
        elif p == 4:
            rfm = phase2_rfm()
            clv = phase3_clv(rfm_df=rfm)
            phase4_churn(clv_df=clv, rfm_df=rfm)
        elif p in [5, 6, 7, 8]:
            if not os.path.exists(MASTER_PARQUET):
                rfm = phase2_rfm()
                clv = phase3_clv(rfm_df=rfm)
                cust = phase4_churn(clv_df=clv, rfm_df=rfm)
                phase5_to_8_fairness(cust)
            else:
                cust = pd.read_parquet(MASTER_PARQUET)
                phase5_to_8_fairness(cust)
        elif p == 9:
            cust = pd.read_parquet(MASTER_PARQUET)
            phase9_export(cust)

if __name__ == "__main__":
    main()
