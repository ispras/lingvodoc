__author__ = 'alexander'

import dill
# from lingvodoc.models import DBSession, Entity
# from dogpile.cache.api import NO_VALUE

from lingvodoc.cache.api.cache import ICache

import logging
log = logging.getLogger(__name__)

from zope.sqlalchemy import ZopeTransactionExtension
from sqlalchemy.orm import scoped_session, sessionmaker
DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))

class ThroughCache(ICache):
    def __init__(self, redis):
        """
        :param redis: redis database
        :return:
        """
        self.cache = redis

    def get(self, keys = None, objects = dict()):
        """
        Gets objects from cache and database, if needed

        :keys: string/list of strings.
            Returns stored in cache value/list of values. No database queries.
        :objects: dictionary
            Gets objects by their lingvodoc_id
            Input/output format:
            {                                                   {
                int : ((1, 2), (3, 4), ...),                        int : [object1, object2, ...],
                <custom class> : ((5, 6), (7, 8), ...),   -->       <custom class> : [object3, object4, ...),
                ...                                                 ...
            }                                                   }

            {
                int : ((1, 2), (3, 4), ...),              -->   [object1, object2, ...]
            }

            {
                int : ((1, 2)),                           -->   object1
            }

        """
        if isinstance(keys, str):
            cached = self.cache.get(keys)
            if cached is None:
                return None
            return dill.loads(cached)
        elif isinstance(keys, list):
            result = []
            for key in keys:
                cached = self.cache.get(key)
                if cached is None:
                    result.append(None)
                result.append(dill.loads(cached))
            return result


        try:
            result = dict()
            for obj_type, ids in objects:
                result[obj_type] = []
                for lingvodoc_id in ids:
                    key = f"auto:{obj_type.__name__}:{lingvodoc_id[0]}:{lingvodoc_id[1]}"
                    cached = self.cache.get(key)
                    if cached is None:
                        cached = DBSession.query(obj_type) \
                                        .filter_by(client_id=lingvodoc_id[0], object_id=lingvodoc_id[1]) \
                                        .first()
                        if cached is None:
                            pass
                        else:
                            self.cache.set(key, dill.dumps(cached))
                    else:
                        cached = dill.loads(cached)
                    result[obj_type].append(cached)
        except Exception as e:
            log.error(f'Exception during getting from cache : {e}')
            return None
        if len(result) == 1:
            result = result.popitem()[1]
            if len(result) == 1:
                result = result[0]
        return result



    # TODO: add try/catch handlers.
    def set(self, key = None, value = None, key_value = dict(), objects = list(), transaction = False):
        """
        Inserts objects to cache and database

        :key: :value: string
            Stores key-value pair in cache. No database queries.
        :key_value: dictionary
            Stores key-value pairs in cache. No database queries.
        :objects: list/tuple of objects
            Inserts objects into database, then to cache. Basically stores one by one.
            If you want to save all or nothing, use :transaction:
            Returns list of True/False(one value if :transaction:) flags of success
        """
        if key is not None:
            self.cache.set(key, dill.dumps(value))
            return
        self.cache.mset(dict(map(lambda key, value: (key, dill.dumps(value)), key_value.items())))


        if transaction:
            DBSession.begin()
            accepted_for_caching = dict()

        result = []
        for obj in objects:
            if not transaction:
                DBSession.begin()
            key = f'{obj.__class__.__name__}:{obj[0]}:{obj[1]}'
            try:
                DBSession.add(obj)
                if not transaction:
                    DBSession.commit()
                    self.cache.set(key, dill.dumps(obj))
                    result.append(True)
                else:
                    accepted_for_caching[key] = dill.dumps(obj)
            except:
                result.append(False)
                DBSession.rollback()
                log.warn(f"Error in saving {key} to database")

        if transaction:
            try:
                DBSession.commit()
                self.cache.mset(accepted_for_caching)
                return True
            except:
                return False
        return result

    def rem(self, keys):
        """
        Removes keys from cache
        :keys: string/list of strings.
            Removes stored in cache value/list of values. No database queries.
        """
        if isinstance(keys, str):
            self.cache.delete(keys)
        elif isinstance(keys, list):
            self.cache.delete(*keys)
