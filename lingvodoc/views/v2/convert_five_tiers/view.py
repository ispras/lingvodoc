import logging
import warnings
from pyramid.view import view_config
from sqlite3 import connect
from lingvodoc.models import (
    DBSession,
    Client
)

from pyramid.httpexceptions import (
    HTTPOk,
    HTTPNotFound
)
from lingvodoc.views.v2.convert_five_tiers.core import async_convert_dictionary_new


log = logging.getLogger(__name__)

@view_config(route_name='convert_five_tiers', renderer='json', request_method='POST')
def convert_dictionary(request):  # TODO: test
    req = request.json_body
    client_id = request.authenticated_userid
    user = Client.get_user_by_client_id(client_id)
    locale_id = int(request.cookies.get('locale_id') or 2)
    args = dict()
    args["user_id"] = client_id
    args["client_id"] = req["client_id"]
    args["object_id"] = req["object_id"]
    args["dictionary_client_id"] = req["dictionary_client_id"]
    args["dictionary_object_id"] = req["dictionary_object_id"]
    args["sqlalchemy_url"] = request.registry.settings["sqlalchemy.url"]
    args["storage"] = request.registry.settings["storage"]
    args['eaf_url'] = req['eaf_url']
    args["locale_id"] = locale_id
    if "sound_url" in req:
        args['sound_url'] = req['sound_url']
    res = async_convert_dictionary_new.delay(**args)
    # async_convert_dictionary_new(user_id, req['blob_client_id'], req['blob_object_id'], req["language_client_id"], req["language_object_id"], req["gist_client_id"], req["gist_object_id"], request.registry.settings["sqlalchemy.url"], request.registry.settings["storage"])
    log.debug("Conversion started")
    request.response.status = HTTPOk.code
    return {"status": "Your dictionary is being converted."
                      " Wait 5-15 minutes and you will see new dictionary in your dashboard."}



