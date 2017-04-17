import logging
from pyramid.view import view_config
from sqlite3 import connect
from lingvodoc.models import (
    DBSession,
    Dictionary,
    TranslationGist,
    Client
)
from lingvodoc.cache.caching import TaskStatus
from pyramid.httpexceptions import (
    HTTPOk,
    HTTPBadRequest,
    HTTPUnauthorized
)
from lingvodoc.views.v2.desktop_sync.core import async_download_dictionary
import json
import requests

log = logging.getLogger(__name__)


def make_request(path, cookies, req_type='get', json_data=None):
    session = requests.Session()
    session.headers.update({'Connection': 'Keep-Alive'})
    adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
    # with open('authentication_data.json', 'r') as f:
    #     cookies = json.loads(f.read())
    session.mount('http://', adapter)
    # log.error(path)
    if req_type == 'get':
        status = session.get(path, cookies=cookies)
    elif req_type == 'post':
        status = session.post(path, json=json_data, cookies=cookies)
    else:
        return None
    return status

@view_config(route_name='download_dictionary', renderer='json', request_method='POST')
def download_dictionary(request):  # TODO: test
    req = request.json_body
    args = dict()
    locale_id = int(request.cookies.get('locale_id') or 2)
    client_id = request.authenticated_userid
    if not client_id:
        request.response.status = HTTPUnauthorized.code
        return {'error': "not authenticated"}
    else:
        user_id = Client.get_user_by_client_id(client_id).id
    args["client_id"] = req["client_id"]
    args["object_id"] = req["object_id"]
    args["central_server"] = request.registry.settings["desktop"]['central_server']
    args["storage"] = request.registry.settings["storage"]
    args['sqlalchemy_url'] = request.registry.settings["sqlalchemy.url"]
    args["cookies"] = json.loads(request.cookies.get('server_cookies'))
    try:
        dictionary_obj = DBSession.query(Dictionary).filter_by(client_id=req["client_id"],
                                                               object_id=req["object_id"]).first()
        if not dictionary_obj:
            dict_json = make_request(args["central_server"] + 'dictionary/%s/%s' % (
                req["client_id"],
                req["object_id"]), args["cookies"])
            if dict_json.status_code != 200 or not dict_json.json():
                task = TaskStatus(user_id, "Dictionary sync with server", "dictionary name placeholder", 5)
            else:
                dict_json = dict_json.json()
                gist = DBSession.query(TranslationGist). \
                    filter_by(client_id=dict_json['translation_gist_client_id'],
                              object_id=dict_json['translation_gist_object_id']).first()
                task = TaskStatus(user_id, "Dictionary sync with server", gist.get_translation(locale_id), 5)

        else:
            gist = DBSession.query(TranslationGist). \
                filter_by(client_id=dictionary_obj.translation_gist_client_id,
                          object_id=dictionary_obj.translation_gist_object_id).first()
            task = TaskStatus(user_id, "Dictionary sync with server", gist.get_translation(locale_id), 5)
    except:
        request.response.status = HTTPBadRequest.code
        return {'error': "wrong parameters"}
    args["task_key"] = task.key
    args["cache_kwargs"] = request.registry.settings["cache_kwargs"]
    res = async_download_dictionary.delay(**args)
    # async_convert_dictionary_new(user_id, req['blob_client_id'], req['blob_object_id'], req["language_client_id"], req["language_object_id"], req["gist_client_id"], req["gist_object_id"], request.registry.settings["sqlalchemy.url"], request.registry.settings["storage"])
    log.debug("Conversion started")
    request.response.status = HTTPOk.code
    return {"status": "Your dictionary is being converted."
                      " Wait 5-15 minutes and you will see new dictionary in your dashboard."}



