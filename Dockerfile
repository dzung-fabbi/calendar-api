# Pinned: Django 3.1 does not run on Python 3.12+, so the previous unpinned
# `FROM python:3` no longer produces a working image.
#
# bookworm, not bullseye: see the comment in `Dockerfile.test` -- bullseye's
# expired security Release file breaks `apt-get update` and made this image
# unbuildable too.
FROM python:3.9-bookworm

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends default-libmysqlclient-dev build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir /code
WORKDIR /code
COPY requirements.txt /code/
RUN pip install --upgrade pip && pip install -r requirements.txt
COPY . /code/
