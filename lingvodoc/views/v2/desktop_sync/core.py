from lingvodoc.scripts.desktop_sync import download_dictionary
from lingvodoc.queue.celery import celery


@celery.task
def async_download_dictionary(client_id, object_id, central_server, storage,
                              sqlalchemy_url, cookies,
                              task_key,
                              cache_kwargs):
    download_dictionary(client_id,
                        object_id,
                        central_server,
                        storage,
                        sqlalchemy_url,
                        cookies,
                        task_key,
                        cache_kwargs
                        )
    return
