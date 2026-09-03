"""预配学校服务器数据库:九(4)班名单 + 管理员/老师账号 + 常用短语。

数据源:概览.xlsx(行序=学号序);在 钱佳祺 与 盛煊然 之间插入 周宇轩
(转学,占位保学号连续)。用法:
    python scripts/provision_school_db.py <xlsx路径> <输出db路径> <admin密码>
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import openpyxl

from server.auth import hash_password
from server.db import connect, init_db
from server.search import pinyin_of

INSERT_AFTER = "钱佳祺"      # 周宇轩 插在其后(盛煊然前)
INSERT_NAME = "周宇轩"
CLASS_NAME = "九(4)班"
TEACHER = ("zheng", "pw123456", "郑老师", "教师办公室")
SNIPPETS = ["订正数学作业", "带上练习册", "带上作图工具", "面谈"]


def load_roster(xlsx_path: str) -> list[str]:
    ws = openpyxl.load_workbook(xlsx_path, read_only=True)["Sheet1"]
    names = [r[0] for r in ws.iter_rows(values_only=True) if r[0]]
    i = names.index(INSERT_AFTER)
    assert names[i + 1] == "盛煊然", "名单顺序与预期不符(钱佳祺/盛煊然不再相邻)"
    names.insert(i + 1, INSERT_NAME)
    return names


def main() -> None:
    xlsx, db_path, admin_pw = sys.argv[1], sys.argv[2], sys.argv[3]
    names = load_roster(xlsx)
    conn = connect(db_path)
    init_db(conn)
    conn.execute(
        "INSERT INTO teachers(username,password_hash,role,display_name,office)"
        " VALUES (?,?,'admin','管理员','')",
        ("admin", hash_password(admin_pw)))
    conn.execute(
        "INSERT INTO teachers(username,password_hash,display_name,office)"
        " VALUES (?,?,?,?)",
        (TEACHER[0], hash_password(TEACHER[1]), TEACHER[2], TEACHER[3]))
    conn.execute("INSERT INTO classes(name,ord) VALUES (?,1)", (CLASS_NAME,))
    for no, name in enumerate(names, 1):
        full, ini = pinyin_of(name)
        conn.execute(
            "INSERT INTO students(class_id,name,student_no,pinyin_full,"
            "pinyin_initials) VALUES (1,?,?,?,?)",
            (name, f"{no:02d}", full, ini))
    for text in SNIPPETS:
        conn.execute("INSERT INTO snippets(teacher_id,text) VALUES (2,?)",
                     (text,))
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    print(f"班级={CLASS_NAME} 学生={n}人(含{INSERT_NAME}@13位) "
          f"账号=admin/管理员 + {TEACHER[0]}/{TEACHER[2]}")
    conn.close()


if __name__ == "__main__":
    main()
