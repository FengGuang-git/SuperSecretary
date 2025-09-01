from app.chat import Client
import os
import datetime
from pathlib import Path
from dotenv import load_dotenv
from app.chat import Client  # 你的 Client 类

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]  # SuperSecretary/

DATA_DIR = ROOT / "data"
DIARY_DIR = DATA_DIR / "diary"
REPORT_DIR = DATA_DIR / "reports"
PROMPT_PATH = ROOT / "app" / "prompts" / "report.md"
for p in (DIARY_DIR, REPORT_DIR):
    p.mkdir(parents=True, exist_ok=True)

def _load_client() -> Client:
    c = Client()
    # 使用 config.json 的第一个模型；如需指定可改为 set_model_by_name
    c.set_model(c.config["models"][0])
    # 覆盖系统提示为周报秘书
    sys_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    c.messages = [{"role": "system", "content": sys_prompt}]
    return c

def add_diary(text: str, date_str: str | None = None) -> str:
    d = date_str or datetime.date.today().isoformat()
    fp = DIARY_DIR / f"{d}.md"
    with fp.open("a", encoding="utf-8") as f:
        f.write(text.strip() + "\n")
    return str(fp)

def _collect_notes(start: str, end: str) -> str:
    s = datetime.date.fromisoformat(start)
    e = datetime.date.fromisoformat(end)
    cur, blocks = s, []
    while cur <= e:
        f = DIARY_DIR / f"{cur.isoformat()}.md"
        if f.exists():
            blocks.append(f"### {cur.isoformat()}\n{f.read_text(encoding='utf-8')}")
        cur += datetime.timedelta(days=1)
    return "\n".join(blocks) or "（本周暂无日记，请列出待确认清单。）"

def gen_weekly(start: str, end: str) -> str:
    diary = _collect_notes(start, end)
    prompt = f"""请基于以下日记生成结构化周报（Markdown）：
周期：{start} ~ {end}
要求：岗位为CAM软件开发工程师；附一条简短企业文化关联，不要太长。

{diary}
"""
    client = _load_client()
    resp = client.send(prompt)
    content = (resp.get("content") or "").strip()
    out = REPORT_DIR / f"weekly_{start}_to_{end}.md"
    out.write_text(content, encoding="utf-8")
    return str(out)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="追加一条日记")
    p_add.add_argument("--text", required=True)
    p_add.add_argument("--date", default=datetime.date.today().isoformat())

    p_rep = sub.add_parser("report", help="生成本周周报")
    p_rep.add_argument("--start")
    p_rep.add_argument("--end")

    args = parser.parse_args()
    if args.cmd == "add":
        path = add_diary(args.text, args.date)
        print(f"已记录：{path}")
    else:
        today = datetime.date.today()
        start = args.start or (today - datetime.timedelta(days=today.weekday())).isoformat()
        end = args.end or today.isoformat()
        path = gen_weekly(start, end)
        print(f"周报已生成：{path}")
