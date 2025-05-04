import smtplib
import mimetypes
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email(email, subject, text):
    addr_from = "amdemidov2@yandex.ru"
    password = "hzpkyvzhbxnwsvuz"

    msg = MIMEMultipart()
    msg["From"] = addr_from
    msg["To"] = email
    msg['Subject'] = subject

    body = text
    msg.attach(MIMEText(body, "plain"))

    server = smtplib.SMTP_SSL("smtp.yandex.ru", 465)
    server.login(addr_from, password)

    server.send_message(msg)
    server.quit()

    return True