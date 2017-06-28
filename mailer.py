# Design of the application is borrowed from python/the-knights-who-say-ni.

import asyncio
import email.message
import email.utils
import http
import http.client
import os
import traceback
import sys

import aiohttp
import aiohttp.web
import aiosmtplib


class ResponseExit(Exception):

    def __init__(self, status=None, text=None) -> None:
        super().__init__(text)
        self.response = aiohttp.web.Response(status=status.value, text=text)


class Config:

    allowed_branches = ['2.7', '3.5', '3.6', 'master']

    @property
    def sender(self):
        sender = os.environ.get('SENDER_EMAIL')
        if sender is None:
            raise ValueError('Set SENDER_EMAIL environment variable.')
        return sender

    @property
    def recipient(self):
        recipient = os.environ.get('RECIPIENT_EMAIL')
        if recipient is None:
            raise ValueError('Set RECIPIENT_EMAIL environment variable.')
        return recipient

    @property
    def smtp_hostname(self):
        return os.environ.get('SMTP_HOSTNAME', 'localhost')

    @property
    def smtp_port(self):
        return int(os.environ.get('SMTP_PORT', 1025))

    @property
    def http_port(self):
        return int(os.environ.get('HTTP_PORT', 8585))


class Diff:

    def __init__(self, client):
        self.client = client
        self.commit = None

    def set_commit_data(self, commit):
        self.commit = commit

    def get_diff_stat(self):
        files = {
            'A': self.commit['added'],
            'D': self.commit['removed'],
            'M': self.commit['modified'],
        }
        result = []
        for key, file_list in files.items():
            if file_list:
                result.append('\n'.join(f'{key} {f}' for f in file_list))
        return '\n'.join(result)

    async def fetch_diff(self, url):
        async with self.client.get(url) as response:
            if response.status >= 300:
                msg = f'unexpected response for {response.url!r}: {response.status}'
                raise http.client.HTTPException(msg)
            return (await response.text())

    async def get_output(self):
        stat = self.get_diff_stat()
        diff = await self.fetch_diff(self.commit['url'] + '.diff')
        return stat, diff


class Email:

    def __init__(self, smtp, config, payload):
        self.smtp = smtp
        self.config = config
        self.payload = payload
        self.commit = payload['commits'][0]

    def build_message(self):
        msg = email.message.EmailMessage()
        # TODO: Use committer name if it's not GitHub as sender name
        msg['From'] = email.utils.formataddr((self.commit['committer']['name'], self.config.sender))
        msg['To'] = self.config.recipient
        msg['Subject'] = self.commit['message'].split('\n')[0]
        msg.set_content(self.build_message_body())
        return msg

    def build_message_body(self):
        commit = self.commit
        branch = self.payload['ref']
        custom_data = self.payload['_custom_data']
        template = f"""\
{commit['url']}
commit: {commit['id']}
branch: {branch}
author: {commit['author']['name']} <{commit['author']['email']}>
committer: {commit['committer']['name']} <{commit['committer']['email']}>
date: {commit['timestamp']}
summary:

{commit['message']}

files:
{custom_data['diff_stat']}

{custom_data['unified_diff']}
        """
        return template

    async def send_email(self):
        message = self.build_message()
        async with self.smtp as smtp:
            await smtp.connect()
            return (await smtp.send_message(message))


class PushEvent:

    def __init__(self, config, client, smtp, request):
        self.config = config
        self.client = client
        self.smtp = smtp
        self.request = request
        # TODO: This is here to improve testability for now. Find a better solution.
        self.diff = Diff(self.client)

    async def process(self):
        if self.request.content_type != 'application/json':
            msg = f'can only accept application/json, not {self.request.content_type}'
            raise ResponseExit(status=http.HTTPStatus.UNSUPPORTED_MEDIA_TYPE, text=msg)
        payload = await self.request.json()
        if len(payload['commits']) == 0:
            raise ResponseExit(status=http.HTTPStatus.NO_CONTENT, text='There is no commit to be processed.')
        branch_name = payload['ref'].split('/').pop()
        if branch_name not in self.config.allowed_branches:
            raise ResponseExit(status=http.HTTPStatus.NO_CONTENT, text='Invalid branch name.')
        # Since we use the 'squash and merge' button, there will
        # always be single commit.
        commit = payload['commits'][0]
        self.diff.set_commit_data(commit)
        diff_stat, unified_diff = await self.diff.get_output()
        custom_data = {
            '_custom_data': {
                'diff_stat': diff_stat,
                'unified_diff': unified_diff,
            }
        }
        # Yes, this is a hack.
        payload.update(custom_data)
        email = Email(self.smtp, self.config, payload)
        _, message = await email.send_email()
        return message


def create_handler(create_client, smtp_client, config):
    async def handler(request):
        async with create_client() as client, smtp_client() as smtp:
            try:
                result = await PushEvent(config, client, smtp, request).process()
                return aiohttp.web.Response(status=http.HTTPStatus.OK, text=result)
            except ResponseExit as exc:
                return exc.response
            except Exception as exc:
                traceback.print_exception(
                    type(exc), exc, exc.__traceback__, file=sys.stderr
                )
                return aiohttp.web.Response(status=http.HTTPStatus.INTERNAL_SERVER_ERROR)
    return handler


def application(loop, config):
    app = aiohttp.web.Application(loop=loop)
    app.router.add_post('/', create_handler(
        lambda: aiohttp.ClientSession(loop=loop),
        lambda: aiosmtplib.SMTP(
            hostname=config.smtp_hostname, port=config.smtp_port, loop=loop,
        ),
        config,
    ))
    return app

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    config = Config()
    app = application(loop, config)
    aiohttp.web.run_app(app, port=config.http_port)
