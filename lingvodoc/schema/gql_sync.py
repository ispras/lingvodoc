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
        args = dict()
        locale_id = int(request.cookies.get('locale_id') or 2)
        dict_id = args['id']
        variables = {'auth': authenticated_userid(request)}
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        user_id = user.id

        args["client_id"] = dict_id[0]
        args["object_id"] = dict_id[1]
        args["central_server"] = request.registry.settings["desktop"]['central_server']
        args["storage"] = request.registry.settings["storage"]
        args['sqlalchemy_url'] = request.registry.settings["sqlalchemy.url"]
        args["cookies"] = json.loads(request.cookies.get('server_cookies'))
        try:
            dictionary_obj = DBSession.query(dbDictionary).filter_by(client_id=dict_id[0],
                                                                   object_id=dict_id[1]).first()
            if not dictionary_obj:
                dict_json = make_request(args["central_server"] + 'dictionary/%s/%s' % (
                    dict_id[0],
                    dict_id[1]), args["cookies"])
                if dict_json.status_code != 200 or not dict_json.json():
                    task = TaskStatus(user_id, "Dictionary sync with server", "dictionary name placeholder", 5)
                else:
                    dict_json = dict_json.json()
                    gist = DBSession.query(dbTranslationGist). \
                        filter_by(client_id=dict_json['translation_gist_client_id'],
                                  object_id=dict_json['translation_gist_object_id']).first()
                    task = TaskStatus(user_id, "Dictionary sync with server", gist.get_translation(locale_id), 5)

            else:
                gist = DBSession.query(dbTranslationGist). \
                    filter_by(client_id=dictionary_obj.translation_gist_client_id,
                              object_id=dictionary_obj.translation_gist_object_id).first()
                task = TaskStatus(user_id, "Dictionary sync with server", gist.get_translation(locale_id), 5)
        except:
            raise ResponseError('this should be impossible in graphql')
        args["task_key"] = task.key
        args["cache_kwargs"] = request.registry.settings["cache_kwargs"]
        res = async_download_dictionary.delay(**args)
        # async_convert_dictionary_new(user_id, req['blob_client_id'], req['blob_object_id'], req["language_client_id"], req["language_object_id"], req["gist_client_id"], req["gist_object_id"], request.registry.settings["sqlalchemy.url"], request.registry.settings["storage"])
        log.debug("Conversion started")
        return DownloadDictionary(triumph=True)