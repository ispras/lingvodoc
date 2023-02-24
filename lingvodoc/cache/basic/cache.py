__author__ = 'alexander'

import dill

# from dogpile.cache.api import NO_VALUE

from lingvodoc.cache.api.cache import ICache


class CommonCache(ICache):
    def __init__(self, redis):
        """
        :param redis: redis database
        :return:
        """
        self.cache = redis

    def get(self, key):
        cached = self.cache.get(key)
        if cached is None:
            return None
        return dill.loads(cached)

    # TODO: add try/catch handlers.
    def set(self, key, value):
        self.cache.set(key, dill.dumps(value))

    def rem(self, key):
        self.cache.delete(key)
