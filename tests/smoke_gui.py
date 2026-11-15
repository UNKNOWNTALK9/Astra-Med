"""GUI smoke test using the headless stub (see gui_stub.py). Run:  python tests/smoke_gui.py"""
import os
import sys
import tempfile
import time
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gui_stub

TMP = tempfile.mkdtemp()
FD = gui_stub.install(os.path.join(TMP, "out"))

from config import NAV_ITEMS, PARAM_KEYS
from database.database import Database
from database.seed import seed_if_empty
import main as M

results = []


def step(name):
    def deco(fn):
        try:
            fn()
            results.append((name, True, ""))
        except Exception:
            results.append((name, False, traceback.format_exc(limit=4)))
        return fn
    return deco


db = Database(os.path.join(TMP, "g.db"))
seed_if_empty(db)
M.load_startup_settings(db)
user = db.get_user("admin")
medic = db.get_user("medic")
app = None


@step("construct App with all 10 pages")
def _():
    global app
    app = M.App(db, user)
    assert set(app.pages) == {k for k, _, _ in NAV_ITEMS}
    assert len(app.astronauts) == 5


@step("telemetry loop feeds pages and alerts")
def _():
    for _ in range(12):
        app.engine.queue.put(app.engine.sim.step())
    app._poll()
    d = app.pages["dashboard"]
    assert len(d.latest) == 5
    app.engine.queue.put({a["id"]: {**app.engine.sim.step()[a["id"]], "heart_rate": 150.0} for a in app.astronauts[:1]})
    app._poll()
    assert db.count_alerts(severity="critical") >= 1
    assert db.unack_counts()["critical"] >= 1


@step("navigate every page")
def _():
    for k, _, _ in NAV_ITEMS:
        app.show_page(k)
        assert app.current == k


@step("monitoring page: select, ecg, tiles, pause")
def _():
    p = app.pages["monitoring"]
    p.select(app.astronauts[1]["id"])
    for _ in range(3):
        app.engine.queue.put(app.engine.sim.step())
    app._poll()
    assert len(p.ecg.data["ecg"]) > 0
    p._toggle_pause(); assert app.engine.paused
    p._toggle_pause(); assert not app.engine.paused


@step("analytics: every tab renders (real matplotlib + seaborn)")
def _():
    p = app.pages["analytics"]
    for rng in ("Last 24 hours", "Last 7 days", "All data"):
        p.range_cb.set(rng)
        p.apply()
        for t in ("Trends", "Vital Overview", "Blood Pressure", "Sleep", "Correlation", "Comparison"):
            getattr(p, "_draw_" + t.lower().replace(" ", "_"))(p.panels[t])
    for g in ("Raw", "Daily", "Weekly", "Monthly"):
        p.gran_cb.set(g); p.apply()
        for t in ("Trends", "Comparison"):
            p.tabs.set(t); p.drawn.clear(); p._on_tab()
    p.astro_cb.set(p._names[1]); p.apply()
    p.range_cb.set("Custom"); p.from_e.insert(0, "2020-01-01"); p.to_e.insert(0, "2030-01-01"); p.apply()


@step("history: search, paginate, compare, export")
def _():
    p = app.pages["history"]
    p.search(); assert p.total > 0 and len(p.table.rows) == 50
    p.go(1); assert p.page == 1
    p.table.tree._sel = ["3"]; p.compare()
    p.preselect(astronaut_code="AST-002"); assert all(r["code"] == "AST-002" for r in p.table.rows.values())
    p.abn.select(); p.search()
    p.export("csv"); p.export("xlsx")
    assert (Path(TMP) / "out.csv").exists() and (Path(TMP) / "out.xlsx").exists()


@step("AI page: analyze + retrain thread")
def _():
    p = app.pages["ai"]
    p.analyze()
    assert "SIMULATED" in p.summary._text or "readings" in p.summary._text
    p.retrain()
    for _ in range(100):
        time.sleep(0.2)
        if not p.q.empty():
            break
    assert not p.q.empty(); kind, payload = p.q.get(); assert kind == "ok", payload


@step("alerts page: filter, acknowledge")
def _():
    p = app.pages["alerts"]
    p.sev_cb.set("critical"); p.ack_cb.set("Unacknowledged"); p.apply()
    assert len(p.table.rows) >= 1
    p.table.tree._sel = ["0"]; before = db.unack_counts()["critical"]; p.ack_selected()
    assert db.unack_counts()["critical"] == before - 1
    p.ack_all(); assert sum(v for k, v in db.unack_counts().items()) == 0


@step("profiles: add / edit / mission assign / delete rebuilds roster")
def _():
    p = app.pages["profiles"]
    missions, names, _f = p._fields()
    base = {"code": "AST-006", "full_name": "Test Astro", "age": "36", "role": "Tester", "spacecraft": "Orion",
            "mission": names[1], "blood_group": "A+", "ec_name": "Kin", "ec_phone": "+1 555 0100", "joined_date": "2026-01-01"}
    p._save(base, None, missions, names)
    assert len(app.astronauts) == 6 and len(app.pages["dashboard"].cards) == 6
    a = db.get_astronaut_by_code("AST-006")
    p._save({**base, "full_name": "Test Astro II", "mission": "(none)"}, a, missions, names)
    assert db.get_astronaut(a["id"])["full_name"] == "Test Astro II" and not db.astronaut_missions(a["id"])
    try:
        p._save({**base, "age": "12"}, None, missions, names); assert False
    except Exception as e:
        assert "Age" in str(e)
    for _ in range(3):
        app.engine.queue.put(app.engine.sim.step())
    app._poll(); assert len(app.pages["dashboard"].latest) == 6
    p.table.tree._sel = ["5"]; p.refresh(); p.table.tree._sel = ["5"]
    db.delete_astronaut(a["id"]); app.refresh_astronauts(); assert len(app.astronauts) == 5


@step("medical history is restricted by role")
def _():
    from core.authentication import can
    assert can(medic, "medical_history") and not can(user, "medical_history")
    p = app.pages["profiles"]
    p.table.tree._sel = ["0"]; p.refresh(); p.table.tree._sel = ["0"]
    p.medical()  # admin -> denied dialog and audit log entry, no exception
    assert any("Denied medical history" in r["message"] for r in db.list_logs(20))


@step("missions: create / edit / assign / progress")
def _():
    from modules.mission_management import progress
    p = app.pages["missions"]
    v = {"code": "MSN-004", "name": "Test Mission", "spacecraft": "X", "launch": "2026-12-01", "ret": "2027-02-01", "status": "Planned", "desc": "d"}
    p._save(v, None)
    m = next(x for x in db.list_missions() if x["code"] == "MSN-004")
    assert m["duration_days"] == 62 and progress(m) == 0
    try:
        p._save({**v, "ret": "2026-11-01"}, m); assert False
    except Exception as e:
        assert "after" in str(e)
    db.set_assignments(m["id"], [a["db_id"] for a in app.astronauts[:2]]); p.refresh()
    p.table.tree._sel = ["0"]; p.show_detail()
    assert progress(db.active_mission()) > 0


@step("reports: PDF thread + csv + xlsx")
def _():
    p = app.pages["reports"]
    p.make_pdf()
    for _ in range(150):
        time.sleep(0.2)
        if not p.q.empty():
            break
    kind, payload = p.q.get(); assert kind == "ok", payload
    assert Path(payload).read_bytes().startswith(b"%PDF")
    p.export("csv"); p.export("xlsx"); p.refresh()
    assert len(db.list_reports()) >= 3


@step("settings: thresholds, monitoring, users, backup, logs")
def _():
    from config import REFERENCE_RANGES
    p = app.pages["settings"]
    p.save_thr()
    p.thr["heart_rate"][2].delete(0); p.thr["heart_rate"][2].insert(0, "110")
    p.save_thr(); assert REFERENCE_RANGES["heart_rate"]["range"][2] == 110.0
    p.reset_thr(); assert REFERENCE_RANGES["heart_rate"]["range"][2] == 100
    p.interval.set(2.0); p.persist.set(5); p.cool.delete(0); p.cool.insert(0, "30")
    p.save_monitoring(); assert app.engine.interval == 2.0 and app.alert_engine.cooldown == 30
    p.save_appearance(); p.backup(); p.load_logs(); p.load_users(); p.preselect(tab="Alert Thresholds")
    p.pw["old"].insert(0, "admin123"); p.pw["new"].insert(0, "NewPass99"); p.pw["conf"].insert(0, "NewPass99")
    p.change_pw(); assert app.auth.login("admin", "NewPass99")[0]
    app.show_page("settings")


@step("apply saved ranges at startup")
def _():
    from config import REFERENCE_RANGES
    db.set_json_setting("reference_ranges", {"heart_rate": [40, 55, 105, 130]})
    from modules.settings import apply_saved_ranges
    apply_saved_ranges(db); assert REFERENCE_RANGES["heart_rate"]["range"][2] == 105


@step("logout & close")
def _():
    app.logout(); assert app.logout_requested and not app.engine.running


ok = sum(r[1] for r in results)
for name, passed, err in results:
    print(("PASS  " if passed else "FAIL  ") + name)
    if err:
        print(err)
print(f"\n{ok}/{len(results)} GUI smoke steps passed")
sys.exit(0 if ok == len(results) else 1)
