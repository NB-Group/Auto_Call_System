import pytest

from server.db import connect, init_db
from server.search import pinyin_of, search_students


@pytest.fixture()
def db(tmp_path):
    conn = connect(tmp_path / "call.db")
    init_db(conn)
    conn.execute("INSERT INTO classes(name) VALUES ('高二(3)班')")
    students = [("梁皓文",), ("李涵文",), ("王小雨",), ("刘昊然",),
                ("王佳琪",), ("张嘉琪",), ("李佳琪",), ("贾启明",)]
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


def test_full_pinyin_contains(db):
    """同名拼音全班可查:"jiaqi" 命中所有 佳琪/嘉琪(不论姓氏),
    同级按逐字拼音序 李li < 王wang < 张zhang(CONTRACTS v1.5)。"""
    names = [r["name"] for r in search_students(db, "jiaqi")]
    assert names == ["贾启明", "李佳琪", "王佳琪", "张嘉琪"]


def test_prefix_outranks_contains(db):
    """全拼前缀命中(jiaqiming)排在仅包含命中(wangjiaqi)之前。"""
    rows = search_students(db, "jiaqi")
    assert rows[0]["name"] == "贾启明"   # tier 1:全拼前缀
    assert rows[1]["name"] == "李佳琪"   # tier 2:全拼包含


def test_name_substring_still_lowest(db):
    """汉字子串仍垫底:仅姓名含"佳琪"者命中,拼音命中者不混入。"""
    assert {r["name"] for r in search_students(db, "佳琪")} == {"王佳琪", "李佳琪"}


def test_no_match(db):
    assert search_students(db, "zzz") == []


def test_limit_and_shape(db):
    rows = search_students(db, "l", 2)
    assert len(rows) == 2
    assert set(rows[0]) == {"id", "name", "class_name", "pinyin_initials"}


def test_student_no_search(db):
    """学号检索(2026-09-05):学号前缀最高级匹配,数字直达。"""
    db.execute(
        "INSERT INTO students(class_id,name,pinyin_full,pinyin_initials,"
        "student_no) VALUES (1,'赵无极',?,?,?)",
        (*pinyin_of("赵无极"), "0305"))
    db.commit()
    assert [r["name"] for r in search_students(db, "0305")] == ["赵无极"]
    assert [r["name"] for r in search_students(db, "03")] == ["赵无极"]
    # 拼音检索不受影响
    assert [r["name"] for r in search_students(db, "zwj")] == ["赵无极"]
