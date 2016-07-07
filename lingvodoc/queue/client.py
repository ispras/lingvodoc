__author__ = 'alexander'

import time

from lingvodoc.queue.celery import (
    PROGRESS_STORE
)
from lingvodoc.queue.cache import (
    QUEUED_TASKS
)


class QueueClient:

    # TODO: add throwing exception if PROGRESS_STORE is not defined
    @classmethod
    def update_progress(cls, task_id, percent):
        PROGRESS_STORE.set(task_id, percent)

    @classmethod
    def generate_task_id(cls, client_id):
        if PROGRESS_STORE is None:
            return None
        return str(client_id) + ':' + str(round(time.time() * 1000))

    @classmethod
    def add_task(cls, user, task_key, async_task):
        QUEUED_TASKS.set(user, task_key, async_task)

    @classmethod
    def get_tasks_info(cls, user):
        # Change to False if you don't want your tasks to be deleted from Redis.
        return QUEUED_TASKS.get(user, True)
