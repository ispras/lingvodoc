__author__ = 'alexander'

import time

from redis import StrictRedis


# TODO: Should we create an Interface class ILingvodocRedisClient(StrictRedis) that will be inherited
# by LingvodocRedisClient and MockRedisClient?
class LingvodocRedisClient(StrictRedis):

    def __init__(self, *args, **kwargs):
        super(LingvodocRedisClient, self).__init__(*args, **kwargs)

    def generate_task_id(self, client_id):
        return str(client_id) + ':' + str(round(time.time() * 1000))
