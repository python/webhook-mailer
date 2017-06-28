## Configuration

You can use following environment variables to configure the mailer
webhook:

* `SENDER_EMAIL`: This is required.
* `RECIPIENT_EMAIL`: This is required.
* `SMTP_HOSTNAME`: This is optional. Defaults to `'localhost'`.
* `SMTP_PORT`: This is optional. Defaults to `1025`.
* `HTTP_PORT`: This is optional. Defaults to `8585`.


## Usage

```sh
$ SENDER_EMAIL=sender@example.com RECIPIENT_EMAIL=recipient@example.com python3 mailer.py
```


## Development

You can use [aiosmtpd](http://aiosmtpd.readthedocs.io/en/latest/) as an
SMTP server during development:

```sh
$ python -m aiosmtpd -nd -l localhost:1025
```
