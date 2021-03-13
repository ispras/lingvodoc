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
from lingvodoc.utils.search import recursive_sort

from lingvodoc.utils.merge import merge_bulk_async, merge_bulk

log = logging.getLogger(__name__)


# there should be mutations for merging


class MergeBulk(graphene.Mutation):
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
        publish_any = graphene.Boolean(required=True)
        group_list = graphene.List(graphene.List(LingvodocID))
        async_execution = graphene.Boolean(required=True)

    triumph = graphene.Boolean()
    result_list = graphene.List(LingvodocID)

    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):
        group_list=args['group_list']
        async_execution = args['async']
        publish_any=args['publish_any']
        request = info.context.request
        old_group_list = [[{'client_id': xx[0], "object_id": xx[1]} for xx in x] for x in group_list]
        if async_execution:
            merge_bulk_async(request, publish_any, old_group_list)
            result_list = list()
        else:
            result_list = merge_bulk(request, publish_any, old_group_list)
        return MergeBulk(triumph=True, result_list=[[x['client_id'], x['object_id']] for x in result_list])
