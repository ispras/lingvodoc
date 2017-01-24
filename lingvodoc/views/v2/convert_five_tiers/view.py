from pyramid.view import view_config
from lingvodoc.models import (
    DBSession,
    Client,
    Dictionary,
    TranslationGist
)
from pyramid.httpexceptions import (
    HTTPOk,
    HTTPNotFound,
    HTTPError,
    HTTPBadRequest
)
from lingvodoc.cache.caching import TaskStatus
from lingvodoc.views.v2.convert_five_tiers.core import async_convert_dictionary_new

@view_config(route_name='convert_five_tiers', renderer='json', request_method='POST')
def convert_dictionary(request):  # TODO: test
    req = request.json_body
    client_id = request.authenticated_userid
    user = Client.get_user_by_client_id(client_id)
    locale_id = int(request.cookies.get('locale_id') or 2)
    try:
        args = dict()
        args["client_id"] = client_id
        args["origin_client_id"] = req["client_id"]
        args["origin_object_id"] = req["object_id"]
        args["dictionary_client_id"] = req["dictionary_client_id"]
        args["dictionary_object_id"] = req["dictionary_object_id"]
        args["sqlalchemy_url"] = request.registry.settings["sqlalchemy.url"]
        args["storage"] = request.registry.settings["storage"]
        args['eaf_url'] = req['eaf_url']
        args["locale_id"] = locale_id
        if "sound_url" in req:
            args['sound_url'] = req['sound_url']
    except HTTPError as e:
        request.response.status = HTTPError.code
        return {'error': str(e)}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}
    dictionary_obj = DBSession.query(Dictionary).filter_by(client_id=req["dictionary_client_id"],
                                                   object_id=req["dictionary_object_id"]).first()
    gist = DBSession.query(TranslationGist).filter_by(client_id=dictionary_obj.translation_gist_client_id,
                                                      object_id=dictionary_obj.translation_gist_object_id).first()
    task = TaskStatus(user.id, "Eaf dictionary conversion", gist.get_translation(locale_id), 10)
    args["task_key"] = task.key
    args["cache_kwargs"] = request.registry.settings["cache_kwargs"]
    res = async_convert_dictionary_new.delay(**args)
    request.response.status = HTTPOk.code
    return {"status": "Your dictionary is being converted."
                      " Wait 5-15 minutes and you will see new dictionary in your dashboard."}



