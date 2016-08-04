__author__ = 'alexander'

from lingvodoc.cache.api.cache import ICache


class MockCache(ICache):
    def get(self, key):
        return None

    def set(self, key, value):
        pass
