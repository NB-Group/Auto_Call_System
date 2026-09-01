import pytest

from server.db import connect, init_db
from server.search import pinyin_of, search_students


@pytest.fixture()
def db(tmp_path):
    conn = connect(tmp_path / "call.db")
    init_db(conn)
    conn.execute("INSERT INTO classes(name) VALUES ('高二(3)班')")
    students = [("梁皓文",), ("李涵文",), ("王小雨",), ("刘昊然",)]
    conn.executemany(
        "INSERT INTO students(class_id,name,pinyin_full,pinyin_initials) "
        "VALUES (1,?,?,?)",
        [(n, *pinyin_of(n)) for (n,) in students])
    conn.commit()
    yield conn
    conn.close()


def test_pinyin_of():
    assert pinyin_of("梁皓文") == ("lianghaowen", "lhw")


def test_initials_prefix_beats_full(db):
    rows = search_students(db, "lh")
    names = [r["name"] for r in rows]
    assert names[0] == "李涵文"          # lh 前缀(lhw 全命中也行,首字母优先)
    assert "梁皓文" in names              # lhw 命中首字母前缀


def test_full_pinyin_prefix(db):
    assert search_students(db, "liang")[0]["name"] == "梁皓文"


def test_name_substring(db):
    assert search_students(db, "皓文")[0]["name"] == "梁皓文"


def test_no_match(db):
    assert search_students(db, "zzz") == []


def test_limit_and_shape(db):
    rows = search_students(db, "l", 2)
    assert len(rows) == 2
    assert set(rows[0]) == {"id", "name", "class_name", "pinyin_initials"}
