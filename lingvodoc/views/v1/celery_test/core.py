__author__ = 'alexander'

from lingvodoc.queue.celery import (
    celery
)
from lingvodoc.queue.client import QueueClient

import time


@celery.task
def test_queue_set_logic(task_id):
    QueueClient.update_progress(task_id, 0)
    for i in range(1, 100):
        QueueClient.update_progress(task_id, i)
        time.sleep(0.25)
    print('AAA')
    QueueClient.update_progress(task_id, 100)
    return 300
