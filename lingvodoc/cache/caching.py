import time
# from dogpile.cache.api import NO_VALUE
# from dogpile.cache import make_region
from redis import Redis

from lingvodoc.cache.basic.cache import CommonCache
from lingvodoc.cache.mock.cache import MockCache
from lingvodoc.cache.through.cache import ThroughCache, DBSession

import uuid
import dill

# We initialize MEMOIZE to identity function so that if the cache is not initialized (e.g. when an
# automatically extracted source code documentation is being compiled), it is still possible to use it.
MEMOIZE = lambda x: x
CACHE = None

# DBSession = DBSession

def create_region(args):
    region = make_region().configure(**args)
    return region


# wrapper(req) - is a cache wrapper. The current cache key form is
# the following: "<REQ_METHOD>:<URL_PATH>?<PARAM1>&<PARAM2>..."
# We should store the additional dictionary of prefixes like
# "<REQ_METHOD>:<URL_PATH>" in the future for invalidation purposes.
# The values of this dict is a list of suffixes like "?<PARAM1>&<PARAM2>..."
# In case POST method changes something regarding a prefix we should
# clear all cached values related to it
#
# We cache values for unauthenticated users only so far
def cache_responses(region):
    def func_wrapper(func):
        def wrapper(req):
            if 'auth_tkt' not in req.environ['webob._parsed_cookies'][0]:
                key = (req.environ['REQUEST_METHOD'] + ':' +
                       req.environ['PATH_INFO'] + '?' +
                       req.environ['QUERY_STRING'])
                cached = region.get(key)
                if cached is not NO_VALUE:
                    return cached
                cached = func(req)
                region.set(key, cached)
            else:
                cached = func(req)
            return cached
        return wrapper
    return func_wrapper


def initialize_cache(args):
    global MEMOIZE
    global CACHE
    if args is None:
        MEMOIZE = lambda func: func
        CACHE = MockCache()
        return
    # region = make_region().configure(**args)
    # MEMOIZE = cache_responses(region)
    # CACHE = CommonCache(Redis(**args))
    CACHE = ThroughCache(Redis(**args))

class TaskStatus():
    def __init__(self, user_id, task_family, task_details, total_stages):
        self.id = str(uuid.uuid4())
        self.user_id = str(user_id)
        self.key = "task:" + self.id
        self.current_stage = 1
        self.total_stages = total_stages
        self.progress = 0
        self.task_family = task_family
        self.task_details = task_details
        self.status = "Starting the task"
        self.result_link_list = []

        self.created_at = time.time()

        self.put_to_cache()

    def put_to_cache(self):
        if CACHE:
            CACHE.set(self.key, dill.dumps(self))
            current_tasks = CACHE.get("current_tasks:" + self.user_id)
            if current_tasks:
                current_tasks = dill.loads(current_tasks)
                if self.key not in current_tasks:
                    current_tasks.add(self.key)
            else:
                current_tasks = set([self.key])
            CACHE.set("current_tasks:" + self.user_id, dill.dumps(current_tasks))

    @classmethod
    def get_from_cache(cls, task_key):
        if CACHE:
            task = CACHE.get(task_key)
            if task:
                return dill.loads(task)
            else:
                return TaskStatus(0, "Dummy task", "task not found", 1)
        else:
            return TaskStatus(0, "Dummy task", "cache failure", 1)

    @classmethod
    def get_user_tasks(cls, user_id, clear_out=False):
        task_list = []
        if CACHE:
            current_tasks = CACHE.get("current_tasks:" + str(user_id))
            current_tasks = dill.loads(current_tasks) if current_tasks else []
            for task_id in current_tasks:
                task = CACHE.get(task_id)
                if task:
                    task = dill.loads(task)
                    task_list.append(task)
        task_list.sort(
            key=lambda task: (getattr(task, 'created_at', 0), task.id),
            reverse=True)
        if clear_out:
            return [task.__dict__ for task in task_list]
        else:
            return task_list

    def set(self, current_stage, progress, status, result_link = None, result_link_list = None):
        if current_stage:
            self.current_stage = current_stage
        self.progress = progress
        self.status = status

        self.result_link_list = [result_link] if result_link else []

        if result_link_list:
            self.result_link_list.extend(result_link_list)

        self.put_to_cache()

    def delete(self):
        if CACHE:
            current_tasks = CACHE.get("current_tasks:" + self.user_id)
            if current_tasks:
                current_tasks = dill.loads(current_tasks)
                if self.key in current_tasks:
                    current_tasks.remove(self.key)
                    CACHE.set("current_tasks:" + self.user_id, dill.dumps(current_tasks))
                    CACHE.rem(self.key)
        return None
