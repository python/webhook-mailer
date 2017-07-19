import json

import aiohttp
import aiosmtplib
import aiosmtplib.response
import pytest

from aiohttp.helpers import sentinel
from aiohttp import streams
from aiohttp.test_utils import make_mocked_request

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

    async def ehlo(self):
        return aiosmtplib.response.SMTPResponse(250, 'EHLO')

    async def login(self, username, password):
        return aiosmtplib.response.SMTPResponse(235, 'AUTH')

    async def connect(self, *args, **kwargs):
        return aiosmtplib.response.SMTPResponse(100, 'ok')

    async def send_message(self, message, sender=None, recipients=None,
                           mail_options=None, rcpt_options=None, timeout=None):
        self.sent_mails.append(message)
        return {}, 'Ok'


def make_request(method, path, *, loop=None, headers=sentinel, data=None):
    if headers is sentinel:
        headers = {'Content-Type': 'application/json'}
    elif 'Content-Type' not in headers:
        headers['Content-Type'] = 'application/json'
    if data is not None:
        data = json.dumps(data).encode()
        payload = streams.StreamReader(loop=loop)
        payload.feed_data(data)
        payload.feed_eof()
        headers.update({'Content-Length': str(len(data))})
    else:
        payload = sentinel
    return make_mocked_request(method, path, headers=headers, payload=payload)


async def test_wrong_content_type(loop):
    smtp = FakeSMTP(hostname='localhost', port=1025, loop=loop)
    client = aiohttp.ClientSession(loop=loop)
    request = make_request('POST', '/', headers={'content-type': 'application/octet-stream'})
    event = mailer.PushEvent(client, smtp, request)
    with pytest.raises(mailer.ResponseExit) as exc:
        await event.process()
    assert str(exc.value) == 'can only accept application/json, not application/octet-stream'


async def test_empty_commits(loop):
    data = data_with_commits.copy()
    del data['commits']
    smtp = FakeSMTP(hostname='localhost', port=1025, loop=loop)
    client = aiohttp.ClientSession(loop=loop)
    request = make_request('POST', '/', data=data, loop=loop)
    event = mailer.PushEvent(client, smtp, request)
    with pytest.raises(mailer.ResponseExit) as exc:
        await event.process()
    assert str(exc.value) == 'There is no commit to be processed.'


async def test_invalid_branch_name(loop):
    data = data_with_commits.copy()
    data['ref'] = 'refs/heads/invalid'
    smtp = FakeSMTP(hostname='localhost', port=1025, loop=loop)
    client = aiohttp.ClientSession(loop=loop)
    request = make_request('POST', '/', data=data, loop=loop)
    event = mailer.PushEvent(client, smtp, request)
    with pytest.raises(mailer.ResponseExit) as exc:
        await event.process()
    assert str(exc.value) == 'Invalid branch name.'


async def test_send_email(loop):
    smtp = FakeSMTP(hostname='localhost', port=1025, loop=loop)
    client = aiohttp.ClientSession(loop=loop)
    request = make_request('POST', '/', data=data_with_commits, loop=loop)
    event = mailer.PushEvent(client, smtp, request)
    resp = await event.process()
    assert resp == 'Ok'
    assert len(smtp.sent_mails) == 1
    mail = smtp.sent_mails[0]
    assert mail['From'] == 'Berker Peksag <sender@example.com>'
    assert mail['To'] == 'recipient@example.com'
    assert mail['Subject'] == 'Update .gitignore'
    assert '(cherry picked from commit 9d9ed0e5cceef45fd63dc1f7b3fe6e695da16e83)' not in mail['Subject']
    body = mail.get_body().as_string()
    # TODO: We probably need a FakeDiff object to avoid making HTTP requests.
    assert diff in body
