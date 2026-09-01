"""学生搜索:拼音首字母 > 全拼 > 姓名子串(CONTRACTS)。"""
from pypinyin import Style, lazy_pinyin


def pinyin_of(name: str) -> tuple[str, str]:
    full = "".join(lazy_pinyin(name))
    initials = "".join(lazy_pinyin(name, style=Style.FIRST_LETTER))
    return full, initials


def _score(q: str, row) -> int | None:
    ql = q.strip().lower()
    if not ql:
        return None
    if row["pinyin_initials"].startswith(ql):
        return 0
    if row["pinyin_full"].startswith(ql):
        return 1
    if ql in row["name"].lower():
        return 2
    return None


def _name_key(name: str) -> tuple:
    """同级姓名排序键:逐字拼音(中文姓名惯例,如 李li<梁liang<刘liu),
    同音不同字再按码点保证确定性。纯码点排序会把 刘 排在 李/梁 前,
    与本模块测试约定的拼音序冲突。"""
    return (tuple(lazy_pinyin(name)), name)


def search_students(conn, q: str, limit: int = 8) -> list[dict]:
    rows = conn.execute(
        "SELECT s.id, s.name, s.pinyin_full, s.pinyin_initials, "
        "       c.name AS class_name "
        "FROM students s JOIN classes c ON c.id = s.class_id").fetchall()
    scored = [(s, r) for r in rows if (s := _score(q, r)) is not None]
    scored.sort(key=lambda t: (t[0], _name_key(t[1]["name"])))
    return [{k: r[k] for k in ("id", "name", "class_name", "pinyin_initials")}
            for _, r in scored[:limit]]
