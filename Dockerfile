FROM python:3.7.17-slim-bookworm

# We create an /opt directory with a virtual environment in it to store our
# application in.
RUN set -x \
    && python3 -m venv /opt/mailer

# Now that we've created our virtual environment, we'll go ahead and update
# our $PATH to refer to it first.
ENV PATH="/opt/mailer/bin:${PATH}"
WORKDIR /opt/mailer/src/

# Define whether we're building a production or a development image. This will
# generally be used to control whether or not we install our development and
# test dependencies.
ARG DEVEL=no

# Next, we want to update pip, setuptools, and wheel inside of this virtual
# environment to ensure that we have the latest versions of them.
# TODO: We use --require-hashes in our requirements files, but not here, making
#       the ones in the requirements files kind of a moot point. We should
#       probably pin these too, and update them as we do anything else.
RUN pip --no-cache-dir --disable-pip-version-check install --upgrade pip setuptools wheel

# We copy this into the docker container prior to copying in the rest of our
# application so that we can skip installing requirements if the only thing
# that has changed is the Warehouse code itself.
COPY requirements /tmp/requirements

# Install our development dependencies if we're building a development install
# otherwise this will do nothing.
RUN --mount=type=cache,target=/root/.cache/pip \
    set -x \
    && if [ "$DEVEL" = "yes" ]; then pip --disable-pip-version-check install -r /tmp/requirements/dev.txt; fi

# Install the Python level Warehouse requirements, this is done after copying
# the requirements but prior to copying Warehouse itself into the container so
# that code changes don't require triggering an entire install of all of
# Warehouse's dependencies.
RUN --mount=type=cache,target=/root/.cache/pip \
    set -x \
    && pip --disable-pip-version-check \
            install --no-deps \
            -r /tmp/requirements/main.txt \
    && pip check \
    && find /opt/mailer -name '*.pyc' -delete

COPY . /opt/mailer/src/
