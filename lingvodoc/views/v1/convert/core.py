__author__ = 'alexander'

from lingvodoc.models import (
    Client,
    DBSession,
    UserBlobs
)

from lingvodoc.scripts.lingvodoc_converter import convert_one
from lingvodoc.queue.celery import (
    celery,
    celery_engine
)

from pyramid.httpexceptions import (
    HTTPOk
)
from pyramid.security import (
    authenticated_userid,
)

import logging

log = logging.getLogger(__name__)


@celery.task
def async_convert_dictionary(client_id, object_id, parent_client_id, parent_object_id, dictionary_client_id,
                             dictionary_object_id, perspective_client_id, perspective_object_id, user_id,
                             task_id=None):
    DBSession.configure(bind=celery_engine)
    client = DBSession.query(Client).filter_by(id=user_id).first()
    user = client.user
    blob = DBSession.query(UserBlobs).filter_by(client_id=client_id, object_id=object_id).first()

    # convert_one(blob.real_storage_path,
    #             user.login,
    #             user.password.hash,
    #             parent_client_id,
    #             parent_object_id)

    # NOTE: doesn't work on Mac OS otherwise

    convert_one(blob.real_storage_path,
                user.login,
                user.password.hash,
                parent_client_id,
                parent_object_id,
                dictionary_client_id,
                dictionary_object_id,
                perspective_client_id,
                perspective_object_id,
                task_id=task_id)

    return