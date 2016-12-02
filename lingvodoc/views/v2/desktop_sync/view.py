import logging
from pyramid.view import view_config
from sqlite3 import connect
from lingvodoc.models import (
    DBSession,
    UserBlobs
)

from pyramid.httpexceptions import (
    HTTPOk,
    HTTPNotFound
)
from lingvodoc.views.v2.desktop_sync.core import async_download_dictionary


log = logging.getLogger(__name__)


@view_config(route_name='download_dictionary', renderer='json', request_method='POST')
def download_dictionary(request):  # TODO: test
    req = request.json_body
    args = dict()
    args["client_id"] = req["client_id"]
    args["object_id"] = req["object_id"]
    args["central_server"] = request.registry.settings["desktop"]['central_server']
    args["storage"] = request.registry.settings["storage"]
    args['sqlalchemy_url'] = request.registry.settings["sqlalchemy.url"]
    res = async_download_dictionary.delay(**args)
    # async_convert_dictionary_new(user_id, req['blob_client_id'], req['blob_object_id'], req["language_client_id"], req["language_object_id"], req["gist_client_id"], req["gist_object_id"], request.registry.settings["sqlalchemy.url"], request.registry.settings["storage"])
    log.debug("Conversion started")
    request.response.status = HTTPOk.code
    return {"status": "Your dictionary is being converted."
                      " Wait 5-15 minutes and you will see new dictionary in your dashboard."}



