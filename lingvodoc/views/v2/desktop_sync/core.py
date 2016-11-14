from lingvodoc.scripts.desktop_sync import download_dictionary
from lingvodoc.queue.celery import celery


@celery.task
def async_download_dictionary(client_id, object_id, central_server, storage):
    download_dictionary(client_id,
                        object_id,
                        central_server,
                        storage
                        )
    return
