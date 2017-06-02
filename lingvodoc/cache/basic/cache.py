__author__ = 'alexander'

from dogpile.cache.api import NO_VALUE

from lingvodoc.cache.api.cache import ICache


class CommonCache(ICache):
    def __init__(self, region):
        """
        :param region: dogpile region
        :return:
        """
        self.cache = region

    def get(self, key):
        cached = self.cache.get(key)
        if cached is NO_VALUE:
            return None
        return cached

    # TODO: add try/catch handlers.
    def set(self, key, value):
        self.cache.set(key, value)

    def rem(self, key):
        self.cache.delete(key)
