"""SQLite data-access layer. One Database object per thread (SQLite connections are
thread-bound); WAL mode lets the monitoring thread write while the GUI reads."""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

from config import DB_PATH, PARAM_KEYS
from database.models import SCHEMA_SQL
from utils.helpers import TS_FMT, now_str
from utils.logger import get_logger

log = get_logger("database")

ASTRONAUT_FIELDS = ("code", "full_name", "age", "role", "spacecraft", "blood_group",
                    "emergency_contact_name", "emergency_contact_phone", "health_status",
                    "joined_date", "is_active")
MISSION_FIELDS = ("code", "name", "spacecraft", "launch_date", "return_date",
                  "duration_days", "status", "description")
USER_FIELDS = ("username", "password_hash", "salt", "role", "full_name", "is_active",
               "failed_attempts", "locked_until", "last_login")


def _ts(v):
    return v.strftime(TS_FMT) if isinstance(v, datetime) else v


class Database:
    def __init__(self, path=DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), timeout=15)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    # ---- low level -------------------------------------------------------
    def q(self, sql, params=()):
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def q1(self, sql, params=()):
        rows = self.q(sql, params)
        return rows[0] if rows else None

    def x(self, sql, params=()):
        try:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur.lastrowid
        except sqlite3.Error:
            self.conn.rollback()
            raise

    def _insert(self, table, data, allowed):
        cols = [k for k in data if k in allowed]
        sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})"
        return self.x(sql, [data[c] for c in cols])

    def _update(self, table, id_, data, allowed):
        cols = [k for k in data if k in allowed]
        if not cols:
            return
        sql = f"UPDATE {table} SET {','.join(c + '=?' for c in cols)} WHERE id=?"
        self.x(sql, [data[c] for c in cols] + [id_])

    def close(self):
        try:
            self.conn.close()
        except sqlite3.Error:
            pass

    # ---- settings / logs ---------------------------------------------------
    def get_setting(self, key, default=None):
        r = self.q1("SELECT value FROM application_settings WHERE key=?", (key,))
        return r["value"] if r else default

    def set_setting(self, key, value):
        self.x("INSERT INTO application_settings(key,value,updated_at) VALUES(?,?,?) "
               "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
               (key, str(value), now_str()))

    def get_json_setting(self, key, default=None):
        v = self.get_setting(key)
        try:
            return json.loads(v) if v is not None else default
        except ValueError:
            return default

    def set_json_setting(self, key, obj):
        self.set_setting(key, json.dumps(obj))

    def log(self, level, source, message, user_id=None):
        getattr(log, level.lower(), log.info)("[%s] %s", source, message)
        self.x("INSERT INTO system_logs(timestamp,level,source,message,user_id) VALUES(?,?,?,?,?)",
               (now_str(), level.upper(), source, message, user_id))

    def list_logs(self, limit=300):
        return self.q("SELECT * FROM system_logs ORDER BY id DESC LIMIT ?", (limit,))

    # ---- users -------------------------------------------------------------
    def create_user(self, **data):
        return self._insert("users", data, USER_FIELDS)

    def get_user(self, username=None, user_id=None):
        if user_id is not None:
            return self.q1("SELECT * FROM users WHERE id=?", (user_id,))
        return self.q1("SELECT * FROM users WHERE username=? COLLATE NOCASE", (username,))

    def list_users(self):
        return self.q("SELECT id,username,full_name,role,is_active,last_login,created_at FROM users ORDER BY username")

    def update_user(self, user_id, **data):
        self._update("users", user_id, data, USER_FIELDS)

    def delete_user(self, user_id):
        self.x("DELETE FROM users WHERE id=?", (user_id,))

    # ---- astronauts ----------------------------------------------------------
    def next_astronaut_code(self):
        nums = [int(r["code"].split("-")[-1]) for r in self.q("SELECT code FROM astronauts")
                if r["code"].split("-")[-1].isdigit()]
        return f"AST-{(max(nums) + 1 if nums else 1):03d}"

    def add_astronaut(self, **data):
        return self._insert("astronauts", data, ASTRONAUT_FIELDS)

    def update_astronaut(self, astronaut_id, **data):
        self._update("astronauts", astronaut_id, data, ASTRONAUT_FIELDS)

    def delete_astronaut(self, astronaut_id):
        self.x("DELETE FROM astronauts WHERE id=?", (astronaut_id,))

    def get_astronaut(self, astronaut_id):
        return self.q1("SELECT * FROM astronauts WHERE id=?", (astronaut_id,))

    def get_astronaut_by_code(self, code):
        return self.q1("SELECT * FROM astronauts WHERE code=?", (code,))

    def list_astronauts(self, search="", status="", active_only=False):
        sql = ("SELECT a.*, (SELECT group_concat(m.name, ', ') FROM mission_assignments ma "
               "JOIN missions m ON m.id=ma.mission_id WHERE ma.astronaut_id=a.id) AS missions "
               "FROM astronauts a WHERE 1=1")
        p = []
        if search:
            sql += " AND (a.full_name LIKE ? OR a.code LIKE ? OR a.role LIKE ? OR a.spacecraft LIKE ?)"
            p += [f"%{search}%"] * 4
        if status:
            sql += " AND a.health_status=?"
            p.append(status)
        if active_only:
            sql += " AND a.is_active=1"
        return self.q(sql + " ORDER BY a.code", p)

    def set_health_status(self, astronaut_id, status):
        self.x("UPDATE astronauts SET health_status=? WHERE id=?", (status, astronaut_id))

    # ---- missions --------------------------------------------------------------
    def add_mission(self, **data):
        return self._insert("missions", data, MISSION_FIELDS)

    def update_mission(self, mission_id, **data):
        self._update("missions", mission_id, data, MISSION_FIELDS)

    def delete_mission(self, mission_id):
        self.x("DELETE FROM missions WHERE id=?", (mission_id,))

    def get_mission(self, mission_id):
        return self.q1("SELECT * FROM missions WHERE id=?", (mission_id,))

    def list_missions(self):
        return self.q("SELECT m.*, (SELECT COUNT(*) FROM mission_assignments ma WHERE ma.mission_id=m.id) "
                      "AS crew_count FROM missions m ORDER BY m.launch_date DESC")

    def active_mission(self):
        return self.q1("SELECT * FROM missions WHERE status='Active' ORDER BY launch_date LIMIT 1")

    def next_mission_code(self):
        nums = [int(r["code"].split("-")[-1]) for r in self.q("SELECT code FROM missions")
                if r["code"].split("-")[-1].isdigit()]
        return f"MSN-{(max(nums) + 1 if nums else 1):03d}"

    def set_assignments(self, mission_id, astronaut_ids):
        try:
            self.conn.execute("DELETE FROM mission_assignments WHERE mission_id=?", (mission_id,))
            self.conn.executemany("INSERT INTO mission_assignments(mission_id,astronaut_id) VALUES(?,?)",
                                  [(mission_id, a) for a in set(astronaut_ids)])
            self.conn.commit()
        except sqlite3.Error:
            self.conn.rollback()
            raise

    def mission_crew(self, mission_id):
        return self.q("SELECT a.* FROM astronauts a JOIN mission_assignments ma ON ma.astronaut_id=a.id "
                      "WHERE ma.mission_id=? ORDER BY a.code", (mission_id,))

    def astronaut_missions(self, astronaut_id):
        return self.q("SELECT m.* FROM missions m JOIN mission_assignments ma ON ma.mission_id=m.id "
                      "WHERE ma.astronaut_id=? ORDER BY m.launch_date DESC", (astronaut_id,))

    def set_astronaut_mission(self, astronaut_id, mission_id):
        """Profile-form helper: make mission_id (or none) the astronaut's assignment."""
        self.x("DELETE FROM mission_assignments WHERE astronaut_id=?", (astronaut_id,))
        if mission_id:
            self.x("INSERT OR IGNORE INTO mission_assignments(mission_id,astronaut_id) VALUES(?,?)",
                   (mission_id, astronaut_id))

    # ---- readings --------------------------------------------------------------
    def insert_readings(self, rows):
        if not rows:
            return
        cols = ["astronaut_id", "timestamp"] + PARAM_KEYS + ["status"]
        sql = f"INSERT INTO health_readings ({','.join(cols)}) VALUES ({','.join(':' + c for c in cols)})"
        data = [{**r, "timestamp": _ts(r["timestamp"])} for r in rows]
        try:
            self.conn.executemany(sql, data)
            self.conn.commit()
        except sqlite3.Error:
            self.conn.rollback()
            raise

    @staticmethod
    def _reading_where(astronaut_id, start, end, abnormal):
        w, p = ["1=1"], []
        if astronaut_id:
            w.append("r.astronaut_id=?"); p.append(astronaut_id)
        if start:
            w.append("r.timestamp>=?"); p.append(_ts(start))
        if end:
            w.append("r.timestamp<=?"); p.append(_ts(end))
        if abnormal:
            w.append("r.status!='normal'")
        return " AND ".join(w), p

    def query_readings(self, astronaut_id=None, start=None, end=None, abnormal=False,
                       limit=50, offset=0, order="DESC"):
        where, p = self._reading_where(astronaut_id, start, end, abnormal)
        order = "ASC" if order.upper() == "ASC" else "DESC"
        return self.q("SELECT r.*, a.code, a.full_name FROM health_readings r "
                      "JOIN astronauts a ON a.id=r.astronaut_id "
                      f"WHERE {where} ORDER BY r.timestamp {order}, r.id {order} LIMIT ? OFFSET ?",
                      p + [limit, offset])

    def count_readings(self, astronaut_id=None, start=None, end=None, abnormal=False):
        where, p = self._reading_where(astronaut_id, start, end, abnormal)
        return self.q1(f"SELECT COUNT(*) n FROM health_readings r WHERE {where}", p)["n"]

    def previous_reading(self, astronaut_id, timestamp):
        return self.q1("SELECT * FROM health_readings WHERE astronaut_id=? AND timestamp<? "
                       "ORDER BY timestamp DESC LIMIT 1", (astronaut_id, _ts(timestamp)))

    def readings_df(self, astronaut_ids=None, start=None, end=None):
        w, p = ["1=1"], []
        if astronaut_ids:
            w.append(f"r.astronaut_id IN ({','.join('?' * len(astronaut_ids))})")
            p += list(astronaut_ids)
        if start:
            w.append("r.timestamp>=?"); p.append(_ts(start))
        if end:
            w.append("r.timestamp<=?"); p.append(_ts(end))
        cols = ", ".join(f"r.{c}" for c in PARAM_KEYS)
        df = pd.read_sql_query(
            f"SELECT r.id, r.astronaut_id, a.code, a.full_name AS name, r.timestamp, {cols}, r.status "
            f"FROM health_readings r JOIN astronauts a ON a.id=r.astronaut_id "
            f"WHERE {' AND '.join(w)} ORDER BY r.timestamp", self.conn, params=p)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df

    def reading_bounds(self):
        r = self.q1("SELECT MIN(timestamp) lo, MAX(timestamp) hi, COUNT(*) n FROM health_readings")
        return r

    # ---- alerts ----------------------------------------------------------------
    def add_alert(self, astronaut_id, severity, parameter, value, message, source="threshold",
                  timestamp=None):
        return self.x("INSERT INTO alerts(astronaut_id,timestamp,severity,parameter,value,message,source) "
                      "VALUES(?,?,?,?,?,?,?)",
                      (astronaut_id, _ts(timestamp) or now_str(), severity, parameter, value, message, source))

    @staticmethod
    def _alert_where(severity, astronaut_id, ack):
        w, p = ["1=1"], []
        if severity:
            w.append("al.severity=?"); p.append(severity)
        if astronaut_id:
            w.append("al.astronaut_id=?"); p.append(astronaut_id)
        if ack is not None:
            w.append("al.acknowledged=?"); p.append(1 if ack else 0)
        return " AND ".join(w), p

    def list_alerts(self, severity=None, astronaut_id=None, ack=None, limit=200, offset=0,
                    start=None, end=None):
        where, p = self._alert_where(severity, astronaut_id, ack)
        if start:
            where += " AND al.timestamp>=?"; p.append(_ts(start))
        if end:
            where += " AND al.timestamp<=?"; p.append(_ts(end))
        return self.q("SELECT al.*, a.code, a.full_name FROM alerts al JOIN astronauts a ON a.id=al.astronaut_id "
                      f"WHERE {where} ORDER BY al.timestamp DESC, al.id DESC LIMIT ? OFFSET ?",
                      p + [limit, offset])

    def count_alerts(self, severity=None, astronaut_id=None, ack=None):
        where, p = self._alert_where(severity, astronaut_id, ack)
        return self.q1(f"SELECT COUNT(*) n FROM alerts al WHERE {where}", p)["n"]

    def ack_alert(self, alert_id, user_id):
        self.x("UPDATE alerts SET acknowledged=1, acknowledged_by=?, acknowledged_at=? WHERE id=?",
               (user_id, now_str(), alert_id))

    def ack_all(self, user_id, severity=None):
        sql, p = "UPDATE alerts SET acknowledged=1, acknowledged_by=?, acknowledged_at=? WHERE acknowledged=0", [user_id, now_str()]
        if severity:
            sql += " AND severity=?"; p.append(severity)
        self.x(sql, p)

    def unack_counts(self):
        out = {"normal": 0, "info": 0, "warning": 0, "critical": 0}
        for r in self.q("SELECT severity, COUNT(*) n FROM alerts WHERE acknowledged=0 GROUP BY severity"):
            out[r["severity"]] = r["n"]
        return out

    # ---- medical history (restricted) -----------------------------------------------
    def add_history(self, astronaut_id, entry_date, condition, notes, user_id):
        return self.x("INSERT INTO medical_history(astronaut_id,entry_date,condition,notes,recorded_by) "
                      "VALUES(?,?,?,?,?)", (astronaut_id, entry_date, condition, notes, user_id))

    def list_history(self, astronaut_id):
        return self.q("SELECT * FROM medical_history WHERE astronaut_id=? ORDER BY entry_date DESC", (astronaut_id,))

    def delete_history(self, history_id):
        self.x("DELETE FROM medical_history WHERE id=?", (history_id,))

    # ---- reports -----------------------------------------------------------------
    def add_report(self, astronaut_id, title, file_path, report_type, date_from, date_to, user_id):
        return self.x("INSERT INTO health_reports(astronaut_id,title,file_path,report_type,date_from,date_to,generated_by) "
                      "VALUES(?,?,?,?,?,?,?)",
                      (astronaut_id, title, str(file_path), report_type, date_from, date_to, user_id))

    def list_reports(self, limit=200):
        return self.q("SELECT r.*, a.full_name, u.username FROM health_reports r "
                      "LEFT JOIN astronauts a ON a.id=r.astronaut_id LEFT JOIN users u ON u.id=r.generated_by "
                      "ORDER BY r.created_at DESC, r.id DESC LIMIT ?", (limit,))

    def delete_report(self, report_id):
        self.x("DELETE FROM health_reports WHERE id=?", (report_id,))
