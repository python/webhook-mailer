A webhook to send every [CPython][cpython] commit to
[python-checkins][python-checkins] mailing list. It's based on
[python/the-knights-who-say-ni][ni] written by Brett Cannon.


## Requirements

* CPython 3.6
* aiohttp
* aiosmtplib

See [requirements.txt](requirements.txt) for details.


## Configuration

You can use following environment variables to configure the mailer
webhook:

* `SENDER_EMAIL`: This is required.
* `RECIPIENT_EMAIL`: This is required.
* `SMTP_HOSTNAME`: This is optional. Defaults to `'localhost'`.
* `SMTP_PORT`: This is optional. Defaults to `1025`.
* `SMTP_USERNAME`: This is optional.
* `SMTP_PASSWORD`: This is optional.
* `PORT`: This is optional. Defaults to `8585`.


## Usage

```sh
$ SENDER_EMAIL=sender@example.com RECIPIENT_EMAIL=recipient@example.com SMTP_USERNAME=spam SMTP_PASSWORD=eggs python3 mailer.py
```


## Development

You can use [aiosmtpd][aiosmtpd] as an SMTP server during development:

```sh
$ python -m aiosmtpd -nd -l localhost:1025
```


[cpython]: https://github.com/python/cpython
[python-checkins]: https://mail.python.org/mailman/listinfo/python-checkins
[ni]: https://github.com/python/the-knights-who-say-ni
[aiosmtpd]: https://aiosmtpd.readthedocs.io/en/latest/
