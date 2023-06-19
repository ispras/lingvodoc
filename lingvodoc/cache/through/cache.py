__author__ = 'winking-maniac'

import dill
# from lingvodoc.models import DBSession, Entity
# from dogpile.cache.api import NO_VALUE

from lingvodoc.cache.api.cache import ICache

import logging
log = logging.getLogger(__name__)


'''
TODO:
    0) Make true bulk get query
    1) Add caching lists of childs
    2) Add caching types with 1 id instead of 2
    3) Add caching not marked_deleted objects
    ? 4) Prettify current interface for getting/saving one object(maybe without backward compability)
    ? 5) Add caching for already supported classes(list of caching and supported for caching classes below)

Classes supported:
    Entity                  implemented
    LexicalEntry            implemented
    DictionaryPerspective   implemented
    Dictionary              implemented

    PublishingEntity
    TranslationAtom
    TranslationGist
    Language
    Field
    DictionaryPerspectiveToField
    ParserResult
    Parser
    UserBlobs

Task 1 can be implemented via extra classes with any structure you want to with signal field 'NO_DATABASE'
Task 2 can be implemented using CompositeIdMixin and IdMixin, maybe with another signal field
'''

class ThroughCache(ICache):
    def __init__(self, redis):
        """
        :param redis: redis database
        :return:
        """
        self.cache = redis

    def get(self, keys = None, objects = dict(), DBSession=None, keep_dims=False):
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

            keep_dims = False
            {
                int : ((1, 2)),                           -->   object1
            }

            keep_dims = True
            {
                int : ((1, 2)),                           -->   [object1,]
            }

        """
        if isinstance(keys, str):
            cached = self.cache.get(keys)
            if not cached:
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

        if not DBSession:
            err_msg = 'DBSession cannot be None'
            log.error(err_msg)
            # raise ValueError(err_msg)

        if DBSession is None:
            log.error("Missing DBSession parameter in CACHE.get()")
            return None
        # try:
        log.debug(objects)
        result = dict()
        for obj_type in objects:
            result[obj_type] = []
            for lingvodoc_id in objects[obj_type]:
                key = f"auto:{obj_type.__name__}:{lingvodoc_id[0]}:{lingvodoc_id[1]}"
                log.debug(key)
                cached = self.cache.get(key)
                if cached is None:
                    cached = DBSession.query(obj_type) \
                                    .filter_by(client_id=lingvodoc_id[0], object_id=lingvodoc_id[1]) \
                                    .first()
                    if not cached:
                        pass
                    else:
                        self.cache.set(key, dill.dumps(cached))
                else:
                    # potentially race condition following data loss
                    # cached = DBSession.merge(dill.loads(cached), load=False)
                    cached = dill.loads(cached)
                    try:
                        DBSession.add(cached)
                    except:
                        cached = DBSession.query(obj_type) \
                                        .filter_by(client_id=lingvodoc_id[0], object_id=lingvodoc_id[1]) \
                                        .first()

                result[obj_type].append(cached)
        # except Exception as e:
        #     log.error(f'Exception during getting from cache : {e}')
        #     return None
        if len(result) == 1:
            result = result.popitem()[1]
            if len(result) == 1 and not keep_dims:
                result = result[0]
        return result



    # TODO: add try/catch handlers.
    def set(self, key = None, value = None, key_value = None, objects = list(), transaction = False, DBSession=None):
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
        if key_value is not None:
            self.cache.mset(
                dict(
                    map(lambda key_value_pair: (key_value_pair[0], dill.dumps(key_value_pair[1]) ),
                        key_value.items()
                    )
                )
            )



        if DBSession is None:
            log.error("Missing DBSession parameter in CACHE.get()")
            return None
        if transaction:
            try:
                accepted_for_caching = dict(
                    map(
                        lambda obj:
                            (f'auto:{obj.__class__.__name__}:{obj.client_id}:{obj.object_id}', dill.dumps(obj)),
                        objects
                    )
                )
                DBSession.add_all(objects)
                DBSession.flush()
                self.cache.mset(accepted_for_caching)
                return True
            except:
                return False
        else:
            result = []
            for obj in objects:
                key = f'auto:{obj.__class__.__name__}:{obj.client_id}:{obj.object_id}'
                log.debug(key)
                try:
                    DBSession.add(obj)
                    DBSession.flush()
                    self.cache.set(key, dill.dumps(obj))
                    result.append(True)
                except:
                    result.append(False)
                    log.warning(f"Error in saving {key} to database")
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
