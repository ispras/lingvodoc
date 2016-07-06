__author__ = 'alexander'

from lingvodoc.queue.celery import (
    celery
)

import time


@celery.task()
def test_queue_set_logic():
    time.sleep(2)
    print('AAA')
    return 300
