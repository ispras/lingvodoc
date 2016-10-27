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
from lingvodoc.views.v2.convert_dictionary_dialeqt.core import async_convert_dictionary_new


log = logging.getLogger(__name__)

@view_config(route_name='convert_dictionary_dialeqt', renderer='json', request_method='POST')
def convert_dictionary(request):  # TODO: test
    req = request.json_body
    user_id = request.authenticated_userid
    args = dict()
    args["user_id"] = user_id
    args['client_id'] = req['blob_client_id']
    args['object_id'] = req['blob_object_id']
    args["language_client_id"] = req["language_client_id"]
    args["language_object_id"] = req["language_object_id"]
    args["gist_client_id"] = req["gist_client_id"]
    args["gist_object_id"] = req["gist_object_id"]
    args["sqlalchemy_url"] = request.registry.settings["sqlalchemy.url"]
    res = async_convert_dictionary_new.delay(**args)
    log.debug("Conversion started")
    request.response.status = HTTPOk.code
    return {"status": "Your dictionary is being converted."
                      " Wait 5-15 minutes and you will see new dictionary in your dashboard."}


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
        dict_attributes = get_dict_attributes(sqconn)
        dictionary_name = dict_attributes["dictionary_name"]
        request.response.status = HTTPOk.code
        return {"dictionary_name": dictionary_name}
    request.response.status = HTTPNotFound.code
    return {'error': str("No such blob in the system")}



