import pytest

from server.db import connect, init_db
from server.search import search_snippets


@pytest.fixture()
def db(tmp_path):
    conn = connect(tmp_path / "call.db")
    init_db(conn)
    # brief 原稿直接插 snippets(teacher_id=1),但 connect() 开启
    # PRAGMA foreign_keys=ON,无 teachers 行会 FOREIGN KEY constraint failed。
    # 补一行教师(AUTOINCREMENT → id=1),断言全部不变。
    conn.execute(
        "INSERT INTO teachers(username,password_hash) VALUES ('t','x')")
    conn.executemany(
        "INSERT INTO snippets(teacher_id,text,use_count) VALUES (1,?,?)",
        [("订正数学作业", 3), ("订正英语作文", 1), ("带上作图工具", 5),
         ("带上练习册", 2), ("面谈", 0)])
    conn.commit()
    yield conn
    conn.close()


def test_initials_prefix_sorted_by_usage(db):
    rows = search_snippets(db, 1, "dz")
    assert [r["text"] for r in rows] == ["订正数学作业", "订正英语作文"]


def test_substring_fallback(db):
    assert search_snippets(db, 1, "练习")[0]["text"] == "带上练习册"


def test_no_match(db):
    assert search_snippets(db, 1, "zz") == []
