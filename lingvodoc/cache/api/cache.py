__author__ = 'alexander'


# TODO: It has to be an abstract class in the future. Read `abc — Abstract Base Classes`
class ICache:

    # Don't think we should return NO_VALUE in this API if the value is not cached.
    def get(self, key):
        """
        :param key:
        :return: Cached value or None if there is no such value in the cache.
        """
        raise NotImplementedError

    def set(self, user, value):
        raise NotImplementedError

    def rem(self, key):
        raise NotImplementedError
