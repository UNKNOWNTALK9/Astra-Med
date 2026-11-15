"""Simulated telemetry: mean-reverting random walks with diurnal rhythm, activity coupling,
nightly sleep totals and occasional excursions. ALL OUTPUT IS SIMULATED and must never be
presented as real medical data. In-flight mode applies NASA-documented behavior (reduced
HR/diastolic variability and diurnal swing; see core/nasa_reference.py)."""
import math
import random
import threading
from datetime import datetime

import numpy as np

from core.nasa_reference import (GROUND_DIURNAL_AMPLITUDE, IN_FLIGHT_DIURNAL_FACTOR,
                                 IN_FLIGHT_VARIABILITY_FACTOR)

# param: (baseline, noise, reversion, hard_min, hard_max)
_MODEL = {
    "heart_rate": (72, 1.6, 0.08, 35, 190),
    "spo2": (97.5, 0.25, 0.12, 80, 100),
    "systolic": (118, 1.5, 0.08, 70, 200),
    "diastolic": (76, 1.0, 0.08, 40, 120),
    "temperature": (36.7, 0.04, 0.10, 34, 41),
    "resp_rate": (15, 0.35, 0.10, 6, 40),
    "activity": (45, 2.0, 0.10, 0, 100),
    "sleep": (7.2, 0.0, 0.0, 0, 14),
    "hydration": (75, 0.6, 0.05, 20, 100),
    "stress": (28, 2.0, 0.08, 0, 100),
}
_SPREAD = {"heart_rate": 8, "spo2": 1.0, "systolic": 5, "diastolic": 4, "temperature": 0.25,
           "resp_rate": 1, "activity": 8, "sleep": 0.3, "hydration": 6, "stress": 6}
_COUPLING = {"heart_rate": 0.32, "resp_rate": 0.05, "systolic": 0.08, "temperature": 0.004}
_EXC_DIR = {"heart_rate": 1, "spo2": -1, "systolic": 1, "diastolic": 1,
            "temperature": 1, "resp_rate": 1, "stress": 1, "hydration": -1}
_EXC_SIZE = {"heart_rate": 70, "spo2": 9, "systolic": 55, "diastolic": 25, "temperature": 1.9,
             "resp_rate": 10, "stress": 55, "hydration": 35}
_ORDER = ["activity"] + [p for p in _MODEL if p != "activity"]


class TelemetrySimulator:
    def __init__(self, astronauts=(), seed=None, anomaly_chance=0.004, in_flight=True,
                 excursion_ticks=(15, 40)):
        """astronauts: iterable of dicts with an 'id' key (the astronaut code)."""
        self.in_flight = in_flight
        self.rng = random.Random(seed)
        self.anomaly_chance = anomaly_chance
        self.excursion_ticks = excursion_ticks
        self.state, self.excursion = {}, {}
        self._lock = threading.Lock()
        self.sync(astronauts)

    def sync(self, astronauts):
        ids = {a["id"] for a in astronauts}
        with self._lock:
            for aid in ids:
                if aid not in self.state:
                    base = {p: b + self.rng.uniform(-_SPREAD[p], _SPREAD[p])
                            for p, (b, *_r) in _MODEL.items()}
                    self.state[aid] = {"baseline": base, "values": dict(base), "day": None}
            for aid in list(self.state):
                if aid not in ids:
                    del self.state[aid]
                    self.excursion.pop(aid, None)

    def _maybe_start_excursion(self, aid):
        if aid not in self.excursion and self.rng.random() < self.anomaly_chance:
            self.excursion[aid] = [self.rng.choice(list(_EXC_DIR)),
                                   self.rng.randint(*self.excursion_ticks),
                                   self.rng.uniform(0.6, 1.0)]

    def step(self, now=None):
        """Advance one tick (optionally at an explicit timestamp); return {code: reading}."""
        now = now or datetime.now()
        hour = now.hour + now.minute / 60
        batch = {}
        with self._lock:
            for aid, st in self.state.items():
                self._maybe_start_excursion(aid)
                target = dict(st["baseline"])
                exc = self.excursion.get(aid)
                if exc:
                    param, ticks, mag = exc
                    target[param] = _MODEL[param][0] + _EXC_DIR[param] * mag * _EXC_SIZE[param]
                    exc[1] -= 1
                    if exc[1] <= 0:
                        del self.excursion[aid]
                if st["day"] != now.date():
                    st["day"] = now.date()
                    st["values"]["sleep"] = min(max(self.rng.gauss(st["baseline"]["sleep"], 0.45), 5.0), 9.5)
                reading = {}
                for p in _ORDER:
                    b, noise, rev, lo, hi = _MODEL[p]
                    v = st["values"][p]
                    if p == "sleep":
                        reading[p] = round(v, 2)
                        continue
                    tgt = target[p]
                    if p == "activity":
                        tgt += 15 * math.sin(2 * math.pi * (hour - 9) / 24)
                    else:
                        tgt += _COUPLING.get(p, 0) * (st["values"]["activity"] - st["baseline"]["activity"])
                    if p in GROUND_DIURNAL_AMPLITUDE:
                        amp = GROUND_DIURNAL_AMPLITUDE[p]
                        if self.in_flight:
                            amp *= IN_FLIGHT_DIURNAL_FACTOR
                            noise *= IN_FLIGHT_VARIABILITY_FACTOR
                        tgt += amp * math.sin(2 * math.pi * (hour - 9) / 24)
                    v += rev * (tgt - v) + self.rng.gauss(0, noise)
                    v = min(max(v, lo), hi)
                    st["values"][p] = v
                    reading[p] = round(v, 2)
                reading["timestamp"] = now
                batch[aid] = reading
        return batch


class EcgGenerator:
    """Synthetic single-lead ECG (sum of Gaussians for P-Q-R-S-T). Waveform is illustrative."""
    _WAVES = [(0.18, 0.12, 0.025), (0.285, -0.12, 0.008), (0.30, 1.0, 0.010),
              (0.315, -0.25, 0.009), (0.50, 0.30, 0.050)]  # (center, amplitude, width) in beat phase

    def __init__(self, fs=100):
        self.fs, self.t = fs, 0.0
        self._rng = np.random.default_rng()

    def chunk(self, hr, seconds=1.0):
        n = max(1, int(seconds * self.fs))
        period = 60.0 / max(float(hr), 30.0)
        times = self.t + np.arange(n) / self.fs
        phase = (times % period) / period
        out = np.zeros(n)
        for c, a, w in self._WAVES:
            out += a * np.exp(-0.5 * ((phase - c) / w) ** 2)
        self.t += n / self.fs
        return out + self._rng.normal(0, 0.01, n)
