__author__ = 'alexander'

import logging

from lingvodoc.queue.api.cache import ITaskCache
from lingvodoc.queue.mock.redis_client import MockRedisClient

log = logging.getLogger(__name__)


class MockTaskCache(ITaskCache):
    """
    Represents mocked TaskCache that is used if Celery is disabled. Does nothing.
    """

    def __init__(self):
        self.progress_store = MockRedisClient()

    def get(self, user, remove_finished=False):
        log.debug("Getting a task in MockTaskCache")
        return {}

    def set(self, user, task_key, async_task):
        log.debug("Setting a task in MockTaskCache")
