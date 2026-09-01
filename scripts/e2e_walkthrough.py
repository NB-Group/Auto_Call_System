"""E2E 全链路走查:按 CONTRACTS.md 逐步驱动 HTTP+WS,覆盖联调手动清单:
建管理员 → 建老师 → 班级名单 → 拼音搜索 → 叫号 → 大屏收到 → 撤销 → 历史。

用法(需一个空库服务器,避免 needs_admin=false):
    mkdir -p /tmp/e2e/data && cd /tmp/e2e
    PYTHONPATH=<项目根> python -m server &
    python scripts/e2e_walkthrough.py --base http://127.0.0.1:8800
每步断言,全过打印 ALL PASS,任一失败非零退出。
"""
import argparse
import asyncio
import sys

import aiohttp

PASS = 0


def ok(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {label}{f' — {detail}' if detail and not cond else ''}")
    if not cond:
        sys.exit(1)
    PASS += 1


async def run(base: str) -> None:
    async with aiohttp.ClientSession() as s:
        async def get(path, token=None, expect=200):
            h = {"Authorization": f"Bearer {token}"} if token else {}
            async with s.get(base + path, headers=h) as r:
                return r.status, await r.json()

        async def post(path, body=None, token=None, expect=None):
            h = {"Authorization": f"Bearer {token}"} if token else {}
            async with s.post(base + path, json=body or {}, headers=h) as r:
                return r.status, await r.json()

        # 1. 引导状态(空库 → 需建管理员)
        st, j = await get("/api/bootstrap/status")
        ok("GET bootstrap/status", st == 200 and "needs_admin" in j, str(j))
        if not j["needs_admin"]:
            print("库非空(needs_admin=false),请用空 data/ 重启服务器后再跑")
            sys.exit(1)

        # 2. 建管理员
        st, admin = await post("/api/bootstrap/admin",
                               {"username": "admin", "password": "admin123",
                                "display_name": "管理员"})
        ok("POST bootstrap/admin", st == 201 and admin.get("role") == "admin")

        # 3. 建老师
        st, _ = await post("/api/admin/teachers",
                           {"username": "lhw", "password": "teacher123",
                            "display_name": "梁老师", "office": "年级办公室"},
                           token=admin["token"])
        ok("POST admin/teachers", st == 201)

        # 4. 班级 + 名单
        st, klass = await post("/api/admin/classes", {"name": "高二(3)班"},
                               token=admin["token"])
        ok("POST admin/classes", st == 201, str(klass))
        st, imp = await post(f"/api/admin/classes/{klass['id']}/students",
                             {"text": "梁皓文\n王小雨,李涵文 0305"},
                             token=admin["token"])
        ok("POST students 导入3人", st == 201 and imp.get("imported") == 3, str(imp))

        # 5. 老师登录 + 拼音搜索(lhw → 梁皓文)
        st, t = await post("/api/auth/login",
                           {"username": "lhw", "password": "teacher123"})
        tok = t.get("token")
        ok("teacher login", st == 200 and t.get("role") == "teacher")
        st, hits = await get("/api/students/search?q=lhw", token=tok)
        ok("search lhw→梁皓文",
           st == 200 and any(h["name"] == "梁皓文" for h in hits), str(hits))
        student = next(h for h in hits if h["name"] == "梁皓文")

        # 6. 短语
        st, snips = await post("/api/snippets", {"text": "订正数学作业"},
                               token=tok)
        ok("POST snippets", st == 201, str(snips))
        snip = next(x for x in snips if x["text"] == "订正数学作业")

        # 7. 显示端匿名订阅(先连后叫)
        ws = await s.ws_connect(base.replace("http", "ws") + "/ws")
        await ws.send_json({"type": "subscribe", "class_id": klass["id"]})
        hello = await asyncio.wait_for(ws.receive(), 5)
        ok("WS hello", hello.type == aiohttp.WSMsgType.TEXT
           and __import__("json").loads(hello.data)["type"] == "hello")

        # 8. 叫号 → 大屏收到 call
        st, called = await post("/api/calls", {"student_id": student["id"],
                                               "snippet_ids": [snip["id"]],
                                               "free_text": ""}, token=tok)
        ok("POST calls", st == 201, str(called))
        c = called.get("call", {})
        ok("call.message 含短语", "订正数学作业" in c.get("message", ""), str(c))
        msg = await asyncio.wait_for(ws.receive(), 5)
        import json as _json
        wsc = _json.loads(msg.data)
        ok("WS display call",
           wsc.get("type") == "call" and wsc["call"]["student_name"] == "梁皓文",
           msg.data)

        # 9. 今日记录(撤销前)
        st, today = await get("/api/calls/today", token=tok)
        ok("calls/today 1条", st == 200 and len(today.get("calls", [])) == 1)

        # 10. 撤销 → 大屏收到 retract
        cid = c["id"]
        async with s.delete(base + f"/api/calls/{cid}",
                            headers={"Authorization": f"Bearer {tok}"}) as r:
            ok("DELETE call", r.status == 200)
        msg = await asyncio.wait_for(ws.receive(), 5)
        wsr = _json.loads(msg.data)
        ok("WS display retract",
           wsr.get("type") == "retract" and wsr.get("call_id") == cid, msg.data)

        # 11. 历史:老师今日 + 管理员全班,均含 retracted_at
        st, today = await get("/api/calls/today", token=tok)
        ok("calls/today 撤销标记",
           st == 200 and today["calls"][0].get("retracted_at"))
        from datetime import date
        st, hist = await get(f"/api/admin/calls?date={date.today():%Y-%m-%d}",
                             token=admin["token"])
        ok("admin history", st == 200 and len(hist.get("calls", [])) == 1
           and hist["calls"][0].get("retracted_at"))
        await ws.close()

    print(f"ALL PASS ({PASS} 步)")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://127.0.0.1:8800")
    asyncio.run(run(p.parse_args().base))


if __name__ == "__main__":
    main()
