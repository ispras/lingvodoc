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

log = logging.getLogger(__name__)


# there should be mutations for merging
