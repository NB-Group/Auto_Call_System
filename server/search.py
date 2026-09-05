"""学生搜索:首字母前缀 > 全拼前缀 > 全拼包含 > 姓名子串(CONTRACTS v1.5)。"""
from pypinyin import Style, lazy_pinyin


def pinyin_of(name: str) -> tuple[str, str]:
    full = "".join(lazy_pinyin(name))
    initials = "".join(lazy_pinyin(name, style=Style.FIRST_LETTER))
    return full, initials


def _score(q: str, row) -> int | None:
    ql = q.strip().lower()
    if not ql:
        return None
    # 学号检索(2026-09-05 用户实测需求):学号前缀与首字母前缀同级
    # 最高 —— 名单按学号排,老师常直接敲 03 找 0305 的学生。
    if row["student_no"] and row["student_no"].lower().startswith(ql):
        return 0
    if row["pinyin_initials"].startswith(ql):
        return 0
    if row["pinyin_full"].startswith(ql):
        return 1
    if ql in row["pinyin_full"]:
        return 2
    if ql in row["name"].lower():
        return 3
    return None


def _name_key(name: str) -> tuple:
    """同级姓名排序键:逐字拼音(中文姓名惯例,如 李li<梁liang<刘liu),
    同音不同字再按码点保证确定性。纯码点排序会把 刘 排在 李/梁 前,
    与本模块测试约定的拼音序冲突。"""
    return (tuple(lazy_pinyin(name)), name)


def search_students(conn, q: str, limit: int = 8) -> list[dict]:
    rows = conn.execute(
        "SELECT s.id, s.name, s.pinyin_full, s.pinyin_initials, "
        "       s.student_no, c.name AS class_name "
        "FROM students s JOIN classes c ON c.id = s.class_id").fetchall()
    scored = [(s, r) for r in rows if (s := _score(q, r)) is not None]
    scored.sort(key=lambda t: (t[0], _name_key(t[1]["name"])))
    return [{k: r[k] for k in ("id", "name", "class_name", "pinyin_initials")}
            for _, r in scored[:limit]]


def search_snippets(conn, teacher_id: int, q: str, limit: int = 6) -> list[dict]:
    """短语搜索:拼音首字母前缀 > 文本子串,同级 use_count 降序(CONTRACTS v1.1)。"""
    ql = q.strip().lower()
    if not ql:
        rows = conn.execute(
            "SELECT id,text,use_count FROM snippets WHERE teacher_id=? "
            "ORDER BY use_count DESC LIMIT ?", (teacher_id, limit)).fetchall()
        return [dict(r) for r in rows]
    rows = conn.execute(
        "SELECT id,text,use_count FROM snippets WHERE teacher_id=? "
        "ORDER BY use_count DESC", (teacher_id,)).fetchall()
    scored = []
    for r in rows:
        ini = "".join(lazy_pinyin(r["text"], style=Style.FIRST_LETTER))
        if ini.startswith(ql):
            scored.append((0, -r["use_count"], r))
        elif ql in r["text"].lower():
            scored.append((1, -r["use_count"], r))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [dict(r) for _, _, r in scored[:limit]]
