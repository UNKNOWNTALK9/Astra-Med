"""Pandas/NumPy analytics over health readings."""
import numpy as np
import pandas as pd

from config import PARAM_KEYS, REFERENCE_RANGES
from utils.helpers import param_status


def _month_alias():
    try:
        pd.tseries.frequencies.to_offset("ME")
        return "ME"
    except Exception:
        return "M"


GRANULARITY = {"Raw": None, "Hourly": "h", "Daily": "D", "Weekly": "W", "Monthly": _month_alias()}


def resample_param(df, param, freq):
    """Return a DataFrame (time x astronaut code) of the parameter, optionally resampled (mean)."""
    wide = df.pivot_table(index="timestamp", columns="code", values=param, aggfunc="mean")
    if freq:
        wide = wide.resample(freq).mean()
    return wide


def summary_stats(df):
    """Per-parameter min/mean/max/std and % of readings outside the normal range."""
    rows = []
    for p in PARAM_KEYS:
        if p not in df or df[p].dropna().empty:
            continue
        s = df[p].dropna()
        out = sum(param_status(p, v) != "normal" for v in s) / len(s) * 100
        meta = REFERENCE_RANGES[p]
        rows.append({"param": p, "label": meta["label"], "unit": meta["unit"], "min": s.min(),
                     "mean": s.mean(), "max": s.max(), "std": s.std(ddof=0), "out_pct": out,
                     "range": f'{meta["range"][1]}-{meta["range"][2]}'})
    return pd.DataFrame(rows)


def correlation(df, params=None):
    cols = [p for p in (params or PARAM_KEYS) if p in df and df[p].std() > 0]
    return df[cols].corr()


def period_comparison(df, param, freq, last=14):
    """Mean of `param` per period and astronaut (last N periods)."""
    return resample_param(df, param, freq).tail(last)


def astronaut_comparison(df, params):
    return df.groupby("code")[list(params)].mean()


def status_breakdown(df):
    vc = df["status"].value_counts(normalize=True) * 100
    return {k: float(vc.get(k, 0.0)) for k in ("normal", "warning", "critical")}


def daily_sleep(df):
    return resample_param(df, "sleep", "D")
