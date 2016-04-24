import sys, datetime
import os, sys, datetime, smtplib, random
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import utils

template = """\
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head></head>
<body>{content}</body></html>"""

output = None

html_escape_table = { "&": "&amp;", '"': "&quot;", "'": "&apos;", ">": "&gt;", "<": "&lt;", }
def html_escape(text):
     return "".join(html_escape_table.get(c,c) for c in text)

def init():
    global output
    output = ""

def log_name(name):
    log_text("Name: {0}".format(name))
    log_html("<div style='margin: 3px; font-size: 15pt; font-weight: bold; color: blue'>{0}</div>".format(name))

def log_task(name):
    log_text("Task: {0}".format(name))
    log_html("<div style='margin: 3px; font-size: 13pt; font-weight: bold; color: green'>Task: {0}</div>".format(name))
    
def log_command(cmd):
    log_html("<div><pre style='margin: 0; padding: 0'><b>&gt; {0}</b></pre></div>".format(html_escape(cmd)))
    log_text(cmd)

def get_html():
    global output
    return template.format(content=output)

def log_warn(txt):
    log_text("[WARN] {0}".format(txt))
    log_html(html_escape(txt) + "\n")

def log_msg(txt):
    log_text(txt)
    log_html("<div style='afont-size: 9pt; margin: 0px; color: #0000ff; font-style: aitalic; font-family: monospace'>{0}</div>".format(html_escape(txt)))

def log_state(txt):
    log_text(txt)
    log_html("<div style='afont-size: 9pt; font-family: monospace'>@ {0}</div>".format(html_escape(txt)))

def log(txt):
    log_text(txt)
    log_html(html_escape(txt))

def log_text(txt):
    sys.stdout.write("{0}\033[0m\n".format(txt))

def log_html(html):
    global output
    html = html.replace("\n", "<br/>").replace("  ", "&nbsp;&nbsp;")
    output += html + "\n"

def send(config, code):
    global output
    now = datetime.datetime.now()
    dateStr = now.strftime("%Y-%m-%d %H:%M")

    name = config['name']
    if code == 0:
        subject = 'backup-rotate: {0} {1} SUCCEED'.format(name, dateStr)
    else:
        subject = 'backup-rotate: {0} {1} FAILED'.format(name, dateStr)

    mail_recipients = config['mail']['recipients']
    mail_from = config['mail']['from']
    mail_smtp_host = config['mail']['smtp_host']
    mail_smtp_port = config['mail'].get('smtp_port', 25)
    mail_smtp_user = config['mail'].get('smtp_user')
    mail_smtp_pass = config['mail'].get('smtp_pass')

    recps = mail_recipients.split(',')

    msg = MIMEMultipart('alternative')
    msg.attach(MIMEText(get_html(), 'html'))

    msg['Subject'] = subject
    msg['From'] = mail_from
    msg['To'] = ",".join(recps)

    s = smtplib.SMTP(mail_smtp_host, port=mail_smtp_port)
    if mail_smtp_user is not None and mail_smtp_pass is not None:
        s.login(mail_smtp_user, mail_smtp_pass)
    s.sendmail(msg['From'], recps, msg.as_string())
    s.quit()

