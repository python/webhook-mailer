import json

import aiohttp
import aiosmtplib
import aiosmtplib.response

import mailer


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

data_with_commits = {
    "ref": "refs/heads/master",
    "commits": [
        {
            "id": "2d420b342509e6c2b597af82ea74c4cbb13e2abd",
            "message": "Update .gitignore\n(cherry picked from commit 9d9ed0e5cceef45fd63dc1f7b3fe6e695da16e83)",
            "timestamp": "2017-02-08T15:37:50+03:00",
            "url": "https://github.com/fayton/cpython/commit/2d420b342509e6c2b597af82ea74c4cbb13e2abd",
            "author": {"name": "cbiggles", "email": "berker.peksag+cbiggles@gmail.com", "username": "cbiggles"},
            "committer": {"name": "Berker Peksag", "email": "berker.peksag@gmail.com", "username": "berkerpeksag"},
            "added": [],
            "removed": [],
            "modified": [".gitignore"]
        }
    ],
}


class FakeSMTP(aiosmtplib.SMTP):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sent_mails = []

    async def connect(self, *args, **kwargs):
        return aiosmtplib.response.SMTPResponse(100, 'ok')

    async def send_message(self, message, sender=None, recipients=None,
                           mail_options=None, rcpt_options=None, timeout=None):
        self.sent_mails.append(message)
        return {}, 'Ok'


async def test_wrong_content_type(test_client, loop):
    smtp = FakeSMTP(hostname='localhost', port=1025, loop=loop)
    app = mailer.application(loop=loop, smtp=smtp)
    client = await test_client(app)
    resp = await client.post('/', headers=dict(content_type='application/octet-stream'))
    assert resp.status == 415
    text = await resp.text()
    assert text == 'can only accept application/json, not application/octet-stream'


async def test_empty_commits(test_client, loop):
    data = data_with_commits.copy()
    del data['commits']
    smtp = FakeSMTP(hostname='localhost', port=1025, loop=loop)
    app = mailer.application(loop=loop, smtp=smtp)
    client = await test_client(app)
    resp = await client.post('/', headers={'content-type': 'application/json'}, data=json.dumps(data))
    assert resp.status == 204
    text = await resp.text()
    assert not text


async def test_invalid_branch_name(test_client, loop):
    data = data_with_commits.copy()
    data['ref'] = 'refs/heads/invalid'
    smtp = FakeSMTP(hostname='localhost', port=1025, loop=loop)
    app = mailer.application(loop=loop, smtp=smtp)
    client = await test_client(app)
    resp = await client.post('/', headers={'content-type': 'application/json'}, data=json.dumps(data))
    assert resp.status == 204
    text = await resp.text()
    assert not text


async def test_send_email(test_client, loop):
    smtp = FakeSMTP(hostname='localhost', port=1025, loop=loop)
    app = mailer.application(loop=loop, smtp=smtp)
    client = await test_client(app)
    resp = await client.post('/', headers={'content-type': 'application/json'}, data=json.dumps(data_with_commits))
    assert resp.status == 200
    text = await resp.text()
    assert text == 'Ok'
    assert len(smtp.sent_mails) == 1
    mail = smtp.sent_mails[0]
    assert mail['From'] == 'Berker Peksag <sender@example.com>'
    assert mail['To'] == 'recipient@example.com'
    assert mail['Subject'] == 'Update .gitignore'
    assert '(cherry picked from commit 9d9ed0e5cceef45fd63dc1f7b3fe6e695da16e83)' not in mail['Subject']
    body = mail.get_body().as_string()
    # TODO: We probably need a FakeDiff object to avoid making HTTP requests.
    assert diff in body
