import graphene

from lingvodoc.schema.gql_holders import (
    LingvodocObjectType,
    CompositeIdHolder,
    AdditionalMetadata,
    CreatedAt,
    MarkedForDeletion,
    Relationship,
    MovedTo,
    fetch_object,
    client_id_check,
    del_object,
    acl_check_by_id,
    ResponseError,
    LingvodocID,
    ObjectVal
)

from lingvodoc.models import (
    Entity as dbEntity,
    Field as dbField,
    PublishingEntity as dbPublishingEntity,
    LexicalEntry as dbLexicalEntry,
    Client,
    DBSession,
    DictionaryPerspective as dbDictionaryPerspective,
    Group as dbGroup,
    LexicalEntry as dbLexicalEntry,
    User as dbUser,
    ObjectTOC as dbObjectTOC,
    BaseGroup as dbBaseGroup,
    Dictionary as dbDictionary,
    TranslationGist as dbTranslationGist
)
from pyramid.security import authenticated_userid
import logging
from lingvodoc.cache.caching import TaskStatus
from pyramid.httpexceptions import (
    HTTPOk,
    HTTPBadRequest,
    HTTPUnauthorized
)
from lingvodoc.views.v2.desktop_sync.core import async_download_dictionary
import json
import requests
from pyramid.request import Request
from pyramid.response import Response

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

def download_dictionary(dict_id, request, user_id, locale_id):
    my_args = dict()
    my_args["client_id"] = dict_id[0]
    my_args["object_id"] = dict_id[1]
    my_args["central_server"] = request.registry.settings["desktop"]['central_server']
    my_args["storage"] = request.registry.settings["storage"]
    my_args['sqlalchemy_url'] = request.registry.settings["sqlalchemy.url"]
    my_args["cookies"] = json.loads(request.cookies.get('server_cookies'))
    try:
        dictionary_obj = DBSession.query(dbDictionary).filter_by(client_id=dict_id[0],
                                                               object_id=dict_id[1]).first()
        if not dictionary_obj:
            dict_json = make_request(my_args["central_server"] + 'dictionary/%s/%s' % (
                dict_id[0],
                dict_id[1]), my_args["cookies"])
            if dict_json.status_code != 200 or not dict_json.json():
                task = TaskStatus(user_id, "Dictionary sync with server", "dictionary name placeholder", 5)
            else:
                dict_json = dict_json.json()
                gist = DBSession.query(dbTranslationGist). \
                    filter_by(client_id=dict_json['translation_gist_client_id'],
                              object_id=dict_json['translation_gist_object_id']).first()
                if gist:
                    task = TaskStatus(user_id, "Dictionary sync with server", gist.get_translation(locale_id), 5)
                else:
                    task = TaskStatus(user_id, "Dictionary sync with server", "dictionary name placeholder", 5)

        else:
            gist = DBSession.query(dbTranslationGist). \
                filter_by(client_id=dictionary_obj.translation_gist_client_id,
                          object_id=dictionary_obj.translation_gist_object_id).first()
            task = TaskStatus(user_id, "Dictionary sync with server", gist.get_translation(locale_id), 5)
    except:
        raise ResponseError('bad request')
    my_args["task_key"] = task.key
    my_args["cache_kwargs"] = request.registry.settings["cache_kwargs"]
    res = async_download_dictionary.delay(**my_args)
    # async_convert_dictionary_new(user_id, req['blob_client_id'], req['blob_object_id'], req["language_client_id"], req["language_object_id"], req["gist_client_id"], req["gist_object_id"], request.registry.settings["sqlalchemy.url"], request.registry.settings["storage"])
    log.debug("Conversion started")


class DownloadDictionary(graphene.Mutation):
    """
    example:
    mutation {
        create_lexicalentry(id: [949,21], perspective_id: [71,5]) {
            field {
                id
            }
            triumph
        }
    }

    (this example works)
    returns:

    {
      "create_lexicalentry": {
        "field": {
          "id": [
            949,
            21
          ]
        },
        "triumph": true
      }
    }
    """

    class Arguments:
        id = LingvodocID(required=True)

    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):
        request = info.context.request
        path = request.route_url('basic_sync')
        subreq = Request.blank(path)
        subreq.method = 'POST'
        subreq.headers = request.headers
        resp = request.invoke_subrequest(subreq)
        if resp.status_code != 200:
            raise ResponseError('network error')
        request = info.context.request
        locale_id = int(request.cookies.get('locale_id') or 2)
        dict_id = args['id']
        variables = {'auth': authenticated_userid(request)}
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        user_id = user.id
        download_dictionary(dict_id, request, user_id, locale_id)

        return DownloadDictionary(triumph=True)

class DownloadDictionaries(graphene.Mutation):
    """
    example:
    mutation {
        create_lexicalentry(id: [949,21], perspective_id: [71,5]) {
            field {
                id
            }
            triumph
        }
    }

    (this example works)
    returns:

    {
      "create_lexicalentry": {
        "field": {
          "id": [
            949,
            21
          ]
        },
        "triumph": true
      }
    }
    """

    class Arguments:
        ids = graphene.List(LingvodocID, required=True)

    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):
        request = info.context.request

        path = request.route_url('basic_sync')
        subreq = Request.blank(path)
        subreq.method = 'POST'
        subreq.headers = request.headers
        resp = request.invoke_subrequest(subreq)
        if resp.status_code != 200:
            raise ResponseError('network error')
        locale_id = int(request.cookies.get('locale_id') or 2)
        ids = args['ids']
        variables = {'auth': authenticated_userid(request)}
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        user_id = user.id

        for dict_id in ids:
            download_dictionary(dict_id, request, user_id, locale_id)

        return DownloadDictionary(triumph=True)



class Synchronize(graphene.Mutation):


    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):
        print('locking client')
        log.error('locking client')

        request = info.context.request
        DBSession.execute("LOCK TABLE client IN EXCLUSIVE MODE;")
        variables = {'auth': authenticated_userid(request)}
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise ResponseError('try to login again')

        client_id = request.authenticated_userid
        user_id = Client.get_user_by_client_id(client_id).id

        is_admin = False
        if user_id == 1:
            is_admin = True

        task = TaskStatus(user_id, "Synchronisation with server", '', 16)
        task.set(1, 10, "Started", "")
        path = request.route_url('check_version')
        subreq = Request.blank(path)
        subreq.method = 'GET'
        subreq.headers = request.headers
        resp = request.invoke_subrequest(subreq)
        if resp.status_code != 200:
            raise ResponseError('network error 1')

        path = request.route_url('basic_sync')
        subreq = Request.blank(path)
        subreq.method = 'POST'
        subreq.headers = request.headers
        resp = request.invoke_subrequest(subreq)
        if resp.status_code != 200:
            raise ResponseError('network error 2')
        task.set(2, 15, "Basic synchronisation completed", "")

        path = request.route_url('diff_desk')
        subreq = Request.blank(path)
        subreq.method = 'POST'
        subreq.headers = request.headers
        subreq.json = {'task_key': task.key}
        log.error('before diff_desk')
        resp = request.invoke_subrequest(subreq)
        log.error('after diff_desk')
        if resp.status_code != 200:
            raise ResponseError('network error 3')
        task.set(15, 95, "All data uploaded to server", "")

        for dict_obj in DBSession.query(dbDictionary).all():
            path = request.route_url('download_dictionary')
            subreq = Request.blank(path)
            subreq.method = 'POST'
            subreq.headers = request.headers
            subreq.json = {"client_id": dict_obj.client_id,
                           "object_id": dict_obj.object_id}
            resp = request.invoke_subrequest(subreq)
            if resp.status_code != 200:
                raise ResponseError('network error 4')

        path = request.route_url('new_client')
        subreq = Request.blank(path)
        subreq.method = 'POST'
        subreq.headers = request.headers
        resp = request.invoke_subrequest(subreq)
        if resp.status_code != 200:
            raise ResponseError('network error 5')
        else:
            path = request.route_url('basic_sync')
            subreq = Request.blank(path)
            subreq.method = 'POST'
            subreq.headers = request.headers
            resp = request.invoke_subrequest(subreq)
            if resp.status_code != 200:
                raise ResponseError('network error 2')
            task.set(16, 100, "Synchronisation complete (New data still can be downloading from server, look a other tasks)", "")
            return Synchronize(triumph=True)