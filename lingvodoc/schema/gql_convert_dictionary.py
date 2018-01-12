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
from lingvodoc.views.v2.convert_dictionary_dialeqt.core import async_convert_dictionary_new
import json
import requests
from pyramid.request import Request
from pyramid.response import Response

from lingvodoc.views.v2.utils import anonymous_userid
log = logging.getLogger(__name__)
from lingvodoc.utils.creation import create_gists_with_atoms

class ConvertDictionary(graphene.Mutation):
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
        dictionary_id = LingvodocID()
        blob_id = LingvodocID(required=True)
        language_id = LingvodocID()
        translation_gist_id = LingvodocID()
        translation_atoms = graphene.List(ObjectVal)

    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):
        request = info.context.request
        locale_id = int(request.cookies.get('locale_id') or 1)
        client_id = request.authenticated_userid
        if not client_id:
            user_id = anonymous_userid(request)
        else:
            user_id = Client.get_user_by_client_id(client_id).id
        cur_args = dict()
        if "dictionary_id" in args:
            cur_args["dictionary_client_id"] = args["dictionary_id"][0]
            cur_args["dictionary_object_id"] = args["dictionary_id"][1]
        else:
            cur_args["dictionary_client_id"] = None
            cur_args["dictionary_object_id"] = None
        cur_args["client_id"] = client_id
        cur_args['blob_client_id'] = args['blob_id'][0]
        cur_args['blob_object_id'] = args['blob_id'][1]
        if "language_id" in args:
            cur_args["language_client_id"] = args['language_id'][0]
            cur_args["language_object_id"] = args['language_id'][1]
        else:
            cur_args["language_client_id"] = None
            cur_args["language_object_id"] = None
        if "translation_gist_id" in args:
            cur_args["gist_client_id"] = args['translation_gist_id'][0]
            cur_args["gist_object_id"] = args['translation_gist_id'][1]
        elif "translation_atoms" in args:
            tr_atoms = args.get("translation_atoms")
            translation_gist_id = args.get('translation_gist_id')
            translation_gist_id = create_gists_with_atoms(tr_atoms, translation_gist_id, [client_id, None])
            cur_args["gist_client_id"] = translation_gist_id[0]
            cur_args["gist_object_id"] = translation_gist_id[1]
        else:
            cur_args["gist_client_id"] = None
            cur_args["gist_object_id"] = None
        cur_args["sqlalchemy_url"] = request.registry.settings["sqlalchemy.url"]
        cur_args["storage"] = request.registry.settings["storage"]
        cur_args["locale_id"] = locale_id
        cur_args["cache_kwargs"] = request.registry.settings["cache_kwargs"]
        gist = DBSession.query(dbTranslationGist).filter_by(client_id=cur_args["gist_client_id"],
                                                          object_id=cur_args["gist_object_id"]).first()
        try:
            if gist:
                task = TaskStatus(user_id, "Dialeqt dictionary conversion", gist.get_translation(locale_id), 10)

            else:
                dictionary_obj = DBSession.query(dbDictionary).filter_by(client_id=args["dictionary_id"][0],
                                                               object_id=args["dictionary_id"][1]).first()
                gist = DBSession.query(dbTranslationGist).\
                    filter_by(client_id=dictionary_obj.translation_gist_client_id,
                              object_id=dictionary_obj.translation_gist_object_id).first()
                task = TaskStatus(user_id, "Dialeqt dictionary conversion", gist.get_translation(locale_id), 10)
        except:
            raise ResponseError(message="wrong parameters")
        cur_args["task_key"] = task.key
        res = async_convert_dictionary_new.delay(**cur_args)
        return ConvertDictionary(triumph=True)