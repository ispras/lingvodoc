from lingvodoc.scripts.desktop_synch import download_dictionary
from lingvodoc.queue.celery import celery


@celery.task
def async_download_dictionary(client_id, object_id, sqlalchemy_url, central_server, storage):
    download_dictionary(client_id,
                        object_id,
                        sqlalchemy_url,
                        central_server,
                        storage
                        )
    return
