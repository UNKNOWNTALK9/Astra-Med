"""AI-assisted anomaly detection (Isolation Forest) with per-astronaut baselines and
explainable reasons. This is a statistical screening aid ONLY. It does not diagnose medical
conditions and does not replace professional medical judgement."""
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import IsolationForest

from config import MODELS_DIR, PARAM_KEYS, REFERENCE_RANGES

MODEL_PATH = MODELS_DIR / "isolation_forest.joblib"
MIN_STD = {"heart_rate": 1.5, "spo2": 0.3, "systolic": 2.0, "diastolic": 1.5, "temperature": 0.08,
           "resp_rate": 0.6, "activity": 3.0, "sleep": 0.4, "hydration": 1.5, "stress": 3.0}
DISCLAIMER = ("Statistical screening aid on SIMULATED data. It does not diagnose medical "
              "conditions or replace professional medical judgement.")
Z_REASON = 2.5
Z_EXTREME = 4.0   # any single parameter this far from personal baseline is flagged regardless of the forest


class AnomalyDetector:
    def __init__(self):
        self.model = None
        self.baseline = {}   # code -> {"mean": {...}, "std": {...}}
        self.global_ = None
        self.calib = None
        self.meta = {}

    @property
    def ready(self):
        return self.model is not None

    # ---- training -----------------------------------------------------------
    def fit(self, df, contamination=0.02, min_rows=50):
        if len(df) < 200:
            raise ValueError("Not enough historical readings to train (need at least 200).")
        df = df.sort_values("timestamp")
        g = df.groupby("code")[PARAM_KEYS]
        counts, means, stds = g.size(), g.mean(), g.std(ddof=0)
        gmean, gstd = df[PARAM_KEYS].mean(), df[PARAM_KEYS].std(ddof=0)
        floor = pd.Series(MIN_STD)
        self.global_ = {"mean": gmean.to_dict(), "std": np.maximum(gstd, floor).to_dict()}
        self.baseline = {c: {"mean": means.loc[c].to_dict(),
                             "std": np.maximum(stds.loc[c].fillna(0), floor).to_dict()}
                         for c in means.index if counts[c] >= min_rows}
        Z = self._z(df)
        cut = int(len(Z) * 0.8)
        probe = IsolationForest(n_estimators=200, contamination=contamination, random_state=42).fit(Z[:cut])
        test_rate = float(((probe.predict(Z[cut:]) == -1) | (np.abs(Z[cut:]).max(axis=1) >= Z_EXTREME)).mean())
        self.model = IsolationForest(n_estimators=200, contamination=contamination, random_state=42).fit(Z)
        self.calib = np.sort(-self.model.score_samples(Z))
        self.meta = {"trained_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "n_rows": int(len(df)),
                     "n_train_eval": int(cut), "n_test_eval": int(len(Z) - cut),
                     "contamination": contamination, "test_flag_rate": test_rate,
                     "train_flag_rate": float(((self.model.predict(Z) == -1) | (np.abs(Z).max(axis=1) >= Z_EXTREME)).mean()),
                     "n_astronauts": int(len(means))}
        return self.meta

    # ---- scoring ----------------------------------------------------------------
    def _base(self, code):
        return self.baseline.get(code, self.global_)

    def _z(self, df):
        Z = np.zeros((len(df), len(PARAM_KEYS)))
        codes = df["code"].to_numpy()
        vals = df[PARAM_KEYS].to_numpy(dtype=float)
        for c in np.unique(codes):
            idx = codes == c
            b = self._base(c)
            mean = np.array([b["mean"][p] for p in PARAM_KEYS])
            std = np.array([b["std"][p] for p in PARAM_KEYS])
            Z[idx] = (vals[idx] - mean) / std
        return Z

    def score_df(self, df):
        """Return a copy with anomaly_score (0-100 percentile of training distribution),
        is_anomaly, and z_<param> columns."""
        if not self.ready:
            raise RuntimeError("Model not trained.")
        out = df.copy()
        Z = self._z(df)
        raw = -self.model.score_samples(Z)
        pct = np.searchsorted(self.calib, raw) / len(self.calib) * 100
        # Isolation Forest scores saturate for points far outside the training range, so a
        # hybrid rule also flags extreme single-parameter deviations (>= Z_EXTREME sigma).
        zmax = np.abs(Z).max(axis=1)
        extreme = zmax >= Z_EXTREME
        out["anomaly_score"] = np.where(extreme, np.maximum(pct, np.minimum(100, 85 + 3 * (zmax - Z_EXTREME))), pct)
        out["is_anomaly"] = (self.model.predict(Z) == -1) | extreme
        for i, p in enumerate(PARAM_KEYS):
            out[f"z_{p}"] = Z[:, i]
        return out

    def score_batch(self, batch):
        """Live scoring for {code: reading}; returns {code: (score, is_anomaly, reasons)}."""
        rows = [{"code": c, **{p: r[p] for p in PARAM_KEYS}} for c, r in batch.items()]
        if not rows or not self.ready:
            return {}
        scored = self.score_df(pd.DataFrame(rows))
        return {row["code"]: (float(row["anomaly_score"]), bool(row["is_anomaly"]),
                              self.reasons(row, row["code"])) for _, row in scored.iterrows()}

    def reasons(self, row, code=None, top=3):
        """Explain an anomaly: the parameters furthest from this astronaut's own baseline."""
        b = self._base(code if code is not None else row.get("code"))
        items = []
        for p in PARAM_KEYS:
            z = float(row[f"z_{p}"])
            if abs(z) >= Z_REASON:
                items.append((abs(z), p, z))
        items.sort(reverse=True)
        out = []
        for _, p, z in items[:top]:
            meta = REFERENCE_RANGES[p]
            out.append(f"{meta['label']} {row[p]:.1f} {meta['unit']} is {abs(z):.1f}σ "
                       f"{'above' if z > 0 else 'below'} personal baseline ({b['mean'][p]:.1f})")
        return out or ["No single parameter dominates; the combination of values is unusual"]

    # ---- trends --------------------------------------------------------------------
    @staticmethod
    def trends(df, min_days=5):
        """Gradual-change detection: linear regression on daily means (p<0.05, >=3% total change)
        plus a last-24h shift versus the prior baseline in standard deviations."""
        out = []
        if df.empty:
            return out
        daily = df.set_index("timestamp")[PARAM_KEYS].resample("D").mean().dropna(how="all")
        for p in PARAM_KEYS:
            s = daily[p].dropna()
            if len(s) >= min_days and s.std() > 0:
                x = np.arange(len(s))
                res = stats.linregress(x, s.values)
                total_pct = res.slope * (len(s) - 1) / abs(s.mean()) * 100 if s.mean() else 0
                if res.pvalue < 0.05 and abs(total_pct) >= 3:
                    out.append({"param": p, "kind": "trend", "slope_per_day": res.slope,
                                "total_pct": total_pct, "p": res.pvalue,
                                "text": f"{REFERENCE_RANGES[p]['label']} shows a gradual "
                                        f"{'increase' if res.slope > 0 else 'decrease'} of about {abs(total_pct):.1f}% "
                                        f"over {len(s)} days (p={res.pvalue:.3f})"})
        last = df["timestamp"].max()
        recent, prior = df[df["timestamp"] > last - pd.Timedelta(hours=24)], df[df["timestamp"] <= last - pd.Timedelta(hours=24)]
        if len(recent) >= 5 and len(prior) >= 50:
            for p in PARAM_KEYS:
                sd = max(prior[p].std(ddof=0), MIN_STD[p])
                z = (recent[p].mean() - prior[p].mean()) / sd
                if abs(z) >= 2:
                    out.append({"param": p, "kind": "shift", "z": z,
                                "text": f"Last-24h mean {REFERENCE_RANGES[p]['label']} is {abs(z):.1f}σ "
                                        f"{'above' if z > 0 else 'below'} the prior baseline"})
        return out

    def summarize(self, name, scored, trend_items):
        n = len(scored)
        flagged = scored[scored["is_anomaly"]]
        lines = [f"Analysis of {n} readings for {name} "
                 f"({scored['timestamp'].min():%Y-%m-%d} to {scored['timestamp'].max():%Y-%m-%d})."]
        if flagged.empty:
            lines.append("No readings were flagged as unusual relative to this astronaut's baseline.")
        else:
            peak = flagged.loc[flagged["anomaly_score"].idxmax()]
            counts = {p: int((flagged[f"z_{p}"].abs() >= Z_REASON).sum()) for p in PARAM_KEYS}
            top = [f"{REFERENCE_RANGES[p]['label']} ({c})" for p, c in
                   sorted(counts.items(), key=lambda kv: -kv[1])[:3] if c]
            lines.append(f"{len(flagged)} readings ({len(flagged) / n * 100:.1f}%) were flagged as unusual. "
                         f"Highest score {peak['anomaly_score']:.0f}/100 at {peak['timestamp']:%Y-%m-%d %H:%M}.")
            if top:
                lines.append("Most frequent contributing parameters: " + ", ".join(top) + ".")
        if trend_items:
            lines.append("Potentially concerning patterns:")
            lines += [f"  - {t['text']}" for t in trend_items]
        else:
            lines.append("No significant gradual trends or recent baseline shifts were detected.")
        lines.append(DISCLAIMER)
        return "\n".join(lines)

    # ---- persistence -------------------------------------------------------------------
    def save(self, path=MODEL_PATH):
        joblib.dump({"model": self.model, "baseline": self.baseline, "global": self.global_,
                     "calib": self.calib, "meta": self.meta}, path)

    def load(self, path=MODEL_PATH):
        try:
            d = joblib.load(path)
            self.model, self.baseline, self.global_ = d["model"], d["baseline"], d["global"]
            self.calib, self.meta = d["calib"], d["meta"]
            return True
        except Exception:
            return False
