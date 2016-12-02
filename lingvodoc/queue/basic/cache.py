__author__ = 'alexander'

import pickle

from lingvodoc.queue.api.cache import ITaskCache
from lingvodoc.queue.basic.redis_client import LingvodocRedisClient

from redis import StrictRedis


class TaskCache(ITaskCache):
    """
    `self.user_store': {'user_id': <list of task_ids>}
    `self.task_store`: {'task_id`: <AsyncResult>}
    `self.progress_store`: {`task_id`: `progress_value(int)`}
    """
    def __init__(self, user_kwargs, task_kwargs ,progress_kwargs):
        self.user_store = StrictRedis(**user_kwargs)
        self.task_store = StrictRedis(**task_kwargs)
        self.progress_store = LingvodocRedisClient(**progress_kwargs)

    def get(self, user, remove_finished=False):
        result = dict()
        tasks = self.user_store.get(user.id)
        if tasks is None:
            return {}
        tasks = pickle.loads(tasks)
        remained_tasks = list()
        for t in tasks:
            val = self.task_store.get(t)
            if val is None:
                continue
            async_result = pickle.loads(val)
            progress = self.progress_store.get(t)
            # Redis client returns byte array. We need to decode it
            if progress is not None:
                progress = int(progress.decode())
            result[t] = {'finished': async_result.ready(),
                         'progress': progress}
            if remove_finished:
                if async_result.ready():
                    self.task_store.delete(t)
                else:
                    remained_tasks.append(t)
        if remove_finished:
            self.user_store.set(user.id, pickle.dumps(remained_tasks))
        return result


    # TODO: add try/catch handlers.
    # we should remove the task from caches (and queue?) if exception is raised
    def set(self, user, task_key, async_task):
        self.task_store.set(task_key, pickle.dumps(async_task))
        cached = self.user_store.get(user.id)
        if cached is None:
            tmp_tasks = [task_key]
        else:
            tmp_tasks = pickle.loads(cached)
            tmp_tasks.append(task_key)
        self.user_store.set(user.id, pickle.dumps(tmp_tasks))
