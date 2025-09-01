# app/email_gateway.py
import os
import ssl
import time
import email
import imaplib
import smtplib
import datetime
import threading
from email.message import EmailMessage
from email.header import decode_header, make_header
from dotenv import load_dotenv
from app.report_secretary import add_diary, gen_weekly
import threading

load_dotenv()

# ========== SMTP（发件，QQ: smtp.qq.com:465） ==========
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.qq.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")   # 你的邮箱地址
SMTP_PASS = os.getenv("SMTP_PASS", "")   # QQ邮箱“授权码”（不是登录密码）

# ========== IMAP（收件，QQ: imap.qq.com:993） ==========
IMAP_HOST = os.getenv("IMAP_HOST", "imap.qq.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER = os.getenv("IMAP_USER", "")   # 你的邮箱地址
IMAP_PASS = os.getenv("IMAP_PASS", "")   # QQ邮箱“授权码”

# 白名单（留空=不限制）
ALLOWED = set(
    x.strip().lower()
    for x in (os.getenv("MAIL_ALLOWED_SENDERS", "") or "").split(",")
    if x.strip()
)



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


def fetch_unseen_from(sender_email: str, mark_seen: bool = True, imap_timeout: int = 60, search_timeout: int = 30):
    """
    拉取“来自指定发件人”的未读邮件（只做 UNSEEN，本地过滤 From），返回列表：
    [{id, from, subject, body, date}]；若 mark_seen=True，会在读取后标记为已读。
    """
    out = []
    print(f"[{datetime.datetime.now():%F %T}] 连接 IMAP: {IMAP_HOST}:{IMAP_PORT}")
    M = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=imap_timeout)
    print(f"[{datetime.datetime.now():%F %T}] 登录 {IMAP_USER}")
    M.login(IMAP_USER, IMAP_PASS)
    print(f"[{datetime.datetime.now():%F %T}] 选择 INBOX")
    M.select("INBOX")
    try:
        M.socket().settimeout(imap_timeout)
    except Exception:
        pass

    print(f"[{datetime.datetime.now():%F %T}] 执行 UNSEEN 搜索（本地按 From 过滤：{sender_email}）")
    typ, data = _search_unseen_with_timeout(M, timeout_sec=search_timeout)
    if typ != "OK":
        raise RuntimeError(f"IMAP SEARCH 返回非 OK：{typ}")
    ids = data[0].split() if data and data[0] else []
    print(f"[{datetime.datetime.now():%F %T}] 未读邮件：{len(ids)}")

    # 先拉 From/Subject/Date 做本地过滤（不改变未读状态）
    target_ids = []
    for num in ids:
        typ, msg_data = M.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
        if typ != "OK" or not msg_data or not msg_data[0]:
            continue
        hdr = email.message_from_bytes(msg_data[0][1])
        frm  = email.utils.parseaddr(hdr.get("From", ""))[1].lower()
        if frm == (sender_email or "").lower():
            target_ids.append(num)

    print(f"[{datetime.datetime.now():%F %T}] 发件人匹配：{len(target_ids)}")

    # 取正文并可选标记已读
    for num in target_ids:
        typ, msg_data = M.fetch(num, "(RFC822)")
        if typ != "OK" or not msg_data or not msg_data[0]:
            print(f"警告 FETCH 非 OK：{typ}")
            continue
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)
        item = {
            "id": num.decode() if isinstance(num, bytes) else str(num),
            "from": email.utils.parseaddr(msg.get("From", ""))[1],
            "subject": _decode_subject(msg.get("Subject", "")),
            "date": msg.get("Date", ""),
            "body": _get_plain_text(msg),
        }
        out.append(item)

        if mark_seen:
            try:
                M.store(num, "+FLAGS", "\\Seen")
            except Exception:
                pass

    try: M.close()
    except Exception: pass
    M.logout()
    print(f"[{datetime.datetime.now():%F %T}] 读取完成：{len(out)} 封")
    return out


def send_mail(to_addr: str, subject: str, body: str):
    """对外导出的发信函数（内部调用 _send_mail）。"""
    return _send_mail(to_addr, subject, body)

def _send_mail(to_addr: str, subject: str, body: str):
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS):
        print("警告 SMTP 未配置完整，跳过发送。")
        return
    msg = EmailMessage()
    msg["From"] = SMTP_USER
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body, subtype="plain", charset="utf-8")
    ctx = ssl.create_default_context()
    try:
        srv = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx, timeout=60)
        srv.login(SMTP_USER, SMTP_PASS)
        srv.send_message(msg)
        srv.quit()
    except smtplib.SMTPResponseException as e:
        if getattr(e, "smtp_code", None) == -1 and getattr(e, "smtp_error", b"") == b"\x00\x00\x00":
            print(f"📨 已发送到 {to_addr}（忽略连接结束软错误）")
        else:
            print(f"错误 发送失败：{e.smtp_code} {e.smtp_error!r}")
            raise
    except Exception as e:
        print(f"错误 发送失败：{e}")
        raise


def _decode_subject(raw_subj: str) -> str:
    if not raw_subj:
        return ""
    try:
        return str(make_header(decode_header(raw_subj))).strip()
    except Exception:
        return raw_subj.strip()


def _parse_cmd(subject: str):
    """
    支持：
      SEC: 日记
      SEC: 日记 YYYY-MM-DD
      SEC: 周报
    兼容 Re:/Fwd: 前缀。
    对于非SEC命令的邮件，返回邮件内容供agent处理
    """
    if not subject:
        return ("", None)
    s = _decode_subject(subject)
    for prefix in ("Re:", "RE:", "Fwd:", "FW:"):
        if s.startswith(prefix):
            s = s[len(prefix):].strip()
    
    # 检查是否为SEC命令
    if s.startswith("SEC:"):
        s = s[4:].strip()
        if s.startswith("日记"):
            parts = s.split()
            return ("diary", parts[1] if len(parts) > 1 else None)
        if s.startswith("周报"):
            return ("weekly", None)
        return ("", None)
    
    # 非SEC命令邮件，返回邮件内容供agent处理
    return ("email_content", None)


def _week_range(today: datetime.date):
    monday = today - datetime.timedelta(days=today.weekday())
    sunday = monday + datetime.timedelta(days=6)
    return monday.isoformat(), sunday.isoformat()


def _get_plain_text(msg) -> str:
    try:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    return part.get_payload(decode=True).decode(
                        part.get_content_charset() or "utf-8", errors="ignore"
                    )
            return ""
        return msg.get_payload(decode=True).decode(
            msg.get_content_charset() or "utf-8", errors="ignore"
        )
    except Exception:
        return ""


def _allowed_subject_local(raw_subj: str) -> bool:
    # 允许所有邮件，不再限制主题前缀
    return True



def process_once(max_retries: int = 3, imap_timeout: int = 60, search_timeout: int = 30):
    """
    QQ/foxmail 最佳实践：
    - 仅 UNSEEN 搜索（快），白名单过滤（稳定）
    - socket/SEARCH 双超时
    - 指数退避重试
    """
    retry = 0
    while retry < max_retries:
        try:
            print(f"[{datetime.datetime.now():%F %T}] 连接 IMAP: {IMAP_HOST}:{IMAP_PORT}")
            M = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=imap_timeout)

            print(f"[{datetime.datetime.now():%F %T}] 登录 {IMAP_USER}")
            M.login(IMAP_USER, IMAP_PASS)

            print(f"[{datetime.datetime.now():%F %T}] 选择 INBOX")
            M.select("INBOX")

            try:
                M.socket().settimeout(imap_timeout)
            except Exception:
                pass

            print(f"[{datetime.datetime.now():%F %T}] 执行 UNSEEN 搜索")
            typ, data = _search_unseen_with_timeout(M, timeout_sec=search_timeout)
            if typ != "OK":
                raise RuntimeError(f"IMAP SEARCH 返回非 OK：{typ}")
            ids = data[0].split() if data and data[0] else []
            print(f"[{datetime.datetime.now():%F %T}] 未读邮件：{len(ids)}")

            filtered_ids = []
            for num in ids:
                try:
                    typ, msg_data = M.fetch(num, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])")
                    if typ != "OK" or not msg_data or not msg_data[0]:
                        continue
                    hdr = email.message_from_bytes(msg_data[0][1])
                    subj = hdr.get("Subject", "")
                    if _allowed_subject_local(subj):
                        filtered_ids.append(num)
                except Exception as e:
                    print(f"警告 获取邮件 {num} 头信息失败: {e}")
                    continue

            print(f"[{datetime.datetime.now():%F %T}] 白名单匹配：{len(filtered_ids)}")

            handled = 0
            for num in filtered_ids:
                typ, msg_data = M.fetch(num, "(RFC822)")
                if typ != "OK" or not msg_data or not msg_data[0]:
                    print(f"警告 FETCH 非 OK：{typ}")
                    continue
                raw = msg_data[0][1]
                m = email.message_from_bytes(raw)

                from_addr = email.utils.parseaddr(m.get("From"))[1].lower()
                if ALLOWED and from_addr not in ALLOWED:
                    print(f"跳过 非白名单发件人：{from_addr}")
                    try: M.store(num, "+FLAGS", "\\Seen")
                    except Exception: pass
                    continue

                subject = m.get("Subject", "")
                body = _get_plain_text(m)
                cmd, date_str = _parse_cmd(subject)

                try:
                    if cmd == "diary":
                        path = add_diary(body, date_str)
                        _send_mail(from_addr, f"成功 日记已记录 {date_str or ''}".strip(), f"已追加到：{path}")
                        handled += 1
                    elif cmd == "weekly":
                        today = datetime.date.today()
                        start, end = _week_range(today)
                        path = gen_weekly(start, end)
                        content = open(path, "r", encoding="utf-8").read()
                        _send_mail(from_addr, f"成功 周报已生成 {start}~{end}", content)
                        handled += 1
                    elif cmd == "email_content":
                        # 非SEC命令邮件，返回邮件信息供agent处理
                        handled += 1
                    else:
                        # 其他情况，不处理
                        pass
                except Exception as e:
                    _send_mail(from_addr, "错误 处理失败", str(e))

                try:
                    M.store(num, "+FLAGS", "\\Seen")
                except Exception:
                    pass

            # 返回处理的新邮件信息（只返回白名单内的邮件）
            processed_emails = []
            for num in filtered_ids:
                try:
                    typ, msg_data = M.fetch(num, "(RFC822)")
                    if typ != "OK" or not msg_data or not msg_data[0]:
                        continue
                    raw = msg_data[0][1]
                    m = email.message_from_bytes(raw)
                    
                    from_addr = email.utils.parseaddr(m.get("From"))[1].lower()
                    # 只返回白名单内的邮件
                    if ALLOWED and from_addr not in ALLOWED:
                        print(f"跳过非白名单发件人: {from_addr}")
                        continue
                    
                    subject = m.get("Subject", "")
                    body = _get_plain_text(m)
                    
                    processed_emails.append({
                        'from': from_addr,
                        'subject': subject,
                        'body': body,
                        'timestamp': datetime.datetime.now().isoformat()
                    })
                    print(f"将处理邮件: 发件人={from_addr}, 主题={subject}")
                except Exception:
                    continue
            
            try: M.close()
            except Exception: pass
            M.logout()
            print(f"[{datetime.datetime.now():%F %T}] 处理完成：{handled}/{len(filtered_ids)}，原未读 {len(ids)}")
            print(f"process_once返回 {len(processed_emails)} 封邮件")
            return processed_emails
        except Exception as e:
            retry += 1
            print(f"[{datetime.datetime.now():%F %T}] IMAP 失败（{retry}/{max_retries}）：{e}")
            if retry < max_retries:
                delay = 2 ** retry
                print(f"等待 {delay}s 后重试…")
                time.sleep(delay)
            else:
                print(f"[{datetime.datetime.now():%F %T}] 达到最大重试次数，退出。")
                return []  # 出错时返回空列表


if __name__ == "__main__":
    process_once()
