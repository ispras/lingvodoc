"""
Creates a Celery instance app. We don't create it in lingvodoc.__init__.py because workers need to
have a working connection to Celery and we don't want to run separate lingvodoc instance on workers.
So, local `celery.ini` contains configuration for Celery. Hardcoded kwargs['include'] lists modules
with queueable methods. If you want to disable Celery then just make kwargs = None and MockApp will
be used instead of Celery. It also happens if `celery.ini` is incomplete.

To run worker you need to run `celery -A lingvodoc.queue.celery worker` from root lingvodoc celery
having all lingvodoc pip dependencies.
"""

__author__ = 'alexander'

import logging

from celery import Celery
from configparser import (
    ConfigParser,
    NoSectionError
)
from lingvodoc.queue.mock_task import (
    MockApp
)
from sqlalchemy import create_engine
from redis import StrictRedis

log = logging.getLogger(__name__)
parser = ConfigParser()
parser.read('celery.ini')


def _parse_celery_args():
    celery_kwargs = dict()
    redis_kwargs = dict()
    try:
        for k, v in parser.items('celery'):
            if k == 'include':
                celery_kwargs[k] = v.split('\n')
            else:
                celery_kwargs[k] = v
        for k, v in parser.items('queue:progress_redis'):
            redis_kwargs[k] = v
        return {'celery': celery_kwargs, 'redis': redis_kwargs}
    except NoSectionError:
        log.warn("No 'celery' or 'queue:progress_redis' sections in config; disabling queue")
        return None


celery = None
PROGRESS_STORE = None
kwargs = _parse_celery_args()
if kwargs is None:
    celery = MockApp()
else:
    celery = Celery(**kwargs['celery'])
    PROGRESS_STORE = StrictRedis(**kwargs['redis'])

# TODO: get a connection string from the configuration file
celery_engine = create_engine('postgresql://postgres:@localhost/lingvodoc')
