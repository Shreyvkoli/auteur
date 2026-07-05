"""
Database — Supabase client with file-backed dev mode.
When Supabase keys are placeholder values, uses a JSON file for shared state
between server + worker processes.
"""

import json
import os
import fcntl
import errno
from core.config import settings

DEV_MODE = settings.dev_mode
DEV_DB_PATH = os.path.join(os.path.dirname(__file__), "..", ".dev_db.json")
DEV_LOCK_PATH = DEV_DB_PATH + ".lock"


def _acquire_lock():
    """Cross-process file lock using flock. Blocks until acquired."""
    fd = os.open(DEV_LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o644)
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def _release_lock(fd):
    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)


def _load_db_unlocked():
    """Read dev DB without acquiring lock. Caller must hold lock."""
    if os.path.exists(DEV_DB_PATH):
        with open(DEV_DB_PATH, "r") as f:
            return json.load(f)
    return {}


def _write_db_unlocked(data):
    """Write to dev DB without acquiring lock. Caller must hold lock."""
    with open(DEV_DB_PATH, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _modify_db(transform_fn):
    """Atomically read the dev DB, apply a transform, and write back.
    
    transform_fn receives the full DB dict and returns a result.
    The entire read-modify-write cycle happens under a single cross-process lock.
    """
    fd = _acquire_lock()
    try:
        db = _load_db_unlocked()
        result = transform_fn(db)
        _write_db_unlocked(db)
        return result
    finally:
        _release_lock(fd)


def _read_db():
    """Read the dev DB atomically."""
    fd = _acquire_lock()
    try:
        return _load_db_unlocked()
    finally:
        _release_lock(fd)


# ── In-Memory Dev Store ───────────────────────────────────────────────────────

class _DevQuery:
    def __init__(self, table_name, db_path):
        self._table = table_name
        self._db_path = db_path
        self._filters = []
        self._order = None
        self._limit_n = None
        self._offset_n = 0
        self._single = False
        self._result_data = None
        self._is_update = False
        self._update_data = None
        self._is_delete = False

    def eq(self, field, value):
        self._filters.append(("eq", field, value))
        return self

    def neq(self, field, value):
        self._filters.append(("neq", field, value))
        return self

    def gte(self, field, value):
        self._filters.append(("gte", field, value))
        return self

    def order(self, field, desc=False):
        self._order = (field, desc)
        return self

    def limit(self, n):
        self._limit_n = n
        return self

    def range(self, start, end):
        self._offset_n = start
        self._limit_n = end - start + 1
        return self

    def single(self):
        self._single = True
        return self

    def _apply(self, db):
        rows = list(db.get(self._table, []))
        for op, field, value in self._filters:
            if op == "eq":
                rows = [r for r in rows if r.get(field) == value]
            elif op == "neq":
                rows = [r for r in rows if r.get(field) != value]
            elif op == "gte":
                rows = [r for r in rows if r.get(field, 0) >= value]
        if self._order:
            field, desc = self._order
            rows.sort(key=lambda r: r.get(field, ""), reverse=desc)
        if self._limit_n:
            rows = rows[:self._limit_n]
        return rows

    def execute(self):
        if self._result_data is not None:
            return _DevResult(self._result_data)

        if self._is_update:
            def do_update(db):
                rows = self._apply(db)
                table = db.get(self._table, [])
                for row in rows:
                    for trow in table:
                        if trow.get("id") == row.get("id"):
                            trow.update(self._update_data)
                return rows
            return _DevResult(_modify_db(do_update))

        if self._is_delete:
            def do_delete(db):
                rows = self._apply(db)
                ids_to_delete = {(r.get("id"),) for r in rows}
                if self._table in db:
                    db[self._table] = [
                        r for r in db[self._table]
                        if r.get("id") not in {rid[0] for rid in ids_to_delete}
                    ]
                return None
            return _DevResult(_modify_db(do_delete))

        db = _read_db()
        rows = self._apply(db)
        total = len(rows)
        if self._offset_n:
            rows = rows[self._offset_n:]
        if self._limit_n:
            rows = rows[:self._limit_n]
        if self._single:
            return _DevResult(rows[0] if rows else None)
        result = _DevResult(rows)
        result.count = total
        return result


class _DevResult:
    def __init__(self, data, total=None):
        self.data = data
        self.count = total if total is not None else (len(data) if data else 0)


class _DevTable:
    def __init__(self, name, db_path):
        self._name = name
        self._db_path = db_path

    def select(self, *args, **kwargs):
        return _DevQuery(self._name, self._db_path)

    def insert(self, data):
        def do_insert(db):
            if self._name not in db:
                db[self._name] = []
            row = data.copy() if isinstance(data, dict) else data
            db[self._name].append(row)
            return [row]
        result = _modify_db(do_insert)
        q = _DevQuery(self._name, self._db_path)
        q._result_data = result
        return q

    def update(self, data):
        q = _DevQuery(self._name, self._db_path)
        q._is_update = True
        q._update_data = data
        return q

    def upsert(self, data):
        return self.insert(data)

    def delete(self):
        q = _DevQuery(self._name, self._db_path)
        q._is_delete = True
        return q


class _DevSupabase:
    def __init__(self):
        pass

    def table(self, name):
        return _DevTable(name, DEV_DB_PATH)


# ── Public API ────────────────────────────────────────────────────────────────

_dev = _DevSupabase() if DEV_MODE else None


def get_supabase():
    if DEV_MODE:
        return _dev
    from supabase import create_client
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def get_supabase_anon():
    if DEV_MODE:
        return _dev
    from supabase import create_client
    return create_client(settings.supabase_url, settings.supabase_anon_key)
