#!/usr/bin/env python3
"""Send an email with the Resend Python SDK.

Install:
    pip install resend

Run:
    RESEND_API_KEY=re_xxx python send_email.py
"""

import os

import resend

resend.api_key = os.environ["RESEND_API_KEY"]

params: resend.Emails.SendParams = {
    "from": "hey@infinitywave.online",
    "to": ["allistera@gmail.com"],
    "subject": "Hello from Resend",
    "html": "<p>This is a test email sent with <strong>Resend</strong>.</p>",
}

email = resend.Emails.send(params)
print(email)
