__author__ = 'alexander'

import logging

log = logging.getLogger(__name__)


class MockRedisClient:
    """
    Mocks Redis client class. Used if Celery is disabled. Does nothing.
    """

    def set(self, *args):
        log.debug("Setting a value in MockRedisClient")

    def generate_task_id(self, client_id):
        return None
