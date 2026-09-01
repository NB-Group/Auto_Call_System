import sqlite3

import pytest

from server.db import connect, init_db


@pytest.fixture()
def db(tmp_path):
    conn = connect(tmp_path / "call.db")
    init_db(conn)
    yield conn
    conn.close()


def test_wal_and_fk(db):
    mode = db.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_all_tables_created(db):
    names = {r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"settings", "teachers", "classes", "students",
            "snippets", "calls", "sessions"} <= names


def test_init_idempotent(db):
    init_db(db)  # 不抛错即过


def test_cascade_delete_class_removes_students(db):
    db.execute("INSERT INTO classes(name) VALUES ('高二(3)班')")
    db.execute("INSERT INTO students(class_id,name) VALUES (1,'梁皓文')")
    db.commit()
    db.execute("DELETE FROM classes WHERE id=1")
    db.commit()
    assert db.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 0
