"""Background monitoring thread. Pushes telemetry batches onto a thread-safe queue (consumed by
the Tk main loop) and persists every Nth tick to SQLite using its OWN connection."""
import queue
import threading

from core.telemetry_simulator import TelemetrySimulator
from database.database import Database
from utils.helpers import overall_status
from utils.logger import get_logger

log = get_logger("monitoring")


class MonitoringEngine:
    def __init__(self, astronauts, interval=1.0, db_path=None, persist_every=10):
        self.roster = list(astronauts)
        self.sim = TelemetrySimulator(self.roster)
        self.interval = max(0.2, float(interval))
        self.persist_every = max(1, int(persist_every))
        self.db_path = db_path
        self.queue: queue.Queue = queue.Queue(maxsize=500)
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._thread = None
        self.ticks = 0

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    @property
    def paused(self):
        return self._paused.is_set()

    def set_interval(self, seconds):
        self.interval = max(0.2, float(seconds))

    def set_persist_every(self, n):
        self.persist_every = max(1, int(n))

    def sync_astronauts(self, astronauts):
        self.roster = list(astronauts)
        self.sim.sync(self.roster)

    def pause(self):
        self._paused.set()

    def resume(self):
        self._paused.clear()

    def start(self):
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="telemetry", daemon=True)
        self._thread.start()
        log.info("Monitoring engine started (interval %.1fs)", self.interval)

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        log.info("Monitoring engine stopped")

    def _run(self):
        db = Database(self.db_path) if self.db_path else None
        try:
            while not self._stop.is_set():
                if not self._paused.is_set():
                    try:
                        batch = self.sim.step()
                        self.ticks += 1
                        try:
                            self.queue.put_nowait(batch)
                        except queue.Full:
                            self.queue.get_nowait()
                            self.queue.put_nowait(batch)
                        if db and self.ticks % self.persist_every == 0:
                            self._persist(db, batch)
                    except Exception:
                        log.exception("Telemetry tick failed")
                self._stop.wait(self.interval)
        finally:
            if db:
                db.close()

    def _persist(self, db, batch):
        ids = {a["id"]: a["db_id"] for a in self.roster}
        rows = []
        for code, r in batch.items():
            if code in ids:
                row = {k: v for k, v in r.items()}
                row.update(astronaut_id=ids[code], status=overall_status(r))
                rows.append(row)
        try:
            db.insert_readings(rows)
        except Exception:
            log.exception("Persisting readings failed")

    def drain(self):
        out = []
        while True:
            try:
                out.append(self.queue.get_nowait())
            except queue.Empty:
                return out
