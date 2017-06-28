import json
import pathlib
import unittest
import unittest.mock

import aiohttp
import aiosmtplib
import aiosmtplib.response

from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

import mailer


def get_payload(path):
    test_data = pathlib.Path(path)
    with test_data.open() as f:
        return json.loads(f.read())

payload = get_payload('test_data.json')
payload_without_commits = get_payload('test_data_empty_commits.json')
diff = """\
diff --git a/.gitignore b/.gitignore
index c2b4fc703f7..e0d0685fa7d 100644
--- a/.gitignore
+++ b/.gitignore
@@ -93,3 +93,4 @@ htmlcov/
 Tools/msi/obj
 Tools/ssl/amd64
 Tools/ssl/win32
+foo
"""


class FakeConfig(mailer.Config):

    @property
    def sender(self):
        return 'sender@sender.com'

    @property
    def recipient(self):
        return 'recipient@recipient.com'


class FakeRequest:

    def __init__(self, payload={}, content_type='application/json'):
        self.content_type = content_type
        self._payload = payload

    async def json(self):
        return self._payload


class FakeSMTP(aiosmtplib.SMTP):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sent_mails = []

    async def connect(self, *args, **kwargs):
        return aiosmtplib.response.SMTPResponse(100, 'ok')

    async def send_message(self, message, sender=None,
            recipients=None,
            mail_options=None, rcpt_options=None,
            timeout=None):
        self.sent_mails.append(message)
        return {}, 'Ok'


class MailerTestCase(AioHTTPTestCase):

    async def get_application(self, loop):
        config = FakeConfig()
        return mailer.application(loop=loop, config=config)

    @unittest_run_loop
    async def test_wrong_content_type(self):
        # TODO: Find a way to get rid of this boilerplate code.
        config = FakeConfig()
        SMTP = unittest.mock.create_autospec(aiosmtplib.SMTP)
        smtp = SMTP(hostname=config.smtp_hostname, port=config.smtp_port, loop=self.loop)
        ClientSession = unittest.mock.create_autospec(aiohttp.ClientSession)
        client = ClientSession(loop=self.loop)
        request = FakeRequest(content_type='application/octet-stream')
        event = mailer.PushEvent(config, client, smtp, request)
        self.assertEqual(event.config.http_port, 8585)
        with self.assertRaises(mailer.ResponseExit) as cm:
            await event.process()
        self.assertEqual(str(cm.exception), 'can only accept application/json, not application/octet-stream')

    @unittest_run_loop
    async def test_empty_commits(self):
        config = FakeConfig()
        SMTP = unittest.mock.create_autospec(aiosmtplib.SMTP)
        smtp = SMTP(hostname=config.smtp_hostname, port=config.smtp_port, loop=self.loop)
        ClientSession = unittest.mock.create_autospec(aiohttp.ClientSession)
        client = ClientSession(loop=self.loop)
        request = FakeRequest(payload_without_commits)
        event = mailer.PushEvent(config, client, smtp, request)
        with self.assertRaises(mailer.ResponseExit) as cm:
            await event.process()
        self.assertEqual(str(cm.exception), 'There is no commit to be processed.')

    @unittest_run_loop
    async def test_invalid_branch_name(self):
        config = FakeConfig()
        SMTP = unittest.mock.create_autospec(aiosmtplib.SMTP)
        smtp = SMTP(hostname=config.smtp_hostname, port=config.smtp_port, loop=self.loop)
        ClientSession = unittest.mock.create_autospec(aiohttp.ClientSession)
        client = ClientSession(loop=self.loop)
        local_payload = payload.copy()
        local_payload['ref'] = 'ref/head/2.6'
        request = FakeRequest(local_payload)
        event = mailer.PushEvent(config, client, smtp, request)
        branch_name = local_payload['ref']
        self.assertNotIn(branch_name, config.allowed_branches)
        with self.assertRaises(mailer.ResponseExit) as cm:
            await event.process()
        self.assertEqual(str(cm.exception), 'Invalid branch name.')

    @unittest_run_loop
    async def test_send_email(self):
        config = FakeConfig()
        smtp = FakeSMTP(hostname=config.smtp_hostname, port=config.smtp_port, loop=self.loop)
        # TODO: Mock Transport so we can run tests without needing internet connection
        client_session = aiohttp.ClientSession(loop=self.loop)
        request = FakeRequest(payload)
        async with client_session as client:
            event = mailer.PushEvent(config, client, smtp, request)
            result = await event.process()
        self.assertEqual(result, 'Ok')
        self.assertEqual(len(smtp.sent_mails), 1)
        mail = smtp.sent_mails[0]
        self.assertEqual(mail['From'], 'Berker Peksag <sender@sender.com>')
        self.assertEqual(mail['To'], 'recipient@recipient.com')
        self.assertEqual(mail['Subject'], 'Update .gitignore')
        self.assertNotIn('(cherry picked from commit 9d9ed0e5cceef45fd63dc1f7b3fe6e695da16e83)',mail['Subject'])
        body = mail.get_body().as_string()
        # TODO: We probably need a FakeDiff object to avoid making HTTP requests.
        self.assertIn(diff, body)
        self.assertIn('author: cbiggles <berker.peksag+cbiggles@gmail.com>', body)
        self.assertIn('committer: Berker Peksag <berker.peksag@gmail.com>', body)


class ConfigTestCase(unittest.TestCase):

    def test_required_env_variables(self):
        config = mailer.Config()
        with self.assertRaises(ValueError) as cm:
            config.sender
        self.assertEqual(str(cm.exception), 'Set SENDER_EMAIL environment variable.')
        with self.assertRaises(ValueError) as cm:
            config.recipient
        self.assertEqual(str(cm.exception), 'Set RECIPIENT_EMAIL environment variable.')

if __name__ == '__main__':
    unittest.main()
