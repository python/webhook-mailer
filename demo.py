import asyncio
import os

from email.mime.text import MIMEText

import aiosmtplib

loop = asyncio.get_event_loop()
smtp = aiosmtplib.SMTP(hostname=os.environ['SMTP_HOSTNAME'], port=os.environ['SMTP_PORT'], loop=loop, use_tls=False)
loop.run_until_complete(smtp.connect())
loop.run_until_complete(smtp.login(os.environ['SMTP_USERNAME'], os.environ['SMTP_PASSWORD']))

message = MIMEText('Sent via aiosmtplib')
message['From'] = os.environ['SENDER_EMAIL']
message['To'] = os.environ['RECIPIENT_EMAIL']
message['Subject'] = 'Hello World!'

loop.run_until_complete(smtp.send_message(message))
