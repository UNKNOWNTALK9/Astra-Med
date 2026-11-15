"""Demo data: fictional crew, missions, 45 days of SIMULATED history, alerts, medical notes."""
from datetime import datetime, timedelta

from config import PARAM_KEYS
from core.alert_engine import AlertEngine
from core.authentication import hash_password
from core.telemetry_simulator import TelemetrySimulator
from utils.helpers import TS_FMT, overall_status

CREW = [
    ("Cmdr. Elena Vasquez", 42, "Mission Commander", "Orion Endeavour", "O+", "Marco Vasquez", "+1 713 555 0101"),
    ("Dr. Kenji Watanabe", 38, "Flight Surgeon", "Orion Endeavour", "A+", "Aiko Watanabe", "+81 3 5550 0102"),
    ("Amara Okafor", 35, "Pilot", "Orion Endeavour", "B+", "Chidi Okafor", "+234 1 555 0103"),
    ("Lars Eriksson", 45, "Systems Engineer", "Orion Endeavour", "AB-", "Ingrid Eriksson", "+46 8 555 0104"),
    ("Priya Nair", 33, "Mission Specialist", "Gateway Logistics 2", "O-", "Arun Nair", "+91 22 5550 0105"),
]
HISTORY_NOTES = [
    [("2025-11-04", "Annual flight physical", "Cleared for long-duration flight.")],
    [("2025-09-18", "Seasonal allergic rhinitis", "Resolved; no current medication.")],
    [("2026-01-12", "Minor lumbar strain", "Physiotherapy completed; full duty.")],
    [("2025-12-02", "Annual flight physical", "Cleared. Mild lipid elevation, diet advised.")],
    [("2026-02-20", "Annual flight physical", "Cleared for flight.")],
]


def seed_if_empty(db, history_days=45, step_minutes=30):
    if db.q1("SELECT COUNT(*) n FROM users")["n"] > 0:
        return False
    for username, pw, role, name in (("admin", "admin123", "admin", "Mission Administrator"),
                                     ("medic", "medic123", "medical_officer", "Dr. Flight Medical Officer")):
        h, s = hash_password(pw)
        db.create_user(username=username, password_hash=h, salt=s, role=role, full_name=name)

    today = datetime.now().date()
    d = lambda off: (today + timedelta(days=off)).strftime("%Y-%m-%d")
    m1 = db.add_mission(code="MSN-001", name="Artemis Horizon-1", spacecraft="Orion Endeavour",
                        launch_date=d(-40), return_date=d(140), duration_days=180, status="Active",
                        description="Long-duration cislunar mission with crew health research.")
    m2 = db.add_mission(code="MSN-002", name="Lunar Gateway Resupply", spacecraft="Gateway Logistics 2",
                        launch_date=d(90), return_date=d(150), duration_days=60, status="Planned",
                        description="Resupply and habitat outfitting mission.")
    db.add_mission(code="MSN-003", name="HERA-7 Analog", spacecraft="HERA Habitat", launch_date=d(-300),
                   return_date=d(-270), duration_days=30, status="Completed",
                   description="Ground analog isolation study.")

    ids = []
    for i, (name, age, role, craft, bg, ec, ph) in enumerate(CREW):
        aid = db.add_astronaut(code=f"AST-{i + 1:03d}", full_name=name, age=age, role=role, spacecraft=craft,
                               blood_group=bg, emergency_contact_name=ec, emergency_contact_phone=ph,
                               joined_date=d(-40 - 20 * i))
        ids.append(aid)
        for dt, cond, notes in HISTORY_NOTES[i]:
            db.add_history(aid, dt, cond, notes, None)
    db.set_assignments(m1, ids[:4])
    db.set_assignments(m2, ids[2:])

    roster = [{"id": f"AST-{i + 1:03d}", "db_id": aid, "name": CREW[i][0]} for i, aid in enumerate(ids)]
    sim = TelemetrySimulator(roster, seed=2026, anomaly_chance=0.0015, excursion_ticks=(2, 6))
    alerts = AlertEngine(db, roster, cooldown_sec=0)
    end = datetime.now().replace(second=0, microsecond=0, minute=(datetime.now().minute // 30) * 30)
    steps = int(history_days * 24 * 60 / step_minutes)
    by_code = {a["id"]: a["db_id"] for a in roster}
    rows = []
    for k in range(steps):
        ts = end - timedelta(minutes=step_minutes * (steps - 1 - k))
        batch = sim.step(now=ts)
        for code, r in batch.items():
            rows.append({**r, "astronaut_id": by_code[code], "status": overall_status(r)})
        alerts.process(batch, now=ts)
        if len(rows) >= 5000:
            db.insert_readings(rows); rows = []
    db.insert_readings(rows)
    cutoff = (datetime.now() - timedelta(days=1)).strftime(TS_FMT)
    db.x("UPDATE alerts SET acknowledged=1, acknowledged_by=1, acknowledged_at=timestamp WHERE timestamp<?", (cutoff,))
    db.set_setting("seeded_at", datetime.now().strftime(TS_FMT))
    db.log("INFO", "seed", f"Demo data created ({steps * len(ids)} simulated readings)")
    return True
