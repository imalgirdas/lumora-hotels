"""
Script:   models.py
Purpose:  The data science part of the project. Each function trains / tests one
          model on 2021-2024 vs 2025 and saves its results to output/tables:
            1. cancellation_model()  - who will cancel? (gradient boosting vs logistic)
            2. demand_forecast()     - rooms sold per hotel per night in 2025
            3. pricing_analysis()    - price elasticity: observational vs A/B price test
            4. ab_tests()            - results of the 4 website experiments
            5. review_drivers()      - what moves the review score (OLS) + review phrases
            6. guest_segments()      - K-means guest segments and value per segment
Run:      python src/models.py   (after clean.py)
"""
import json

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss, mean_absolute_error,
                             roc_auc_score, roc_curve)
from sklearn.preprocessing import StandardScaler

from config import MODEL_DIR, RANDOM_STATE, TAB_DIR, TEST_YEAR, make_dirs
import features as F


def _encode(df, cats):
    """Category columns -> integer codes (HistGradientBoosting handles them natively)."""
    X = df.copy()
    for c in cats:
        X[c] = X[c].astype("category").cat.codes
    return X


def _save(df, name):
    df.to_csv(TAB_DIR / f"{name}.csv", index=False)
    return df


# --------------------------------------------------------------------------------------
# 1. Cancellation model
# --------------------------------------------------------------------------------------
def cancellation_model(clean, bf=None):
    print("1. Cancellation model")
    bf = F.booking_features(clean) if bf is None else bf
    cols = F.CANCEL_NUM + F.CANCEL_CAT
    X = _encode(bf[cols], F.CANCEL_CAT)
    y = bf.is_cancelled.values
    train = bf.year < TEST_YEAR
    test = ~train
    cat_mask = [c in F.CANCEL_CAT for c in cols]
    gb = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.06, max_leaf_nodes=48,
                                        categorical_features=cat_mask, random_state=RANDOM_STATE)
    gb.fit(X[train], y[train])
    p = gb.predict_proba(X[test])[:, 1]
    # baseline: logistic regression on a few simple features
    base_cols = ["log_lead", "special_requests", "prev_cancel_rate", "is_member", "log_price_index"]
    Xb = pd.get_dummies(bf[base_cols + ["rate_plan_id", "channel_id"]], columns=["rate_plan_id", "channel_id"], dtype=float)
    lr = LogisticRegression(max_iter=2000).fit(Xb[train], y[train])
    pb = lr.predict_proba(Xb[test])[:, 1]
    metrics = {
        "train_rows": int(train.sum()), "test_rows": int(test.sum()),
        "test_cancel_rate": float(y[test].mean()),
        "auc_gradient_boosting": roc_auc_score(y[test], p),
        "auc_logistic_baseline": roc_auc_score(y[test], pb),
        "pr_auc_gradient_boosting": average_precision_score(y[test], p),
        "brier_gradient_boosting": brier_score_loss(y[test], p),
    }
    # how many cancellations are in the riskiest 20% of bookings?
    order = np.argsort(-p)
    top = order[: int(0.2 * len(p))]
    metrics["share_of_cancels_in_top20pct_risk"] = float(y[test][top].sum() / y[test].sum())
    print("   " + ", ".join(f"{k}={v:.3f}" for k, v in metrics.items() if isinstance(v, float)))

    sample = X[test].sample(15000, random_state=1)
    pi = permutation_importance(gb, sample, pd.Series(y, index=X.index).loc[sample.index],
                                scoring="roc_auc", n_repeats=3, random_state=RANDOM_STATE)
    imp = pd.DataFrame({"feature": cols, "importance": pi.importances_mean}).sort_values("importance", ascending=False)
    _save(imp, "cancel_feature_importance")
    fpr, tpr, _ = roc_curve(y[test], p)
    fpr_b, tpr_b, _ = roc_curve(y[test], pb)
    pick = np.linspace(0, len(fpr) - 1, 200).astype(int)
    pick_b = np.linspace(0, len(fpr_b) - 1, 200).astype(int)
    _save(pd.DataFrame({"model": ["Gradient boosting"] * 200 + ["Logistic baseline"] * 200,
                        "fpr": np.r_[fpr[pick], fpr_b[pick_b]], "tpr": np.r_[tpr[pick], tpr_b[pick_b]]}), "cancel_roc")
    preds = bf.loc[test, ["booking_id", "hotel_id", "channel_id", "market_segment", "rate_plan_id",
                          "checkin_date", "lead_time_days", "is_cancelled"]].copy()
    preds["p_cancel"] = p.round(4)
    _save(preds, "cancel_predictions_2025")
    calib = preds.assign(bin=pd.qcut(preds.p_cancel, 10, labels=False, duplicates="drop")).groupby("bin").agg(
        predicted=("p_cancel", "mean"), actual=("is_cancelled", "mean"), bookings=("p_cancel", "size")).reset_index()
    _save(calib, "cancel_calibration")
    (MODEL_DIR / "cancel_metrics.json").write_text(json.dumps(metrics, indent=2))
    return {"metrics": metrics, "importance": imp, "predictions": preds, "calibration": calib}


# --------------------------------------------------------------------------------------
# 2. Demand forecast
# --------------------------------------------------------------------------------------
def demand_forecast(clean, hd=None):
    print("2. Demand forecast (rooms sold per hotel-night)")
    hd = F.hotel_daily(clean) if hd is None else hd
    cols = F.DEMAND_NUM + F.DEMAND_CAT
    X = _encode(hd[cols], F.DEMAND_CAT)
    y = hd.occupancy.values
    train = (hd.year < TEST_YEAR) & (hd.year >= 2022)      # 2021 is a COVID year, kept as lag only
    test = hd.year == TEST_YEAR
    m = HistGradientBoostingRegressor(max_iter=500, learning_rate=0.05, max_leaf_nodes=48,
                                      categorical_features=[c in F.DEMAND_CAT for c in cols], random_state=RANDOM_STATE)
    m.fit(X[train], y[train])
    hd["forecast_occ"] = np.clip(m.predict(X), 0, 1)
    hd["forecast_rooms"] = (hd.forecast_occ * hd.rooms).round(1)
    hd["naive_rooms"] = (hd.occ_lag364 * hd.rooms).round(1)    # same weekday last year
    t = hd[test]
    wape = lambda a, f: float(np.abs(a - f).sum() / a.sum())
    metrics = {"wape_model": wape(t.rooms_sold, t.forecast_rooms),
               "wape_naive_last_year": wape(t.rooms_sold, t.naive_rooms.fillna(t.rooms_sold.mean())),
               "mae_rooms_model": mean_absolute_error(t.rooms_sold, t.forecast_rooms)}
    # monthly accuracy is what revenue managers use
    mo = t.groupby(["hotel_id", "month"])[["rooms_sold", "forecast_rooms"]].sum()
    metrics["wape_monthly_model"] = wape(mo.rooms_sold, mo.forecast_rooms)
    print("   " + ", ".join(f"{k}={v:.3f}" for k, v in metrics.items()))
    by_hotel = t.groupby("hotel_id").apply(lambda d: pd.Series({
        "actual_rooms": d.rooms_sold.sum(), "forecast_rooms": d.forecast_rooms.sum(),
        "wape_model": wape(d.rooms_sold, d.forecast_rooms),
        "wape_naive": wape(d.rooms_sold, d.naive_rooms.fillna(d.rooms_sold.mean()))}), include_groups=False).reset_index()
    _save(by_hotel, "forecast_accuracy_by_hotel")
    _save(hd[["hotel_id", "date", "rooms", "rooms_sold", "occupancy", "forecast_rooms", "naive_rooms", "events"]], "hotel_daily_forecast")
    (MODEL_DIR / "forecast_metrics.json").write_text(json.dumps(metrics, indent=2))
    return {"metrics": metrics, "daily": hd, "by_hotel": by_hotel}


# --------------------------------------------------------------------------------------
# 3. Pricing: observational vs experimental price sensitivity
# --------------------------------------------------------------------------------------
def pricing_analysis(clean, qf=None):
    print("3. Pricing analysis")
    qf = F.quote_features(clean) if qf is None else qf
    q = qf[(qf.availability == "available") & qf.log_price_index.notna()].copy()
    controls = ["lead_time_days", "nights", "logged_in", "weekend_stay", "quote_rank"]
    Xo = pd.get_dummies(q[["log_price_index"] + controls + ["device", "traffic_source"]],
                        columns=["device", "traffic_source"], drop_first=True, dtype=float)
    lr = LogisticRegression(max_iter=3000).fit(Xo, q.converted)
    coef_obs = float(lr.coef_[0][0])
    # experiment EXP02: price randomly x0.92 / x1.00 / x1.08
    e = q[q.experiment_id == "EXP02"].copy()
    e["log_mult"] = np.log(e.variant.map({"control": 1.0, "price_minus_8": 0.92, "price_plus_8": 1.08}))
    Xe = pd.get_dummies(e[["log_mult"] + controls + ["device", "traffic_source"]],
                        columns=["device", "traffic_source"], drop_first=True, dtype=float)
    lr_e = LogisticRegression(max_iter=3000).fit(Xe, e.converted)
    coef_exp = float(lr_e.coef_[0][0])
    e["revenue"] = e.converted * e.price_per_night_eur * e.nights
    by_var = e.groupby("variant").agg(quotes=("converted", "size"), conversion=("converted", "mean"),
                                      avg_price=("price_per_night_eur", "mean"),
                                      revenue_per_quote=("revenue", "mean")).reset_index()
    c = by_var.set_index("variant")
    arc = (np.log(c.loc["price_plus_8", "conversion"]) - np.log(c.loc["price_minus_8", "conversion"])) / (np.log(1.08) - np.log(0.92))
    # who is most price sensitive? interact price with stay type in the experiment
    seg = []
    for nm, mask in [("Weekday stay", e.weekend_stay == 0), ("Weekend stay", e.weekend_stay == 1),
                     ("Lead < 14 days", e.lead_time_days < 14), ("Lead 14+ days", e.lead_time_days >= 14),
                     ("Logged in", e.logged_in == 1), ("Not logged in", e.logged_in == 0)]:
        s = e[mask].groupby("variant").converted.mean()
        seg.append({"group": nm, "elasticity": (np.log(s["price_plus_8"]) - np.log(s["price_minus_8"])) / (np.log(1.08) - np.log(0.92)),
                    "quotes": int(mask.sum())})
    seg = pd.DataFrame(seg)
    q["price_bin"] = pd.cut(q.price_index, [0, .8, .9, .95, 1.0, 1.05, 1.1, 1.2, 1.35, 10],
                            labels=["<0.80", "0.80-0.90", "0.90-0.95", "0.95-1.00", "1.00-1.05", "1.05-1.10",
                                    "1.10-1.20", "1.20-1.35", ">1.35"])
    curve = q.groupby("price_bin", observed=True).agg(quotes=("converted", "size"), conversion=("converted", "mean")).reset_index()
    metrics = {"logit_coef_price_observational": coef_obs, "logit_coef_price_experiment": coef_exp,
               "arc_elasticity_conversion_exp02": float(arc)}
    print("   " + ", ".join(f"{k}={v:.3f}" for k, v in metrics.items()))
    _save(by_var, "price_test_by_variant")
    _save(seg, "price_elasticity_by_group")
    _save(curve, "conversion_by_price_index")
    (MODEL_DIR / "pricing_metrics.json").write_text(json.dumps(metrics, indent=2))
    return {"metrics": metrics, "by_variant": by_var, "by_group": seg, "curve": curve, "quotes": q}


# --------------------------------------------------------------------------------------
# 4. A/B tests
# --------------------------------------------------------------------------------------
def two_prop_test(n_c, x_c, n_t, x_t):
    p_c, p_t = x_c / n_c, x_t / n_t
    p = (x_c + x_t) / (n_c + n_t)
    se0 = np.sqrt(p * (1 - p) * (1 / n_c + 1 / n_t))
    z = (p_t - p_c) / se0
    se = np.sqrt(p_c * (1 - p_c) / n_c + p_t * (1 - p_t) / n_t)
    return p_c, p_t, p_t - p_c, (p_t - p_c - 1.96 * se, p_t - p_c + 1.96 * se), 2 * (1 - stats.norm.cdf(abs(z)))


def ab_tests(clean, qf=None):
    print("4. A/B tests")
    q = clean["rate_quotes"]
    q = q[(q.availability == "available") & (q.experiment_id != "")]
    rows = []
    for (eid, var), d in q.groupby(["experiment_id", "variant"]):
        if var == "control":
            continue
        c = q[(q.experiment_id == eid) & (q.variant == "control")]
        p_c, p_t, diff, ci, pval = two_prop_test(len(c), c.converted.sum(), len(d), d.converted.sum())
        rows.append({"experiment_id": eid, "variant": var, "control_quotes": len(c), "variant_quotes": len(d),
                     "control_conv": p_c, "variant_conv": p_t, "diff_pp": diff * 100,
                     "ci_low_pp": ci[0] * 100, "ci_high_pp": ci[1] * 100, "relative_lift": diff / p_c,
                     "p_value": pval, "significant": pval < 0.05})
    res = pd.DataFrame(rows).merge(clean["experiments"][["experiment_id", "experiment_name"]], on="experiment_id")
    print(res[["experiment_id", "variant", "diff_pp", "p_value"]].round(4).to_string(index=False))
    return _save(res, "ab_test_results")


# --------------------------------------------------------------------------------------
# 5. Review drivers
# --------------------------------------------------------------------------------------
def review_drivers(clean, bf=None):
    print("5. Review score drivers")
    bf = F.booking_features(clean) if bf is None else bf
    r = clean["reviews"].merge(bf[["booking_id", "log_price_index", "room_type_id", "rate_plan_id", "market_segment",
                                   "nights", "special_requests", "stars", "event_on_arrival", "is_member", "hotel_id",
                                   "checkin_date"]], on=["booking_id", "hotel_id"])
    st = clean["staffing_monthly"].set_index(["hotel_id", "month"]).staff_turnover_pct
    r["staff_turnover_pct"] = st.reindex(pd.MultiIndex.from_arrays(
        [r.hotel_id, r.checkin_date.dt.to_period("M").astype(str)])).values
    rt = clean["room_types"].set_index("room_type_id").room_type
    r["room_type"] = r.room_type_id.map(rt)
    X = pd.DataFrame({
        "Staff turnover (+1 pp)": r.staff_turnover_pct,
        "Price vs competitors (+10%)": r.log_price_index / np.log(1.1),
        "Stars (+1)": r.stars,
        "Breakfast included": (r.rate_plan_id.isin(["RP3", "RP6"])).astype(int),
        "Member rate": (r.rate_plan_id == "RP4").astype(int),
        "Superior room": (r.room_type == "Superior").astype(int),
        "Deluxe room": (r.room_type == "Deluxe").astype(int),
        "Suite": (r.room_type == "Suite").astype(int),
        "Business trip": (r.market_segment == "Business").astype(int),
        "Family trip": (r.market_segment == "Family").astype(int),
        "Group trip": (r.market_segment == "Group").astype(int),
        "Event in city": r.event_on_arrival,
        "Long stay (7+ nights)": (r.nights >= 7).astype(int),
    }).fillna(0)
    ols = LinearRegression().fit(X, r.overall_score)
    # bootstrap confidence intervals
    rng = np.random.default_rng(RANDOM_STATE)
    boots = []
    for _ in range(30):
        i = rng.integers(0, len(X), len(X))
        boots.append(LinearRegression().fit(X.iloc[i], r.overall_score.iloc[i]).coef_)
    boots = np.array(boots)
    coefs = pd.DataFrame({"driver": X.columns, "effect": ols.coef_,
                          "ci_low": np.percentile(boots, 2.5, axis=0), "ci_high": np.percentile(boots, 97.5, axis=0)})
    coefs = coefs.sort_values("effect")
    print(f"   R2 = {ols.score(X, r.overall_score):.3f}")
    # phrases in the review text
    ph = r[["review_id", "hotel_id", "year", "overall_score", "review_text"]].copy()
    ph["phrase"] = ph.review_text.str.rstrip(".").str.split(". ", regex=False)
    ph = ph.explode("phrase")
    stats_ = ph.groupby("phrase").agg(mentions=("review_id", "size"), avg_score=("overall_score", "mean")).reset_index()
    stats_["tone"] = np.where(stats_.avg_score >= r.overall_score.mean(), "Positive", "Negative")
    _save(coefs, "review_drivers")
    _save(stats_.sort_values("mentions", ascending=False), "review_phrases")
    return {"coefs": coefs, "phrases": stats_, "phrase_rows": ph, "r2": ols.score(X, r.overall_score), "reviews": r}


# --------------------------------------------------------------------------------------
# 6. Guest segments
# --------------------------------------------------------------------------------------
def guest_segments(clean, bf=None, k=5):
    print("6. Guest segments (K-means)")
    bf = F.booking_features(clean) if bf is None else bf
    anc = clean["stay_charges"].groupby("booking_id").amount_eur.sum()
    b = bf.assign(ancillary_eur=bf.booking_id.map(anc).fillna(0))
    end = pd.Timestamp("2026-01-01")
    g = b.groupby("guest_id").agg(
        bookings=("booking_id", "size"), stays=("status", lambda s: (s == "Checked-out").sum()),
        cancel_rate=("is_cancelled", "mean"), room_revenue=("room_revenue_eur", "sum"),
        ancillary=("ancillary_eur", "sum"), avg_lead=("lead_time_days", "mean"), avg_nights=("nights", "mean"),
        avg_party=("party_size", "mean"), weekday_share=("weekend_stay", lambda s: 1 - s.mean()),
        direct_share=("is_direct", "mean"), last=("checkin_date", "max"), first=("booking_datetime", "min"))
    g["recency_days"] = (end - g["last"]).dt.days
    g["total_value"] = g.room_revenue + g.ancillary
    g["years_active"] = ((g["last"] - g["first"]).dt.days / 365).clip(lower=1 / 12)
    feats = ["bookings", "cancel_rate", "total_value", "avg_lead", "avg_nights", "avg_party", "weekday_share",
             "direct_share", "recency_days"]
    Z = g[feats].copy()
    for c in ["bookings", "total_value", "avg_lead", "avg_nights"]:
        Z[c] = np.log1p(Z[c])
    Z = StandardScaler().fit_transform(Z)
    km = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE).fit(Z)
    g["cluster"] = km.labels_
    prof = g.groupby("cluster").agg(guests=("bookings", "size"), **{f: (f, "mean") for f in feats},
                                    value_per_guest=("total_value", "mean"),
                                    value_total=("total_value", "sum")).reset_index()
    # readable names: give each name to the cluster that fits it best, in priority order
    names, left = {}, prof.set_index("cluster")
    for name, col in [("Loyal regulars", "bookings"), ("Cancel-prone planners", "cancel_rate"),
                      ("Families & groups", "avg_party"), ("Direct bookers", "direct_share")]:
        best = left[col].idxmax()
        names[best] = name
        left = left.drop(best)
    for i, cl in enumerate(left.index):
        names[cl] = "OTA one-timers" if i == 0 else f"Other guests {i}"
    g["segment"] = g.cluster.map(names)
    prof["segment"] = prof.cluster.map(names)
    prof["share_of_value"] = prof.value_total / prof.value_total.sum()
    print(prof[["segment", "guests", "bookings", "value_per_guest", "share_of_value"]].round(2).to_string(index=False))
    _save(prof, "guest_segment_profiles")
    _save(g.reset_index()[["guest_id", "segment"] + feats + ["total_value"]], "guest_segments")
    return {"guests": g.reset_index(), "profiles": prof}


def run_all_models(clean):
    make_dirs()
    bf = F.booking_features(clean)
    out = {"cancel": cancellation_model(clean, bf)}
    out["demand"] = demand_forecast(clean)
    qf = F.quote_features(clean)
    out["pricing"] = pricing_analysis(clean, qf)
    out["ab"] = ab_tests(clean)
    out["reviews"] = review_drivers(clean, bf)
    out["segments"] = guest_segments(clean, bf)
    out["bf"] = bf
    return out


if __name__ == "__main__":
    from load import load_clean
    run_all_models(load_clean())
