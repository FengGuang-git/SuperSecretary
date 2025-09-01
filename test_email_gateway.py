# test_email_receive.py
import os, email, imaplib, datetime, threading, ssl
from email.header import decode_header, make_header
from dotenv import load_dotenv

load_dotenv()

IMAP_HOST = os.getenv("IMAP_HOST", "imap.qq.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER = os.getenv("IMAP_USER", "")
IMAP_PASS = os.getenv("IMAP_PASS", "")

IMAP_TIMEOUT = 60
SEARCH_TIMEOUT = 30

def _now():
    return datetime.datetime.now().strftime("%F %T")

def _decode_subject(raw_subj: str) -> str:
    if not raw_subj:
        return ""
    try:
        return str(make_header(decode_header(raw_subj))).strip()
    except Exception:
        return raw_subj.strip()

def _allowed_subject_local(raw_subj: str) -> bool:
    # 允许所有主题，不再限制主题前缀
    return True

def _search_unseen_with_timeout(M: imaplib.IMAP4_SSL, timeout_sec: int = 30):
    """只做 UNSEEN；线程级硬超时，避免卡死。"""
    result = {"typ": None, "data": None, "err": None}
    def _do():
        try:
            result["typ"], result["data"] = M.search(None, 'UNSEEN')
        except Exception as e:
            result["err"] = e
    t = threading.Thread(target=_do, daemon=True)
    t.start()
    t.join(timeout_sec)
    if t.is_alive():
        raise TimeoutError("IMAP SEARCH(UNSEEN) 超时")
    if result["err"]:
        raise result["err"]
    return result["typ"], result["data"]

def main():
    print(f"[{_now()}] 连接 IMAP: {IMAP_HOST}:{IMAP_PORT}")
    M = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=IMAP_TIMEOUT)
    print(f"[{_now()}] 登录 {IMAP_USER}")
    M.login(IMAP_USER, IMAP_PASS)
    print(f"[{_now()}] 选择 INBOX")
    M.select("INBOX")

    # socket 级超时（部分实现只对收发生效）
    try:
        M.socket().settimeout(IMAP_TIMEOUT)
    except Exception:
        pass

    print(f"[{_now()}] 执行 UNSEEN 搜索")
    typ, data = _search_unseen_with_timeout(M, timeout_sec=SEARCH_TIMEOUT)
    if typ != "OK":
        raise RuntimeError(f"IMAP SEARCH 返回非 OK：{typ}")
    ids = data[0].split() if data and data[0] else []
    print(f"[{_now()}] 未读邮件：{len(ids)}")

    # 拉主题头做本地过滤（不改变未读状态）
    filtered = []
    for num in ids:
        typ, msg_data = M.fetch(num, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])")
        if typ != "OK" or not msg_data or not msg_data[0]:
            continue
        hdr = email.message_from_bytes(msg_data[0][1])
        subj = hdr.get("Subject", "")
        frm  = hdr.get("From", "")
        dt   = hdr.get("Date", "")
        if _allowed_subject_local(subj):
            filtered.append((num, _decode_subject(subj), frm, dt))

    print(f"[{_now()}] 邮件匹配：{len(filtered)}")
    for num, subj, frm, dt in filtered:
        print(f"  - id={num.decode() if isinstance(num, bytes) else num} | {subj} | {frm} | {dt}")

    try: M.close()
    except Exception: pass
    M.logout()
    print(f"[{_now()}] 完成。")

if __name__ == "__main__":
    main()
