FROM python:3.4-alpine
ADD . /api
WORKDIR /api
RUN apk add --update postgresql-dev build-base python-dev py-pip wget freetype-dev libpng-dev openssl-dev libffi-dev
RUN pip install -U pip setuptools && pip install -r server-requirements.txt && pip install alembic gunicorn 
