from lingvodoc.scripts.convert_five_tiers import convert_all
from lingvodoc.queue.celery import celery

@celery.task
def async_convert_dictionary_new(user_id, client_id, object_id, language_client_id, language_object_id, gist_client_id, gist_object_id, sqlalchemy_url, storage,eaf_url, sound_url=None):
    convert_all(language_client_id,
                language_object_id,
                user_id,
                client_id,
                object_id,
                gist_client_id,
                gist_object_id,
                sqlalchemy_url,
                storage,
                eaf_url,
                sound_url
                )
    return
