"""
Creates a Celery instance app and task sores. We don't create it in lingvodoc.__init__.py because workers
need to have a working connection to Celery and we don't want to run a separate instance of lingvodoc on
workers. So, local `celery.ini` contains configuration for Celery. I used static `celery.ini` file because
there is no way to provide configuration file to Celery. Read more here:
http://docs.celeryproject.org/en/latest/getting-started/first-steps-with-celery.html#configuration

If you want to disable Celery then just make kwargs = None and MockApp will be used instead of Celery.
It also happens if `celery.ini` is incomplete. The same for TaskStore

To run a worker you need to run `celery worker -A lingvodoc.queue.celery` from lingvodoc root having all
lingvodoc pip dependencies installed.
"""

__author__ = 'alexander'

import logging
from configparser import (
    ConfigParser,
    NoSectionError
)

from sqlalchemy import create_engine

from celery import Celery

from lingvodoc.queue.basic.cache import TaskCache
from lingvodoc.queue.mock.cache import MockTaskCache
from lingvodoc.queue.mock.celery import MockApp

log = logging.getLogger(__name__)
parser = ConfigParser()
parser.read('celery.ini')


def _parse_celery_args():
    celery_kwargs = dict()
    progress_kwargs = dict()
    user_cache_kwargs = dict()
    task_cache_kwargs = dict()
    try:
        for k, v in parser.items('queue:user_redis'):
            user_cache_kwargs[k] = v
        for k, v in parser.items('queue:task_redis'):
            task_cache_kwargs[k] = v
        for k, v in parser.items('celery'):
            if k == 'include':
                celery_kwargs[k] = v.split('\n')
            else:
                celery_kwargs[k] = v
        for k, v in parser.items('queue:progress_redis'):
            progress_kwargs[k] = v
        return {
            'celery': celery_kwargs,
            'progress': progress_kwargs,
            'user_cache': user_cache_kwargs,
            'task_cache': task_cache_kwargs
        }
    except NoSectionError:
        log.warn("No 'celery' or 'queue:(progress|task|user)_redis' sections in config; disabling queue")
        return None

QUEUED_TASKS = None

celery = None
kwargs = _parse_celery_args()
# kwargs = None
if kwargs is None:
    celery = MockApp()
    QUEUED_TASKS = MockTaskCache()
else:
    celery = Celery(**kwargs['celery'])
    QUEUED_TASKS = TaskCache(kwargs['user_cache'], kwargs['task_cache'], kwargs['progress'])

# TODO: get a connection string from the configuration file
# celery_engine = create_engine('postgresql://postgres:@localhost/lingvodoc')
celery_engine = None
