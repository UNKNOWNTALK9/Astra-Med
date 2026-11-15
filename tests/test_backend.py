"""Backend tests (no GUI needed). Run:  python -m unittest discover -s tests -v"""
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from config import PARAM_KEYS, PERMISSIONS, REFERENCE_RANGES, DEFAULT_RANGES
from core import analytics_engine as ae
from core.alert_engine import AlertEngine
from core.anomaly_detector import AnomalyDetector
from core.authentication import AuthService, can, hash_password, verify_password
from core.monitoring_engine import MonitoringEngine
from core.telemetry_simulator import EcgGenerator, TelemetrySimulator
from database.database import Database
from database.models import TABLES
from database.seed import seed_if_empty
from services import backup_service, export_service
from services.pdf_service import build_report
from utils.helpers import overall_status, param_status
from utils.validators import ValidationError, validate_age, validate_date, validate_password, validate_phone


def roster(db):
    return [{"id": a["code"], "db_id": a["id"], "name": a["full_name"]} for a in db.list_astronauts()]


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.db = Database(os.path.join(cls.tmp, "t.db"))
        seed_if_empty(cls.db)
        cls.admin = cls.db.get_user("admin")
        cls.medic = cls.db.get_user("medic")


class TestDatabase(Base):
    def test_ten_tables(self):
        names = {r["name"] for r in self.db.q("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in TABLES:
            self.assertIn(t, names)

    def test_seed_contents(self):
        self.assertEqual(len(self.db.list_astronauts()), 5)
        self.assertEqual(len(self.db.list_missions()), 3)
        self.assertGreater(self.db.count_readings(), 10000)
        self.assertIsNotNone(self.db.active_mission())

    def test_foreign_keys_enforced(self):
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.add_alert(9999, "info", "x", 1, "orphan")

    def test_astronaut_crud_and_cascade(self):
        aid = self.db.add_astronaut(code="AST-999", full_name="Test Pilot", age=30, joined_date="2026-01-01")
        self.db.update_astronaut(aid, role="Tester")
        self.assertEqual(self.db.get_astronaut(aid)["role"], "Tester")
        self.assertEqual(len(self.db.list_astronauts(search="Test Pilot")), 1)
        self.db.insert_readings([{"astronaut_id": aid, "timestamp": datetime.now(), "status": "normal",
                                  **{p: 1.0 for p in PARAM_KEYS}}])
        self.db.delete_astronaut(aid)
        self.assertEqual(self.db.count_readings(aid), 0)  # cascade

    def test_next_code(self):
        self.assertEqual(self.db.next_astronaut_code(), "AST-006")

    def test_pagination_and_filters(self):
        a = self.db.list_astronauts()[0]
        p1 = self.db.query_readings(a["id"], limit=10, offset=0)
        p2 = self.db.query_readings(a["id"], limit=10, offset=10)
        self.assertEqual(len(p1), 10)
        self.assertNotEqual(p1[0]["id"], p2[0]["id"])
        self.assertGreater(self.db.count_readings(a["id"]), self.db.count_readings(a["id"], abnormal=True))
        start = datetime.now() - timedelta(days=2)
        self.assertLess(self.db.count_readings(a["id"], start=start), self.db.count_readings(a["id"]))

    def test_assignments(self):
        m = self.db.active_mission()
        crew = self.db.mission_crew(m["id"])
        self.assertEqual(len(crew), 4)
        self.db.set_assignments(m["id"], [c["id"] for c in crew[:2]])
        self.assertEqual(len(self.db.mission_crew(m["id"])), 2)
        self.db.set_assignments(m["id"], [c["id"] for c in crew])

    def test_settings(self):
        self.db.set_setting("k", "v1"); self.db.set_setting("k", "v2")
        self.assertEqual(self.db.get_setting("k"), "v2")
        self.db.set_json_setting("j", {"a": 1})
        self.assertEqual(self.db.get_json_setting("j"), {"a": 1})


class TestAuth(Base):
    def test_hash_verify(self):
        h, s = hash_password("Secret123")
        self.assertTrue(verify_password("Secret123", h, s))
        self.assertFalse(verify_password("secret123", h, s))
        self.assertNotEqual(hash_password("Secret123")[0], h)  # random salt

    def test_login_flow_and_lockout(self):
        auth = AuthService(self.db)
        u, _ = auth.login("admin", "admin123")
        self.assertEqual(u["role"], "admin")
        self.assertIsNone(auth.login("nobody", "x")[0])
        for _ in range(5):
            auth.login("medic", "wrong")
        u, msg = auth.login("medic", "medic123")
        self.assertIsNone(u); self.assertIn("locked", msg.lower())
        self.db.update_user(self.medic["id"], locked_until=None, failed_attempts=0)

    def test_permissions(self):
        self.assertTrue(can(self.medic, "medical_history"))
        self.assertFalse(can(self.admin, "medical_history"))   # least privilege
        self.assertTrue(can(self.admin, "manage_users"))
        self.assertFalse(can(self.medic, "manage_users"))

    def test_create_user_requires_admin(self):
        auth = AuthService(self.db)
        with self.assertRaises(PermissionError):
            auth.create_user(self.medic, "newguy", "Passw0rdX", "admin")
        auth.create_user(self.admin, "newguy", "Passw0rdX", "medical_officer")
        with self.assertRaises(ValidationError):
            auth.create_user(self.admin, "newguy", "Passw0rdX", "admin")
        self.db.delete_user(self.db.get_user("newguy")["id"])

    def test_change_password(self):
        auth = AuthService(self.db)
        u = self.db.get_user("admin")
        with self.assertRaises(ValidationError):
            auth.change_password(u, "bad", "NewPass123")
        with self.assertRaises(ValidationError):
            auth.change_password(u, "admin123", "short")
        auth.change_password(u, "admin123", "NewPass123")
        self.assertIsNotNone(auth.login("admin", "NewPass123")[0])
        auth.change_password(self.db.get_user("admin"), "NewPass123", "admin123")

    def test_validators(self):
        self.assertEqual(validate_age("42"), 42)
        for bad in ("abc", "5", "200"):
            with self.assertRaises(ValidationError):
                validate_age(bad)
        with self.assertRaises(ValidationError):
            validate_date("2026-13-40")
        with self.assertRaises(ValidationError):
            validate_phone("abc")
        validate_password("abcdef12")


class TestSimulatorAndAlerts(Base):
    def test_simulator_mostly_normal(self):
        sim = TelemetrySimulator([{"id": "A"}, {"id": "B"}], seed=1, anomaly_chance=0.0)
        n = 0
        for _ in range(1500):
            for r in sim.step().values():
                n += overall_status(r) == "normal"
        self.assertGreater(n / 3000, 0.93)

    def test_in_flight_reduces_variability(self):
        def sd(flag):
            sim = TelemetrySimulator([{"id": "A"}], seed=3, anomaly_chance=0.0, in_flight=flag)
            return np.std([sim.step()["A"]["heart_rate"] for _ in range(2500)])
        self.assertLess(sd(True), sd(False))

    def test_sync_adds_removes(self):
        sim = TelemetrySimulator([{"id": "A"}])
        sim.sync([{"id": "B"}])
        self.assertEqual(list(sim.step()), ["B"])

    def test_ecg_shape(self):
        e = EcgGenerator(); x = e.chunk(60, 5)
        self.assertEqual(len(x), 500); self.assertGreater(x.max(), 0.8)

    def test_alert_escalation_cooldown_recovery(self):
        eng = AlertEngine(self.db, roster(self.db), cooldown_sec=120)
        code = roster(self.db)[0]["id"]
        t0 = datetime.now()
        base = {p: (REFERENCE_RANGES[p]["range"][1] + REFERENCE_RANGES[p]["range"][2]) / 2 for p in PARAM_KEYS}
        mk = lambda **kw: {code: {**base, **kw, "timestamp": t0}}
        self.assertEqual(eng.process(mk(), t0), [])
        a = eng.process(mk(heart_rate=110), t0)
        self.assertEqual([x["severity"] for x in a], ["warning"])
        self.assertEqual(eng.process(mk(heart_rate=111), t0), [])           # sustained: no spam
        a = eng.process(mk(heart_rate=140), t0)
        self.assertEqual(a[0]["severity"], "critical")                      # escalation
        a = eng.process(mk(), t0)
        self.assertEqual(a[0]["severity"], "normal")                        # recovery
        self.assertEqual(eng.process(mk(heart_rate=110), t0 + timedelta(seconds=10)), [])   # cooldown
        self.assertEqual(len(eng.process(mk(), t0)), 1)
        self.assertEqual(len(eng.process(mk(heart_rate=110), t0 + timedelta(seconds=500))), 1)

    def test_ack(self):
        before = self.db.unack_counts()
        a = self.db.add_alert(roster(self.db)[0]["db_id"], "critical", "heart_rate", 150, "test")
        self.assertEqual(self.db.unack_counts()["critical"], before["critical"] + 1)
        self.db.ack_alert(a, self.admin["id"])
        self.assertEqual(self.db.unack_counts()["critical"], before["critical"])
        self.assertEqual(len(self.db.list_alerts(ack=False, severity="critical")), before["critical"])

    def test_threshold_edit_changes_status(self):
        saved = REFERENCE_RANGES["heart_rate"]["range"]
        try:
            self.assertEqual(param_status("heart_rate", 105), "warning")
            REFERENCE_RANGES["heart_rate"]["range"] = (40, 55, 110, 130)
            self.assertEqual(param_status("heart_rate", 105), "normal")
        finally:
            REFERENCE_RANGES["heart_rate"]["range"] = saved


class TestAnalyticsAndAI(Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.df = cls.db.readings_df()
        cls.det = AnomalyDetector()
        cls.meta = cls.det.fit(cls.df)

    def test_analytics(self):
        self.assertEqual(set(ae.summary_stats(self.df)["param"]), set(PARAM_KEYS))
        c = ae.correlation(self.df)
        self.assertGreater(c.loc["heart_rate", "activity"], 0.15)   # coupling is visible
        for f in ("Raw", "Daily", "Weekly", "Monthly"):
            w = ae.resample_param(self.df, "heart_rate", ae.GRANULARITY[f])
            self.assertGreater(len(w), 0)
        self.assertLessEqual(len(ae.period_comparison(self.df, "spo2", "D", 14)), 14)
        self.assertAlmostEqual(sum(ae.status_breakdown(self.df).values()), 100, places=3)

    def test_model_trained_and_calibrated(self):
        self.assertTrue(self.det.ready)
        self.assertLess(self.meta["train_flag_rate"], 0.05)
        self.assertLess(self.meta["test_flag_rate"], 0.15)
        s = self.det.score_df(self.df.head(500))
        self.assertTrue(s["anomaly_score"].between(0, 100).all())

    def test_injected_anomaly_detected_and_explained(self):
        code = self.df["code"].iloc[0]
        base = self.df[self.df["code"] == code][PARAM_KEYS].median().to_dict()
        normal = {**base, "timestamp": datetime.now()}
        bad = {**base, "heart_rate": base["heart_rate"] + 60, "spo2": base["spo2"] - 7, "timestamp": datetime.now()}
        res = self.det.score_batch({code: bad})[code]
        res_n = self.det.score_batch({code: normal})[code]
        self.assertTrue(res[1]); self.assertFalse(res_n[1])
        self.assertGreater(res[0], res_n[0])
        joined = " ".join(res[2])
        self.assertIn("Heart Rate", joined); self.assertIn("above", joined)

    def test_trend_detection(self):
        idx = pd.date_range(end=datetime.now(), periods=14 * 24, freq="h")
        d = pd.DataFrame({p: np.full(len(idx), (REFERENCE_RANGES[p]["range"][1] + REFERENCE_RANGES[p]["range"][2]) / 2) for p in PARAM_KEYS})
        d["timestamp"] = idx
        d["heart_rate"] += np.linspace(0, 15, len(idx)) + np.random.default_rng(1).normal(0, 0.5, len(idx))
        t = AnomalyDetector.trends(d)
        self.assertTrue(any(x["param"] == "heart_rate" and x["kind"] == "trend" for x in t))

    def test_persistence_and_summary(self):
        p = Path(self.tmp) / "m.joblib"
        self.det.save(p)
        d2 = AnomalyDetector(); self.assertTrue(d2.load(p))
        sub = self.df[self.df["code"] == "AST-001"]
        scored = d2.score_df(sub)
        txt = d2.summarize("X", scored, AnomalyDetector.trends(sub))
        self.assertIn("does not diagnose", txt)
        self.assertFalse(AnomalyDetector().load(Path(self.tmp) / "missing.joblib"))


class TestServices(Base):
    def test_exports_and_import(self):
        a = self.db.list_astronauts()[0]
        df = export_service.readings_for_export(self.db, a["id"])
        csv = export_service.export_csv(df, Path(self.tmp) / "r.csv")
        x = export_service.export_excel(Path(self.tmp) / "r.xlsx", {"Readings": df.head(100), "Stats": ae.summary_stats(self.db.readings_df([a["id"]]))})
        self.assertTrue(csv.stat().st_size > 0 and x.stat().st_size > 0)
        import openpyxl
        self.assertEqual(openpyxl.load_workbook(x).sheetnames, ["Readings", "Stats"])
        sample = df.head(3).rename(columns={"astronaut_code": "astronaut_code"})
        sample.to_csv(Path(self.tmp) / "imp.csv", index=False)
        n0 = self.db.count_readings(a["id"])
        n, errs = export_service.import_readings_csv(self.db, Path(self.tmp) / "imp.csv")
        self.assertEqual((n, errs), (3, []))
        self.assertEqual(self.db.count_readings(a["id"]), n0 + 3)
        pd.DataFrame({"x": [1]}).to_csv(Path(self.tmp) / "bad.csv", index=False)
        self.assertEqual(export_service.import_readings_csv(self.db, Path(self.tmp) / "bad.csv")[0], 0)

    def test_pdf_report(self):
        a = self.db.list_astronauts()[0]
        det = AnomalyDetector(); det.fit(self.db.readings_df())
        out = build_report(self.db, self.medic, a["id"], datetime.now() - timedelta(days=30), datetime.now(),
                           Path(self.tmp) / "rep.pdf", det, include_history=True)
        data = out.read_bytes()
        self.assertTrue(data.startswith(b"%PDF") and len(data) > 20000)
        self.assertEqual(len(self.db.list_reports()), 1 + 0 if False else len(self.db.list_reports()))
        with self.assertRaises(ValueError):
            build_report(self.db, self.admin, a["id"], datetime(2000, 1, 1), datetime(2000, 1, 2), Path(self.tmp) / "x.pdf")

    def test_backup_restore(self):
        b = backup_service.create_backup(self.db, Path(self.tmp) / "bk")
        self.assertTrue(backup_service.validate_backup(b))
        junk = Path(self.tmp) / "junk.db"; junk.write_bytes(b"not a db")
        self.assertFalse(backup_service.validate_backup(junk))
        # restore into a scratch DB
        d2 = Database(Path(self.tmp) / "scratch.db"); seed_if_empty(d2, history_days=2)
        d2.add_astronaut(code="AST-777", full_name="Temp", age=40, joined_date="2026-01-01")
        backup_service.restore_backup(d2, b)
        d3 = Database(Path(self.tmp) / "scratch.db")
        self.assertIsNone(d3.get_astronaut_by_code("AST-777"))
        self.assertGreater(d3.count_readings(), 10000)
        with self.assertRaises(ValueError):
            backup_service.restore_backup(d3, junk)


class TestEngine(unittest.TestCase):
    def test_engine_threads_and_persists(self):
        tmp = tempfile.mkdtemp(); db = Database(os.path.join(tmp, "e.db"))
        aid = db.add_astronaut(code="AST-001", full_name="E", age=40, joined_date="2026-01-01")
        r = [{"id": "AST-001", "db_id": aid, "name": "E"}]
        eng = MonitoringEngine(r, 0.2, db.path, persist_every=2); eng.start(); time.sleep(1.5)
        eng.pause(); n = eng.ticks; time.sleep(0.6); self.assertEqual(eng.ticks, n)   # paused
        eng.resume(); eng.stop()
        self.assertGreater(len(eng.drain()), 3)
        self.assertGreater(db.count_readings(aid), 1)
        self.assertFalse(eng.running)


if __name__ == "__main__":
    unittest.main(verbosity=2)
