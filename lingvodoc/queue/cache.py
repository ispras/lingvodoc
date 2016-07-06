__author__ = 'alexander'

import pickle

# from dogpile.cache.api import NO_VALUE
# from dogpile.cache import make_region

from redis import StrictRedis

QUEUED_TASKS = None


class TaskCache:
    def __init__(self, user_kwargs, task_kwargs):
        # self.region_user = make_region().configure(**user_kwargs)
        # self.region_task = make_region().configure(**task_kwargs)
        self.user_store = StrictRedis(**user_kwargs)
        self.task_store = StrictRedis(**task_kwargs)

    def get(self, user, remove_finished=False):
        """ Gets a dictionary of tasks for the user
        :param user: User whose tasks we're looking for
        :param remove_finished: If True then all finished tasks will be deleted from the store and
        its IDs will be removed from the user's list of tasks.
        :return: a dictionary of tasks {'Task ID (hash)': 'Finished (True/False)'}. If there is no tasks
        then the return value is an empty dict.
        """
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
            result[t] = async_result.ready()
            if remove_finished:
                if async_result.ready():
                    self.task_store.delete(t)
                else:
                    remained_tasks.append(t)
        if remove_finished:
            self.user_store.set(user.id, pickle.dumps(remained_tasks))
        return result


    #TODO: add try/catch handlers.
    # we should remove the task from caches (and queue?) if exception is raised
    def set(self, user, async_task):
        task_key = hash(async_task)
        self.task_store.set(task_key, pickle.dumps(async_task))
        cached = self.user_store.get(user.id)
        if cached is None:
            tmp_tasks = [task_key]
        else:
            tmp_tasks = pickle.loads(cached)
            tmp_tasks.append(task_key)
        self.user_store.set(user.id, pickle.dumps(tmp_tasks))


def initialize_queue(args):
    global QUEUED_TASKS
    QUEUED_TASKS = TaskCache(args['user_cache'], args['task_cache'])
