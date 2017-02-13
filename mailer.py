# Design of the application is borrowed from python/the-knights-who-say-ni.

import asyncio
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
        super().__init__()
        self.response = aiohttp.web.Response(status=status.value, text=text)


class Config:

    allowed_branches = ['2.7', '3.5', '3.6', 'master']

    @property
    def sender(self):
        return os.environ.get('SENDER_EMAIL', 'mail@example.com')

    @property
    def recipient(self):
        return os.environ.get('RECIPIENT_EMAIL', 'mail@example.com')

    @property
    def smtp_hostname(self):
        return os.environ.get('SMTP_HOSTNAME', 'localhost')

    @property
    def smtp_port(self):
        return int(os.environ.get('SMTP_PORT', 1025))

    @property
    def http_port(self):
        return int(os.environ.get('PORT', 8585))


class Email:

    def __init__(self, smtp, client, payload):
        self.smtp = smtp
        self.client = client
        self.payload = payload
        self.commit = payload['commits'][0]

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

    async def get_diff(self, url):
        async with self.client.get(url) as response:
            if response.status >= 300:
                msg = f'unexpected response for {response.url!r}: {response.status}'
                raise http.client.HTTPException(msg)
            return (await response.text())

    async def get_body(self):
        commit = self.commit
        branch = self.payload['ref']
        diff_stat = self.get_diff_stat()
        diff = await self.get_diff(f"{commit['url']}.diff")
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
{diff_stat}

{diff}
        """
        return template

    async def send_email(self, sender, recipient):
        body = await self.get_body()
        async with self.smtp as smtp:
            await smtp.connect()
            return (await smtp.sendmail(sender, [recipient], body))


class PushEvent:

    def __init__(self, config, client, smtp, request):
        self.config = config
        self.client = client
        self.smtp = smtp
        self.request = request

    async def process(self):
        if self.request.content_type != 'application/json':
            msg = f'can only accept application/json, not {self.request.content_type}'
            raise ResponseExit(status=http.HTTPStatus.UNSUPPORTED_MEDIA_TYPE, text=msg)
        payload = await self.request.json()
        if len(payload['commits']) == 0:
            raise ResponseExit(status=http.HTTPStatus.NO_CONTENT)
        branch_name = payload['ref'].split('/').pop()
        if branch_name not in self.config.allowed_branches:
            raise ResponseExit(status=http.HTTPStatus.NO_CONTENT)
        email = Email(self.smtp, self.client, payload)
        _, message = await email.send_email(self.config.sender, self.config.recipient)
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
