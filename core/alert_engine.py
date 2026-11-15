"""Threshold alert engine with hysteresis: alerts fire on escalation, on re-entry after a
cooldown, and on recovery. Alerts persist to SQLite. AI alerts are 'info' severity."""
from datetime import datetime

from config import PARAM_KEYS, REFERENCE_RANGES
from utils.helpers import SEVERITY_ORDER, param_status


def describe(param, value, severity):
    meta = REFERENCE_RANGES[param]
    lo_w, lo_n, hi_n, hi_w = meta["range"]
    u, lab = meta["unit"], meta["label"]
    if value > hi_w:
        txt = f"above critical limit ({hi_w})"
    elif value > hi_n:
        txt = f"above normal range (max {hi_n})"
    elif value < lo_w:
        txt = f"below critical limit ({lo_w})"
    else:
        txt = f"below normal range (min {lo_n})"
    return f"{lab} {value:.1f} {u} {txt}"


class AlertEngine:
    def __init__(self, db, roster=(), cooldown_sec=120):
        self.db = db
        self.cooldown = cooldown_sec
        self.roster = {}
        self.state = {}      # (code, param) -> last severity
        self.last_emit = {}  # (code, param, severity) -> datetime
        self.set_roster(roster)

    def set_roster(self, astronauts):
        self.roster = {a["id"]: a for a in astronauts}

    def _cooled(self, key, now):
        t = self.last_emit.get(key)
        return t is None or (now - t).total_seconds() >= self.cooldown

    def _emit(self, a, param, severity, value, message, now, source="threshold"):
        aid = self.db.add_alert(a["db_id"], severity, param, value, message, source, now)
        self.last_emit[(a["id"], param, severity)] = now
        return {"id": aid, "astronaut_id": a["db_id"], "code": a["id"], "name": a["name"],
                "timestamp": now, "severity": severity, "parameter": param,
                "value": value, "message": message, "source": source}

    def process(self, batch, now=None):
        """Evaluate one telemetry batch; persist and return the new alerts."""
        out = []
        for code, r in batch.items():
            a = self.roster.get(code)
            if not a:
                continue
            ts = now or r.get("timestamp") or datetime.now()
            for p in PARAM_KEYS:
                if p not in r:
                    continue
                sev = param_status(p, r[p])
                key = (code, p)
                prev = self.state.get(key, "normal")
                if sev != prev:
                    lab = REFERENCE_RANGES[p]["label"]
                    if sev == "normal":
                        if prev in ("warning", "critical"):
                            out.append(self._emit(a, p, "normal", r[p],
                                                  f"{lab} returned to normal range ({r[p]:.1f} {REFERENCE_RANGES[p]['unit']})", ts))
                    elif SEVERITY_ORDER[sev] > SEVERITY_ORDER[prev] and (
                            prev != "normal" or self._cooled((code, p, sev), ts)):
                        out.append(self._emit(a, p, sev, r[p], describe(p, r[p], sev), ts))
                    self.state[key] = sev
        return out

    def emit_ai(self, code, score, reasons, now=None):
        a = self.roster.get(code)
        if not a:
            return None
        now = now or datetime.now()
        if not self._cooled((code, "ai", "info"), now):
            return None
        msg = f"AI: unusual vital-sign pattern (score {score:.0f}/100). " + "; ".join(reasons[:2])
        return self._emit(a, "ai", "info", float(score), msg, now, source="ai")
