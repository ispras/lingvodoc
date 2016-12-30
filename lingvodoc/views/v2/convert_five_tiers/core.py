from lingvodoc.scripts.convert_five_tiers import convert_all
from lingvodoc.queue.celery import celery

@celery.task
def async_convert_dictionary_new(user_id, client_id, object_id, dictionary_client_id, dictionary_object_id, sqlalchemy_url, storage, eaf_url, locale_id, sound_url=None):
    convert_all(dictionary_client_id,
                dictionary_object_id,
                user_id,
                client_id,
                object_id,
                sqlalchemy_url,
                storage,
                eaf_url,
                locale_id,
                sound_url=sound_url
                )
    return
