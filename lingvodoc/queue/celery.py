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

log = logging.getLogger(__name__)
parser = ConfigParser()
parser.read('celery.ini')


def _parse_celery_args():
    kwargs = dict()
    try:
        for k, v in parser.items('celery'):
            if k == 'include':
                kwargs[k] = v.split('\n')
            else:
                kwargs[k] = v

        # kwargs['include'] = ['lingvodoc.views.v1.celery_test.core',
        #                      'lingvodoc.views.v1.convert.core']
        return kwargs
    except NoSectionError:
        log.warn("No 'celery' sections in config; disabling queue")
        return None


celery = None
kwargs = _parse_celery_args()
print(kwargs)
if kwargs is None:
    celery = MockApp()
else:
    celery = Celery(**kwargs)

celery_engine = create_engine('postgresql://postgres:@localhost/lingvodoc')