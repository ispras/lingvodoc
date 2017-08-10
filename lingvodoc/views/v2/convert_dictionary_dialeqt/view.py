import base64
from hashlib import md5
from sqlite3 import connect
from pyramid.view import view_config
from pyramid.httpexceptions import (
    HTTPOk,
    HTTPNotFound,
    HTTPBadRequest,
    HTTPConflict
)
from lingvodoc.models import (
    DBSession,
    Dictionary,
    UserBlobs,
    Client,
    TranslationGist
)
from lingvodoc.exceptions import CommonException
from lingvodoc.views.v2.convert_dictionary_dialeqt.core import async_convert_dictionary_new
from lingvodoc.views.v2.utils import anonymous_userid
from lingvodoc.cache.caching import TaskStatus

@view_config(route_name='convert_dictionary_dialeqt', renderer='json', request_method='POST')
def convert_dictionary(request):  # TODO: test
    try:
        req = request.json_body
        locale_id = int(request.cookies.get('locale_id') or 1)
        client_id = request.authenticated_userid
        if not client_id:
            user_id = anonymous_userid(request)
        else:
            user_id = Client.get_user_by_client_id(client_id).id
        args = dict()
        if "dictionary_client_id" in req and "dictionary_object_id" in req:
            args["dictionary_client_id"] = req["dictionary_client_id"]
            args["dictionary_object_id"] = req["dictionary_object_id"]
        else:
            args["dictionary_client_id"] = None
            args["dictionary_object_id"] = None
        args["client_id"] = client_id
        args['blob_client_id'] = req['blob_client_id']
        args['blob_object_id'] = req['blob_object_id']
        if "language_client_id" in req and "language_object_id" in req:
            args["language_client_id"] = req["language_client_id"]
            args["language_object_id"] = req["language_object_id"]
        else:
            args["language_client_id"] = None
            args["language_object_id"] = None
        if "gist_client_id" in req and "gist_object_id" in req:
            args["gist_client_id"] = req["gist_client_id"]
            args["gist_object_id"] = req["gist_object_id"]
        else:
            args["gist_client_id"] = None
            args["gist_object_id"] = None
        args["sqlalchemy_url"] = request.registry.settings["sqlalchemy.url"]
        args["storage"] = request.registry.settings["storage"]
        args["locale_id"] = locale_id
        args["cache_kwargs"] = request.registry.settings["cache_kwargs"]
        gist = DBSession.query(TranslationGist).filter_by(client_id=args["gist_client_id"],
                                                          object_id=args["gist_object_id"]).first()
        try:
            if gist:
                task = TaskStatus(user_id, "Dialeqt dictionary conversion", gist.get_translation(locale_id), 10)
            else:
                dictionary_obj = DBSession.query(Dictionary).filter_by(client_id=req["dictionary_client_id"],
                                                               object_id=req["dictionary_object_id"]).first()
                gist = DBSession.query(TranslationGist).\
                    filter_by(client_id=dictionary_obj.translation_gist_client_id,
                              object_id=dictionary_obj.translation_gist_object_id).first()
                task = TaskStatus(user_id, "Dialeqt dictionary conversion", gist.get_translation(locale_id), 10)
        except:
            request.response.status = HTTPBadRequest.code
            return {'error': "wrong parameters"}
        args["task_key"] = task.key
        res = async_convert_dictionary_new.delay(**args)
        request.response.status = HTTPOk.code
        return {"status": "Your dictionary is being converted."
                          " Wait 5-15 minutes and you will see new dictionary in your dashboard."}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}
    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'error': str(e)}

def get_dict_attributes(sqconn):
    dict_trav = sqconn.cursor()
    dict_trav.execute("""SELECT
                        dict_name,
                        dict_identificator,
                        dict_description
                        FROM
                        dict_attributes
                        WHERE
                        id = 1;""")
    req = dict()
    for dictionary in dict_trav:
        req['dictionary_name'] = dictionary[0]
        req['dialeqt_id'] = dictionary[1]
    return req


@view_config(route_name='convert_dictionary_dialeqt_get_info', renderer='json', request_method='GET')
def convert_dictionary_dialeqt_get_info(request):  # TODO: test
    blob_client_id = request.matchdict.get('blob_client_id')
    blob_object_id = request.matchdict.get('blob_object_id')
    blob = DBSession.query(UserBlobs).filter_by(client_id=blob_client_id, object_id=blob_object_id).first()
    if blob:
        filename = blob.real_storage_path
        sqconn = connect(filename)
        try:
            dict_attributes = get_dict_attributes(sqconn)
        except:
            return {'error': str("database disk image is malformed")}
        dictionary_name = dict_attributes["dictionary_name"]
        request.response.status = HTTPOk.code
        return {"dictionary_name": dictionary_name}
    request.response.status = HTTPNotFound.code
    return {'error': str("No such blob in the system")}



