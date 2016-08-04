from dogpile.cache.api import NO_VALUE
from dogpile.cache import make_region

from lingvodoc.cache.basic.cache import CommonCache
from lingvodoc.cache.mock.cache import MockCache


MEMOIZE = None
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
