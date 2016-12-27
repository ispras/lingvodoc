from dogpile.cache.api import NO_VALUE
from dogpile.cache import make_region

from lingvodoc.cache.basic.cache import CommonCache
from lingvodoc.cache.mock.cache import MockCache

import uuid
import json

# We initialize MEMOIZE to identity function so that if the cache is not initialized (e.g. when an
# automatically extracted source code documentation is being compiled), it is still possible to use it.
MEMOIZE = lambda x: x
CACHE = None


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
    region = make_region().configure(**args)
    MEMOIZE = cache_responses(region)
    CACHE = CommonCache(region)


class TaskStatus():
    def __init__(self, user_id, task_family, task_details, total_stages):
        self.id = str(uuid.uuid4())
        self.user_id = str(user_id)
        self.key = "task:" + + self.id
        self.current_stage = 1
        self.total_stages = total_stages
        self.progress = 0
        self.task_family = task_family
        self.task_details = task_details
        self.status = "Starting the task"

    def put_to_cache(self):
        if CACHE:
            CACHE.set(self.key, dill.dumps(self))
            current_tasks = CACHE.get("current_tasks:" + self.user_id)
            if current_tasks:
                if self.key not in current_tasks:
                    current_tasks.add(self.key)
            else:
                current_tasks = set([self.key])
            CACHE.set(self.user_id, current_tasks)

    @classmethod
    def get_from_cache(self, task_id):
        task = CACHE.get(task_id)
        if task:
            return dill.loads(task)
        else:
            return None

    @classmethod
    def get_user_tasks(self, user_id, serialize):
        task_list = []
        if CACHE:
            current_tasks = CACHE.get("current_tasks:" + self.user_id)
            for task_id in current_tasks:
                task = CACHE.get(task_id)
                if task:
                    task_list.append(task)
        if serialize:
            return json.dumps(task_list)
        else:
            return task_list

    def set(self, current_stage, progress, status):
        self.current_stage = current_stage
        self.progress = progress
        self.status = status
