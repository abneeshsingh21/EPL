"""
EPL Email Package - Python Backend
Email sending: SMTP, HTML emails, attachments, templates, bulk send.
"""

import mimetypes as _mimetypes
import os as _os
import re as _re
import smtplib as _smtplib
import string as _string
from email import encoders as _encoders
from email.mime.base import MIMEBase as _MIMEBase
from email.mime.multipart import MIMEMultipart as _MIMEMultipart
from email.mime.text import MIMEText as _MIMEText

# ═══════════════════════════════════════════════════════════
#  SMTP Connection
# ═══════════════════════════════════════════════════════════


def create_mailer(host, port, username, password):
    return {
        '_type': 'mailer',
        'host': host,
        'port': int(port),
        'username': username,
        'password': password,
        'ssl': False,
    }


def create_mailer_ssl(host, port, username, password):
    return {
        '_type': 'mailer',
        'host': host,
        'port': int(port),
        'username': username,
        'password': password,
        'ssl': True,
    }


def _connect(mailer):
    if mailer['ssl']:
        server = _smtplib.SMTP_SSL(mailer['host'], mailer['port'], timeout=30)
    else:
        server = _smtplib.SMTP(mailer['host'], mailer['port'], timeout=30)
        server.starttls()
    server.login(mailer['username'], mailer['password'])
    return server


# ═══════════════════════════════════════════════════════════
#  Sending Emails
# ═══════════════════════════════════════════════════════════


def send_plain(mailer, to_addr, subject, body):
    msg = _MIMEText(body, 'plain')
    msg['Subject'] = subject
    msg['From'] = mailer['username']
    msg['To'] = to_addr
    server = _connect(mailer)
    try:
        server.sendmail(mailer['username'], [to_addr], msg.as_string())
        return True
    finally:
        server.quit()


def send_html(mailer, to_addr, subject, html_body):
    msg = _MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = mailer['username']
    msg['To'] = to_addr
    msg.attach(_MIMEText(html_body, 'html'))
    server = _connect(mailer)
    try:
        server.sendmail(mailer['username'], [to_addr], msg.as_string())
        return True
    finally:
        server.quit()


def send_with_attachment(mailer, to_addr, subject, body, file_path):
    msg = _MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = mailer['username']
    msg['To'] = to_addr
    msg.attach(_MIMEText(body, 'plain'))
    mime_type, _ = _mimetypes.guess_type(file_path)
    main_type, sub_type = (mime_type or 'application/octet-stream').split('/', 1)
    with open(file_path, 'rb') as f:
        attachment = _MIMEBase(main_type, sub_type)
        attachment.set_payload(f.read())
    _encoders.encode_base64(attachment)
    attachment.add_header(
        'Content-Disposition', 'attachment', filename=_os.path.basename(file_path)
    )
    msg.attach(attachment)
    server = _connect(mailer)
    try:
        server.sendmail(mailer['username'], [to_addr], msg.as_string())
        return True
    finally:
        server.quit()


def send_bulk(mailer, recipients, subject, body):
    if isinstance(recipients, str):
        recipients = [r.strip() for r in recipients.split(',')]
    msg = _MIMEText(body, 'plain')
    msg['Subject'] = subject
    msg['From'] = mailer['username']
    server = _connect(mailer)
    try:
        sent = 0
        for addr in recipients:
            try:
                del msg['To']
                msg['To'] = addr
                server.sendmail(mailer['username'], [addr], msg.as_string())
                sent += 1
            except Exception:
                continue  # best-effort bulk send; returned `sent` count reflects skips
        return sent
    finally:
        server.quit()


# ═══════════════════════════════════════════════════════════
#  Templates
# ═══════════════════════════════════════════════════════════


def create_template(template_string):
    return {'_type': 'template', 'template': template_string}


def render_template(template, variables):
    tmpl = template['template'] if isinstance(template, dict) else template
    t = _string.Template(tmpl)
    if isinstance(variables, dict):
        return t.safe_substitute(variables)
    return tmpl


def send_templated(mailer, to_addr, subject, template, variables):
    body = render_template(template, variables)
    return send_plain(mailer, to_addr, subject, body)


# ═══════════════════════════════════════════════════════════
#  Message Builder
# ═══════════════════════════════════════════════════════════


def create_message(from_addr, to_addr, subject):
    return {
        '_type': 'message',
        'from': from_addr,
        'to': [to_addr] if isinstance(to_addr, str) else to_addr,
        'subject': subject,
        'body': '',
        'html': None,
        'attachments': [],
        'cc': [],
        'bcc': [],
        'reply_to': None,
    }


def set_body(msg, body_content):
    msg['body'] = body_content
    return msg


def set_html(msg, html_content):
    msg['html'] = html_content
    return msg


def add_attachment(msg, file_path):
    msg['attachments'].append(file_path)
    return msg


def add_cc(msg, cc_addr):
    msg['cc'].append(cc_addr)
    return msg


def add_bcc(msg, bcc_addr):
    msg['bcc'].append(bcc_addr)
    return msg


def set_reply_to(msg, reply_addr):
    msg['reply_to'] = reply_addr
    return msg


def send_message(mailer, msg):
    mime_msg = _MIMEMultipart()
    mime_msg['Subject'] = msg['subject']
    mime_msg['From'] = msg['from']
    mime_msg['To'] = ', '.join(msg['to'])
    if msg['cc']:
        mime_msg['Cc'] = ', '.join(msg['cc'])
    if msg['reply_to']:
        mime_msg['Reply-To'] = msg['reply_to']
    if msg['html']:
        mime_msg.attach(_MIMEText(msg['html'], 'html'))
    else:
        mime_msg.attach(_MIMEText(msg['body'], 'plain'))
    for fp in msg['attachments']:
        with open(fp, 'rb') as f:
            att = _MIMEBase('application', 'octet-stream')
            att.set_payload(f.read())
        _encoders.encode_base64(att)
        att.add_header('Content-Disposition', 'attachment', filename=_os.path.basename(fp))
        mime_msg.attach(att)
    all_recipients = msg['to'] + msg['cc'] + msg['bcc']
    server = _connect(mailer)
    try:
        server.sendmail(msg['from'], all_recipients, mime_msg.as_string())
        return True
    finally:
        server.quit()


# ═══════════════════════════════════════════════════════════
#  Utilities
# ═══════════════════════════════════════════════════════════

_EMAIL_RE = _re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


def validate_email(addr):
    return bool(_EMAIL_RE.match(str(addr)))


def extract_domain(addr):
    parts = str(addr).split('@')
    return parts[1] if len(parts) == 2 else ''
