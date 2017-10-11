import graphene

from lingvodoc.schema.gql_entity import (
    Entity,
    CreateEntity,
    UpdateEntity,
    DeleteEntity,
    BulkCreateEntity
)
from lingvodoc.schema.gql_dictipersptofield import (
    DictionaryPerspectiveToField,
    CreateDictionaryPerspectiveToField,
    UpdateDictionaryPerspectiveToField,
    DeleteDictionaryPerspectiveToField
)
from lingvodoc.schema.gql_basegroup import (
    BaseGroup,
)
from lingvodoc.schema.gql_group import (
    Group
)
from lingvodoc.schema.gql_organization import (
    Organization,
    CreateOrganization,
    UpdateOrganization,
    DeleteOrganization
)
# from lingvodoc.schema.gql_publishingentity import (
#     PublishingEntity
# )
from lingvodoc.schema.gql_translationatom import (
    TranslationAtom,
    CreateTranslationAtom,
    UpdateTranslationAtom
)
from lingvodoc.schema.gql_translationgist import (
    TranslationGist,
    CreateTranslationGist,
    DeleteTranslationGist
)
from lingvodoc.schema.gql_userblobs import (
    UserBlobs,
    CreateUserBlob,
    DeleteUserBlob
)
from lingvodoc.schema.gql_field import (
    Field,
    CreateField,
    UpdateField,
    DeleteField
)

from lingvodoc.schema.gql_dictionary import (
    Dictionary,
    CreateDictionary,
    UpdateDictionary,
    UpdateDictionaryStatus,
    UpdateDictionaryRoles,
    DeleteDictionary
)

from lingvodoc.schema.gql_lexicalentry import (
    LexicalEntry,
    CreateLexicalEntry,
    DeleteLexicalEntry,
    BulkCreateLexicalEntry
)

from lingvodoc.schema.gql_language import (
    Language,
    CreateLanguage,
    UpdateLanguage,
    DeleteLanguage
)
from lingvodoc.schema.gql_dictionaryperspective import (
    DictionaryPerspective,
    CreateDictionaryPerspective,
    UpdateDictionaryPerspective,
    UpdatePerspectiveStatus,
    UpdatePerspectiveRoles,
    DeleteDictionaryPerspective
)
from lingvodoc.schema.gql_user import (
    User,
    CreateUser,
    UpdateUser
)
from lingvodoc.schema.gql_grant import (
    Grant,
    CreateGrant,
    UpdateGrant,
    DeleteGrant
)
# from lingvodoc.schema.gql_email import (
#     Email
# )
from lingvodoc.schema.gql_holders import (
    PermissionException,
    ResponseError,
    ObjectVal,
    client_id_check,
    LingvodocID
)

from lingvodoc.schema.gql_userrequest import (
    UserRequest,
    CreateGrantPermission,
    AddDictionaryToGrant,
    AdministrateOrg,
    ParticipateOrg,
    AcceptUserRequest,
    DeleteUserRequest
)

import lingvodoc.acl as acl

from lingvodoc.models import (
    DBSession,
    Dictionary as dbDictionary,
    DictionaryPerspective as dbPerspective,
    Language as dbLanguage,
    Organization as dbOrganization,
    Field as dbField,
    Group as dbGroup,
    BaseGroup as dbBaseGroup,
    User as dbUser,
    Entity as dbEntity,
    LexicalEntry as dbLexicalEntry,
    DictionaryPerspectiveToField as dbPerspectiveToField,
    Locale as dbLocale,
    TranslationAtom as dbTranslationAtom,
    TranslationGist as dbTranslationGist,
    Email as dbEmail,
    UserBlobs as dbUserBlobs,
    UserRequest as dbUserRequest,
    Grant as dbGrant,
    Client
)
from pyramid.request import Request

from sqlalchemy import (
    func,
    and_,
    or_,
    tuple_
)
from lingvodoc.views.v2.utils import (
    view_field_from_object,
)
from sqlalchemy.orm import aliased

from sqlalchemy.sql.functions import coalesce

from pyramid.security import authenticated_userid

from lingvodoc.utils.phonology import phonology as utils_phonology

RUSSIAN_LOCALE = 1
ENGLISH_LOCALE = 2


class Query(graphene.ObjectType):
    client = graphene.String()
    dictionaries = graphene.List(Dictionary, published=graphene.Boolean())
    dictionary = graphene.Field(Dictionary, id=LingvodocID())
    perspectives = graphene.List(DictionaryPerspective, published=graphene.Boolean())
    perspective = graphene.Field(DictionaryPerspective, id=LingvodocID())
    entity = graphene.Field(Entity, id=LingvodocID())
    language = graphene.Field(Language, id=LingvodocID())
    languages = graphene.List(Language)
    user = graphene.Field(User, id=graphene.Int())
    users = graphene.List(User, search=graphene.String())
    field = graphene.Field(Field, id=LingvodocID())
    translationgist = graphene.Field(TranslationGist, id=LingvodocID())
    userblob = graphene.Field(UserBlobs, id=LingvodocID())
    translationatom = graphene.Field(TranslationAtom, id=LingvodocID())
    organization = graphene.Field(Organization, id=LingvodocID())
    organizations = graphene.List(Organization)
    lexicalentry = graphene.Field(LexicalEntry, id=LingvodocID())
    lexicalentries = graphene.List(LexicalEntry, searchstring=graphene.String(), can_add_tags=graphene.Boolean(),
                                   perspective_id=LingvodocID(), field_id=LingvodocID(),
                                   search_in_published=graphene.Boolean())
    advanced_lexicalentries = graphene.List(LexicalEntry, searchstrings=graphene.List(ObjectVal),
                                            perspectives=LingvodocID(),
                                            adopted=graphene.Boolean(),
                                            adopted_type=LingvodocID(),
                                            with_entimology=graphene.Boolean())
    translationgists = graphene.List(TranslationGist)
    translation_search = graphene.List(TranslationGist, searchstring=graphene.String(), translation_type=graphene.String())
    translation_service_search = graphene.Field(TranslationGist, searchstring=graphene.String())
    advanced_translation_search = graphene.List(TranslationGist, searchstrings=graphene.List(graphene.String))
    all_locales = graphene.List(ObjectVal)
    user_blobs = graphene.List(UserBlobs, data_type=graphene.String(), is_global=graphene.Boolean())
    userrequest = graphene.Field(UserRequest, id=graphene.Int())
    userrequests = graphene.List(UserRequest)
    all_basegroups = graphene.List(BaseGroup)
    all_data_types = graphene.List(TranslationGist)
    all_fields = graphene.List(Field)
    all_statuses = graphene.List(TranslationGist)
    template_fields = graphene.List(Field, mode=graphene.String())
    template_modes = graphene.List(graphene.String)
    grant = graphene.Field(Grant, id=graphene.Int())
    grants = graphene.List(Grant)
    phonology = graphene.Field(graphene.Boolean, perspective_id=LingvodocID(),
        limit=graphene.Int(),
        limit_exception=graphene.Int(),
        limit_no_vowel=graphene.Int(),
        limit_result=graphene.Int(),
        group_by_description=graphene.Boolean(),
        only_first_translation=graphene.Boolean(),
        vowel_selection=graphene.Boolean(),
        maybe_tier_list=graphene.List(graphene.String),
        maybe_tier_set=graphene.List(graphene.String),
        synchronous=graphene.Boolean())

    def resolve_template_modes(self, info):
        return ['corpora']

    def resolve_template_fields(self, info, mode=None):
        response = list()
        request = info.context.request
        if mode == 'corpora':
            data_type_query = DBSession.query(dbField) \
                .join(dbTranslationGist,
                      and_(dbField.translation_gist_object_id == dbTranslationGist.object_id,
                           dbField.translation_gist_client_id == dbTranslationGist.client_id)) \
                .join(dbTranslationGist.translationatom)
            sound_field = data_type_query.filter(dbTranslationAtom.locale_id == 2,
                                                 dbTranslationAtom.content == 'Sound').one()  # todo: a way to find this fields if wwe cannot use one
            markup_field = data_type_query.filter(dbTranslationAtom.locale_id == 2,
                                                  dbTranslationAtom.content == 'Markup').one()
            comment_field = data_type_query.filter(dbTranslationAtom.locale_id == 2,
                                                    dbTranslationAtom.content == 'Comment').one()
            sound_field =view_field_from_object(request=request, field=sound_field)
            markup_field = view_field_from_object(request=request, field=markup_field)
            comment_field = view_field_from_object(request=request, field=comment_field)
            fake_id_1 = '6f355d7a-e68d-44ab-9cf6-36f78e8f1b34'  # chosen by fair dice roll
            fake_id_2 = '51fbe0b6-2cea-4d40-a994-f6bb6f501d48'  # guaranteed to be random
            f = Field(id=[sound_field["client_id"], sound_field["object_id"]], fake_id = fake_id_1)
            f2 = Field(id=[markup_field["client_id"], markup_field["object_id"]], fake_id = fake_id_2, self_fake_id = fake_id_1)
            f.dbObject = DBSession.query(dbField).filter_by(client_id=sound_field["client_id"], object_id=sound_field["object_id"]).first()
            f2.dbObject = DBSession.query(dbField).filter_by(client_id=markup_field["client_id"], object_id=markup_field["object_id"]).first()
            response.append(f)
            response.append(f2)

            f3 = Field(id=[comment_field["client_id"], comment_field["object_id"]])
            f3.dbObject = DBSession.query(dbField).filter_by(client_id=comment_field["client_id"]).first()
            response.append(f3)
            # response[0]['contains'] = [view_field_from_object(request=request, field=markup_field)]
            # response.append(view_field_from_object(request=request, field=markup_field))
            # response.append(view_field_from_object(request=request, field=comment_field))
            #
            # return response
            #
            # response.append(TranslationGist(id=[sound_field.translation_gist_client_id, sound_field.data_type_translation_gist_object_id]))
            # response.append(TranslationGist(id=[markup_field.data_type_translation_gist_client_id, markup_field.data_type_translation_gist_object_id]))
            # response.append(TranslationGist(id=[comment_field.data_type_translation_gist_client_id, comment_field.data_type_translation_gist_object_id]))
            return response
        else:
            raise ResponseError(message='no such mode')
    def resolve_all_statuses(self, info):
        request = info.context.request
        response = list()
        for status in ['WiP', 'Published', 'Limited access', 'Hidden']:
            subreq = Request.blank('/translation_service_search')
            subreq.method = 'POST'
            subreq.headers = request.headers
            subreq.json = {'searchstring': status}
            headers = {'Cookie': request.headers['Cookie']}
            subreq.headers = headers
            resp = request.invoke_subrequest(subreq)
            jn = resp.json
            response.append(TranslationGist(id=[jn["client_id"], jn["object_id"] ]))
        return response

    def resolve_all_fields(self, info):
        fields = DBSession.query(dbField).filter_by(marked_for_deletion=False).all() #todo: think about desktop and sync
        response = list()
        for field in fields:
            f = Field(id=[field.client_id, field.object_id],
                      translation=field.get_translation(info.context.get('locale_id'))
                      )
            #f.dbObject = field
            response.append(f)

        return response

    def resolve_all_data_types(self, info):
        import json
        request = info.context.request
        response = list()
        for data_type in ['Text', 'Image', 'Sound', 'Markup', 'Link', 'Grouping Tag']:
            subreq = Request.blank('/translation_service_search')
            subreq.method = 'POST'
            subreq.headers = request.headers
            subreq.json = {'searchstring': data_type}
            # headers = {'Cookie': request.headers['Cookie']}
            # subreq.headers = headers
            resp = request.invoke_subrequest(subreq)
            jn = resp.json
            #if "contains" in jn:
            #    del jn["contains"]
            response.append(TranslationGist(id=[jn["client_id"], jn["object_id"] ]))
        return response

    def resolve_dictionaries(self, info, published):
        """
        example:

        query DictionaryList {
            dictionaries(published: true) {
                id
                translation
                parent_id
                translation_gist_id
                state_translation_gist_id
                category
                domain
            }
        }
        """
        context = info.context
        dbdicts = list()
        request = context.get('request')
        if published:

            subreq = Request.blank('/translation_service_search')
            subreq.method = 'POST'
            subreq.headers = request.headers
            subreq.json = {'searchstring': 'Published'}
            headers = dict()
            if request.headers.get('Cookie'):
                headers = {'Cookie': request.headers['Cookie']}
            subreq.headers = headers
            resp = request.invoke_subrequest(subreq)

            if 'error' not in resp.json:
                state_translation_gist_object_id, state_translation_gist_client_id = resp.json['object_id'], resp.json[
                    'client_id']
            else:
                raise KeyError("Something wrong with the base", resp.json['error'])

            subreq = Request.blank('/translation_service_search')
            subreq.method = 'POST'
            subreq.headers = request.headers
            subreq.json = {'searchstring': 'Limited access'}  # todo: fix
            headers = dict()
            if request.headers.get('Cookie'):
                headers = {'Cookie': request.headers['Cookie']}
            subreq.headers = headers
            resp = request.invoke_subrequest(subreq)

            if 'error' not in resp.json:
                limited_object_id, limited_client_id = resp.json['object_id'], resp.json['client_id']
            else:
                raise KeyError("Something wrong with the base", resp.json['error'])

            dbdicts = DBSession.query(dbDictionary).filter(
                or_(and_(dbDictionary.state_translation_gist_object_id == state_translation_gist_object_id,
                         dbDictionary.state_translation_gist_client_id == state_translation_gist_client_id),
                    and_(dbDictionary.state_translation_gist_object_id == limited_object_id,
                         dbDictionary.state_translation_gist_client_id == limited_client_id))). \
                join(dbPerspective) \
                .filter(or_(and_(dbPerspective.state_translation_gist_object_id == state_translation_gist_object_id,
                                 dbPerspective.state_translation_gist_client_id == state_translation_gist_client_id),
                            and_(dbPerspective.state_translation_gist_object_id == limited_object_id,
                                 dbPerspective.state_translation_gist_client_id == limited_client_id))). \
                filter(dbPerspective.marked_for_deletion == False).all()

        else:
            dbdicts = DBSession.query(dbDictionary).filter(dbPerspective.marked_for_deletion == False).all()

        dictionaries_list = [Dictionary(id=[dbdict.client_id, dbdict.object_id],
                                        parent_id=[dbdict.parent_client_id, dbdict.parent_object_id],
                                        translation_gist_id=[dbdict.translation_gist_client_id, dbdict.translation_gist_object_id],
                                        state_translation_gist_id=[dbdict.state_translation_gist_client_id, dbdict.state_translation_gist_object_id],
                                        category=dbdict.category,
                                        domain=dbdict.domain,
                                        translation=dbdict.get_translation(context.get('locale_id'))) for dbdict in dbdicts]
        return dictionaries_list

    def resolve_dictionary(self, info, id):
        return Dictionary(id=id)

    def resolve_perspectives(self,info, published):
        """
        example:

        query LanguagesList {
            perspectives(published: true) {
                id
                translation
                parent_id
                translation_gist_id
                state_translation_gist_id
                import_source
                import_hash
            }
        }
        """
        context = info.context
        request = context.get('request')
        cookies = info.context.get('cookies')
        if published:
            subreq = Request.blank('/translation_service_search')
            subreq.method = 'POST'
            subreq.headers = request.headers
            subreq.json = {'searchstring': 'Published'}
            headers = {'Cookie': cookies}
            subreq.headers = headers
            resp = request.invoke_subrequest(subreq)
            if 'error' not in resp.json:
                state_translation_gist_object_id, state_translation_gist_client_id = resp.json['object_id'], resp.json[
                    'client_id']
            else:
                raise KeyError("Something wrong with the base", resp.json['error'])

            subreq = Request.blank('/translation_service_search')
            subreq.method = 'POST'
            subreq.headers = request.headers
            subreq.json = {'searchstring': 'Limited access'}
            headers = {'Cookie': cookies}
            subreq.headers = headers
            resp = request.invoke_subrequest(subreq)
            if 'error' not in resp.json:
                limited_object_id, limited_client_id = resp.json['object_id'], resp.json[
                    'client_id']
            else:
                raise KeyError("Something wrong with the base", resp.json['error'])

            """
            atom_perspective_name_alias = aliased(dbTranslationAtom, name="PerspectiveName")
            atom_perspective_name_fallback_alias = aliased(dbTranslationAtom, name="PerspectiveNameFallback")
            persps = DBSession.query(dbPerspective,
                                     dbTranslationAtom,
                                     coalesce(atom_perspective_name_alias.content,
                                              atom_perspective_name_fallback_alias.content,
                                              "No translation for your locale available").label("Translation")
                                     ).filter(dbPerspective.marked_for_deletion == False)
            """
            persps = DBSession.query(dbPerspective).filter(
                or_(and_(dbPerspective.state_translation_gist_object_id == state_translation_gist_object_id,
                         dbPerspective.state_translation_gist_client_id == state_translation_gist_client_id),
                    and_(dbPerspective.state_translation_gist_object_id == limited_object_id,
                         dbDictionary.state_translation_gist_client_id == limited_client_id))). \
                filter(dbPerspective.marked_for_deletion == False).all()
        else:
            persps = DBSession.query(dbPerspective).filter(dbPerspective.marked_for_deletion == False).all()

        perspectives_list = [DictionaryPerspective(id=[persp.client_id, persp.object_id],
                                                   parent_id=[persp.parent_client_id, persp.parent_object_id],
                                                   translation_gist_id=[persp.translation_gist_client_id, persp.translation_gist_object_id],
                                                   state_translation_gist_id=[persp.state_translation_gist_client_id, persp.state_translation_gist_object_id],
                                                   import_source=persp.import_source, import_hash=persp.import_hash,
                                                   translation=persp.get_translation(context.get('locale_id'))) for persp in persps]
        return perspectives_list


    def resolve_perspective(self, info, id):
        return DictionaryPerspective(id=id)

    def resolve_language(self, info, id):
        return Language(id=id)

    def resolve_languages(self, info):
        """
        example:

        query LanguagesList {
            languages {
                id
                translation
                parent_id
                translation_gist_id
            }
        }
        """
        context = info.context

        languages = DBSession.query(dbLanguage).filter(dbLanguage.marked_for_deletion == False).all()
        languages_list = [Language(id=[lang.client_id, lang.object_id],
                                   parent_id=[lang.parent_client_id, lang.parent_object_id],
                                   translation_gist_id=[lang.translation_gist_client_id, lang.translation_gist_object_id],
                                   translation=lang.get_translation(context.get('locale_id'))) for lang in languages]
        return languages_list

    def resolve_entity(self, info, id):
        return Entity(id=id)

    def resolve_user(self, info, id):
        return User(id=id)

    def resolve_users(self, info, search):
        """
        example:

        query UsersList {
            users(search: "modis") {
                login
                name
                intl_name
            }
        }
        """
        users = DBSession.query(dbUser).join(dbUser.email)
        if search:
            name = search + '%'
            users = users.filter(or_(
                dbUser.name.startswith(name),
                dbUser.login.startswith(name),
                dbUser.intl_name.startswith(name),
                dbEmail.email.startswith(name)
            ))
        users_list = [User(name=user.name,
                           intl_name=user.intl_name, login=user.login) for user in users]
        return users_list


    # def resolve_datetime(self, args, context, info):
    #     id = args.get('id')
    #     return DateTime(id=id)

    def resolve_basegroup(self, info, id):
        return BaseGroup(id=id)

    def resolve_client(self, info):
        context = info.context
        return context.get('client')

    def resolve_dictionaryperspectivetofield(self, info, id):
        return DictionaryPerspectiveToField(id=id)


    def resolve_grant(self, info, id):
        return Grant(id=id)

    def resolve_group(self, info, id):
        return Group(id=id)

    def resolve_organization(self, info, id):
        return Organization(id=id)

    def resolve_organizations(self, info):
        organizations = DBSession.query(dbOrganization).filter_by(marked_for_deletion=False).all()
        organizations_list = [Organization(id=organization.id,
                                           name=organization.name,
                                           about=organization.about) for organization in organizations]
        return organizations_list

    # def resolve_passhash(self, args, context, info):
    #     id = args.get('id')
    #     return Passhash(id=id)

    # def resolve_objecttoc(self, args, context, info):
    #     id = args.get('id')
    #     return ObjectTOC(id=id)


    def resolve_translationatom(self, info, id):
        return TranslationAtom(id=id)

    def resolve_translationgist(self, info, id):
        return TranslationGist(id=id)

    def resolve_translationgists(self, info):
        """
        example:
        query GistsList {
            translationgists {
                id
                type
            }
        }
        """

        gists = DBSession.query(dbTranslationGist).order_by(dbTranslationGist.type).all()
        gists_list = [TranslationGist(id=[gist.client_id, gist.object_id],
                                      type=gist.type) for gist in gists]
        return gists_list

    def resolve_translation_search(self, info, searchstring, translation_type=None):
        """
        query TranslationsList {
            translation_search(searchstring: "словарь") {
                id
                type
                translationatoms {
                     id
                     content
                }
            }
        }
        """
        translationatoms = DBSession.query(dbTranslationAtom).filter(dbTranslationAtom.content.like('%' + searchstring + '%'))
        if translation_type:
            translationatoms = translationatoms.join(dbTranslationGist).filter(dbTranslationGist.type == translation_type).all()
        else:
            translationatoms = translationatoms.all()

        translationgists = list()
        for translationatom in translationatoms:
            parent = translationatom.parent
            if parent not in translationgists:
                translationgists.append(parent)

        if translationgists:
            translationgists_list = list()
            for translationgist in translationgists:
                translationatoms_list = list()
                for translationatom in translationgist.translationatom:
                    translationatom_object = TranslationAtom(id=[translationatom.client_id, translationatom.object_id],
                                                             parent_id=[translationatom.parent_client_id,
                                                                        translationatom.parent_object_id],
                                                             content=translationatom.content,
                                                             locale_id=translationatom.locale_id,
                                                             created_at=translationatom.created_at
                                                             )
                    translationatoms_list.append(translationatom_object)
                translationgist_object = TranslationGist(id=[translationgist.client_id, translationgist.object_id],
                                                         type=translationgist.type,
                                                         created_at=translationgist.created_at,
                                                         translationatoms=translationatoms_list)
                translationgists_list.append(translationgist_object)
            return translationgists_list
        raise ResponseError(message="Error: no result")

    def resolve_translation_service_search(self, info, searchstring):
        """
        query TranslationsList {
            translation_service_search(searchstring: "Converting 80%") {
                id
                type
                translationatoms {
                     id
                     content
                }
            }
        }
        """
        translationatom = DBSession.query(dbTranslationAtom) \
            .join(dbTranslationGist). \
            filter(dbTranslationAtom.content == searchstring,
                   dbTranslationAtom.locale_id == 2,
                   dbTranslationGist.type == 'Service') \
            .one()
        if translationatom and translationatom.parent:
            translationgist = translationatom.parent

            translationatoms_list = list()
            for translationatom in translationgist.translationatom:
                translationatom_object = TranslationAtom(id=[translationatom.client_id, translationatom.object_id],
                                                         parent_id=[translationatom.parent_client_id,
                                                                    translationatom.parent_object_id],
                                                         content=translationatom.content,
                                                         locale_id=translationatom.locale_id,
                                                         created_at=translationatom.created_at
                                                         )
                translationatoms_list.append(translationatom_object)
            translationgist_object = TranslationGist(id=[translationgist.client_id, translationgist.object_id],
                                                     type=translationgist.type,
                                                     created_at=translationgist.created_at,
                                                     translationatoms=translationatoms_list)
            return translationgist_object
        raise ResponseError(message="Error: no result")

    def resolve_advanced_translation_search(self, info, searchstrings):
        """
        query TranslationsList {
            advanced_translation_search(searchstrings: ["Converting 80%", "Available dictionaries"]) {
                id
                type
                translationatoms {
                     id
                     content
                }
            }
        }
        """
        if not searchstrings[0]:
            raise ResponseError(message="Error: no search strings")

        translationatoms = DBSession.query(dbTranslationAtom) \
            .join(dbTranslationGist). \
            filter(dbTranslationAtom.content.in_(searchstrings),
                   dbTranslationAtom.locale_id == 2,
                   dbTranslationGist.type == 'Service') \
            .all()

        translationgists = list()
        for translationatom in translationatoms:
            parent = translationatom.parent
            if parent not in translationgists:
                translationgists.append(parent)

        if translationgists:
            translationgists_list = list()
            for translationgist in translationgists:
                translationatoms_list = list()
                for translationatom in translationgist.translationatom:
                    translationatom_object = TranslationAtom(id=[translationatom.client_id, translationatom.object_id],
                                                             parent_id=[translationatom.parent_client_id,
                                                                        translationatom.parent_object_id],
                                                             content=translationatom.content,
                                                             locale_id=translationatom.locale_id,
                                                             created_at=translationatom.created_at
                                                             )
                    translationatoms_list.append(translationatom_object)
                translationgist_object = TranslationGist(id=[translationgist.client_id, translationgist.object_id],
                                                         type=translationgist.type,
                                                         created_at=translationgist.created_at,
                                                         translationatoms=translationatoms_list)
                translationgists_list.append(translationgist_object)
            return translationgists_list
        raise ResponseError(message="Error: no result")

    def resolve_userblob(self, info, id):
        return UserBlobs(id=id)

    def resolve_field(self, info, id):
        client_id = info.context.get("client_id")
        return Field(id=id)

    def resolve_lexicalentry(self, info, id):
        return LexicalEntry(id=id)

    def resolve_all_locales(self, info):
        response = list()
        locales = DBSession.query(dbLocale).all()
        for locale in locales:
            locale_json = dict()
            locale_json['shortcut'] = locale.shortcut
            locale_json['intl_name'] = locale.intl_name
            locale_json['created_at'] = locale.created_at
            locale_json['id'] = locale.id
            response.append(locale_json)
        return response


    def resolve_lexicalentries(self, info, searchstring, search_in_published, field_id=None, perspective_id=None, can_add_tags=None): #basic_search() function
        """
        query EntriesList {
            lexicalentries(searchstring: "следить", search_in_published: true) {
                id
                entities {
                     id
                     content
                }
            }
        }

        """

        if searchstring:
            if len(searchstring) >= 1:
                field = None
                if field_id:
                    field_client_id, field_object_id = field_id[0], field_id[1]
                    field = DBSession.query(dbField).filter_by(client_id=field_client_id, object_id=field_object_id).first()

                client_id = info.context.get('client_id')
                group = DBSession.query(dbGroup).filter(dbGroup.subject_override == True).join(dbBaseGroup) \
                    .filter(dbBaseGroup.subject == 'lexical_entries_and_entities', dbBaseGroup.action == 'view') \
                    .join(dbUser, dbGroup.users).join(Client) \
                    .filter(Client.id == client_id).first()

                published_cursor = None

                if group:
                    results_cursor = DBSession.query(dbEntity).filter(dbEntity.content.like('%'+searchstring+'%'), dbEntity.marked_for_deletion == False)
                    if perspective_id:
                        perspective_client_id, perspective_object_id = perspective_id
                        results_cursor = results_cursor.join(dbLexicalEntry) \
                            .join(dbPerspective) \
                            .filter(dbPerspective.client_id == perspective_client_id,
                                    dbPerspective.object_id == perspective_object_id)
                else:
                    results_cursor = DBSession.query(dbEntity) \
                        .join(dbEntity.parent) \
                        .join(dbPerspective)

                    if not perspective_id:
                        published_cursor = results_cursor

                    ignore_groups = False
                    request = info.context.get('request')
                    subreq = Request.blank('/translation_service_search')
                    subreq.method = 'POST'
                    subreq.headers = request.headers
                    subreq.json = {'searchstring': 'Published'}
                    headers = dict()
                    if request.headers.get('Cookie'):
                        headers = {'Cookie': request.headers['Cookie']}
                    subreq.headers = headers
                    resp = request.invoke_subrequest(subreq)

                    if 'error' not in resp.json:
                        state_translation_gist_object_id, state_translation_gist_client_id = resp.json['object_id'], \
                                                                                             resp.json['client_id']
                    else:
                        raise KeyError("Something wrong with the base", resp.json['error'])

                    if perspective_id:
                        perspective_client_id, perspective_object_id = perspective_id
                        results_cursor = results_cursor.filter(dbPerspective.client_id == perspective_client_id,
                                                               dbPerspective.object_id == perspective_object_id)
                        persp = DBSession.query(dbPerspective).filter_by(client_id=perspective_client_id,
                                                                                 object_id=perspective_object_id).first()
                        if persp and persp.state_translation_gist_client_id == state_translation_gist_client_id and persp.state_translation_gist_object_id == state_translation_gist_object_id:
                            ignore_groups = True
                    else:
                        published_cursor = results_cursor

                    if not ignore_groups:
                        results_cursor = results_cursor.join(dbGroup, and_(
                            dbPerspective.client_id == dbGroup.subject_client_id,
                            dbPerspective.object_id == dbGroup.subject_object_id)) \
                            .join(dbBaseGroup) \
                            .join(dbUser, dbGroup.users) \
                            .join(Client) \
                            .filter(Client.id == client_id,
                                    dbEntity.content.like('%' + searchstring + '%'), dbEntity.marked_for_deletion == False)
                    else:
                        results_cursor = results_cursor.filter(dbEntity.content.like('%' + searchstring + '%'),
                                                               dbEntity.marked_for_deletion == False)
                    if published_cursor:
                        published_cursor = published_cursor \
                            .join(dbPerspective.parent).filter(
                            dbDictionary.state_translation_gist_object_id == state_translation_gist_object_id,
                            dbDictionary.state_translation_gist_client_id == state_translation_gist_client_id,
                            dbPerspective.state_translation_gist_object_id == state_translation_gist_object_id,
                            dbPerspective.state_translation_gist_client_id == state_translation_gist_client_id,
                            dbEntity.content.like('%' + searchstring + '%'))

                    if can_add_tags:
                        results_cursor = results_cursor \
                            .filter(dbBaseGroup.subject == 'lexical_entries_and_entities',
                                    or_(dbBaseGroup.action == 'create', dbBaseGroup.action == 'view')) \
                            .group_by(dbEntity).having(func.count('*') == 2)
                    else:
                        results_cursor = results_cursor.filter(dbBaseGroup.subject == 'lexical_entries_and_entities',
                                                       dbBaseGroup.action == 'view')

                    if field:
                        results_cursor = results_cursor.join(dbPerspective.dictionaryperspectivetofield).filter(
                            dbPerspectiveToField.field == field)
                        if published_cursor:
                            published_cursor = published_cursor.join(
                                dbPerspective.dictionaryperspectivetofield).filter(
                                dbPerspectiveToField.field == field)

                    entries = list()

                    for item in results_cursor:
                        if item.parent not in entries:
                            entries.append(item.parent)
                    if published_cursor:
                        for item in published_cursor:
                            if item.parent not in entries:
                                entries.append(item.parent)

                    lexical_entries = list()
                    for entry in entries:
                        if not entry.marked_for_deletion:
                            if (entry.parent_client_id, entry.parent_object_id) in dbPerspective.get_deleted():
                                continue
                            if (entry.parent_client_id, entry.parent_object_id) in dbPerspective.get_hidden():
                                continue
                            lexical_entries.append(entry.track(search_in_published, info.context["locale_id"]))

                    lexical_entries_list = list()
                    for entry in lexical_entries:
                        entities = []
                        for ent in entry['contains']:
                            del ent["contains"]
                            del ent["level"]
                            del ent["accepted"]
                            del ent["published"]
                            if "link_client_id" in ent and "link_object_id" in ent:
                                ent["link_id"] = (ent["link_client_id"], ent["link_object_id"])
                            else:
                                ent["link_id"] = None
                            ent["field_id"] = (ent["field_client_id"], ent["field_object_id"])
                            if "self_client_id" in ent and "self_object_id" in ent:
                                ent["self_id"] = (ent["self_client_id"], ent["self_object_id"])
                            else:
                                ent["self_id"] = None
                            if "content" not in ent:
                                ent["content"] = None
                            if "additional_metadata" in ent:

                                ent["additional_metadata_string"] = ent["additional_metadata"]
                                del ent["additional_metadata"]
                            if 'entity_type' in ent:
                                del ent['entity_type']
                            gr_entity_object = Entity(id=[ent['client_id'],
                                                          ent['object_id']],
                                                      # link_id = (ent["link_client_id"], ent["link_object_id"]),
                                                      parent_id=(ent["parent_client_id"], ent["parent_object_id"]),
                                                      **ent  # all other args from sub_result
                                                      )
                            entities.append(gr_entity_object)
                        del entry["published"]
                        del entry["contains"]
                        del entry["level"]
                        gr_lexicalentry_object = LexicalEntry(id=[entry['client_id'],
                                                                  entry['object_id']],
                                                              entities=entities, **entry)

                        lexical_entries_list.append(gr_lexicalentry_object)
                    return lexical_entries_list
            raise ResponseError(message="Bad string")

    def resolve_advanced_lexicalentries(self, info, searchstrings, perspectives=None, adopted=None,
                                        adopted_type=None, with_etimology=None): #advanced_search() function

        """
        query EntriesList {
            advanced_lexicalentries(searchstrings: [{searchstring: "смотреть следить"}]) {
                id
                entities {
                     id
                     content
                }
            }
        }

        """
        request = info.context.get('request')
        cookies = info.context.get('cookies')
        headers = info.context.get('headers')

        if not perspectives:
            subreq = Request.blank('/translation_service_search')
            subreq.method = 'POST'
            subreq.headers = request.headers
            subreq.json = {'searchstring': 'Published'}
            headers = {'Cookie': cookies}
            subreq.headers = headers
            resp = request.invoke_subrequest(subreq)
            if 'error' not in resp.json:
                state_translation_gist_object_id, state_translation_gist_client_id = resp.json['object_id'], \
                                                                                     resp.json[
                                                                                         'client_id']
                published_gist = (state_translation_gist_client_id, state_translation_gist_object_id)
            else:
                raise KeyError("Something wrong with the base", resp.json['error'])
            subreq = Request.blank('/translation_service_search')
            subreq.method = 'POST'
            subreq.headers = request.headers
            subreq.json = {'searchstring': 'Limited access'}
            headers = {'Cookie': cookies}
            subreq.headers = headers
            resp = request.invoke_subrequest(subreq)
            if 'error' not in resp.json:
                state_translation_gist_object_id, state_translation_gist_client_id = resp.json['object_id'], \
                                                                                     resp.json[
                                                                                         'client_id']
                limited_gist = (state_translation_gist_client_id, state_translation_gist_object_id)
            else:
                raise KeyError("Something wrong with the base", resp.json['error'])

            perspectives = [(persp.client_id, persp.object_id) for persp in DBSession.query(dbPerspective).filter(
                dbPerspective.marked_for_deletion == False,
                or_(and_(dbPerspective.state_translation_gist_client_id == published_gist[0],
                         dbPerspective.state_translation_gist_object_id == published_gist[1]),
                    and_(dbPerspective.state_translation_gist_client_id == limited_gist[0],
                         dbPerspective.state_translation_gist_object_id == limited_gist[1]))).all()]

        def make_query(searchstring, perspectives):
            results_cursor = DBSession.query(dbLexicalEntry).join(dbEntity.parent) \
                .join(dbEntity.field).join(dbTranslationAtom,
                                         and_(dbField.translation_gist_client_id == dbTranslationAtom.parent_client_id,
                                              dbField.translation_gist_object_id == dbTranslationAtom.parent_object_id,
                                              dbField.marked_for_deletion == False)) \
                .distinct(dbEntity.parent_client_id, dbEntity.parent_object_id)
            if perspectives:
                results_cursor = results_cursor.filter(
                    tuple_(dbLexicalEntry.parent_client_id, dbLexicalEntry.parent_object_id).in_(perspectives))
            if not searchstring["searchstring"]:
                raise ResponseError(message="Error: bad argument 'searchstring'.")
            search_parts = searchstring["searchstring"].split()
            search_expression = dbEntity.content.like('%' + search_parts[0] + '%')
            to_do_or = searchstring.get('search_by_or', True)

            for part in search_parts[1:]:
                search_expression = or_(search_expression, dbEntity.content.like('%' + part + '%'))
            if 'entity_type' in searchstring and searchstring['entity_type']:
                search_expression = and_(search_expression, dbField.client_id == searchstring['entity_type'][0],
                                         dbField.object_id == searchstring['entity_type'][1])

            results_cursor = results_cursor.filter(search_expression)
            return results_cursor, to_do_or

        if not searchstrings[0]:
            raise ResponseError(message="Error: bad argument 'searchstrings'")

        results_cursor, to_do_or = make_query(searchstrings[0], perspectives)

        pre_results = set(results_cursor.all())
        if adopted:
            results_cursor = DBSession.query(dbLexicalEntry).join(dbEntity.parent).filter(
                dbEntity.content.like('%заим.%'))
            if adopted_type:
                results_cursor = results_cursor.join(dbEntity.field) \
                    .join(dbTranslationAtom,
                          and_(dbField.translation_gist_client_id == dbTranslationAtom.parent_client_id,
                               dbField.translation_gist_object_id == dbTranslationAtom.parent_object_id,
                               dbField.marked_for_deletion == False)) \
                    .filter(dbTranslationAtom.content == adopted_type,
                            dbTranslationAtom.locale_id == 2)
            pre_results = pre_results & set(results_cursor.all())
        if with_etimology:
            results_cursor = DBSession.query(dbLexicalEntry).join(dbEntity.parent).join(dbEntity.field) \
                .join(dbTranslationAtom,
                      and_(dbField.data_type_translation_gist_client_id == dbTranslationAtom.parent_client_id,
                           dbField.data_type_translation_gist_object_id == dbTranslationAtom.parent_object_id,
                           dbField.marked_for_deletion == False)) \
                .filter(dbTranslationAtom.content == 'Grouping Tag',
                        dbTranslationAtom.locale_id == 2)

        pre_results = pre_results & set(results_cursor.all())

        for search_string in searchstrings[1:]:
            results_cursor, to_do_or_new = make_query(search_string, perspectives)
            if to_do_or:
                pre_results = pre_results | set(results_cursor.all())
            else:
                pre_results = pre_results & set(results_cursor.all())
            to_do_or = to_do_or_new

        lexes_composite_list = [(lex.created_at,
                                 lex.client_id, lex.object_id, lex.parent_client_id, lex.parent_object_id,
                                 lex.marked_for_deletion, lex.additional_metadata,
                                 lex.additional_metadata.get('came_from')
                                 if lex.additional_metadata and 'came_from' in lex.additional_metadata else None)
                                for lex in pre_results]

        lexical_entries = dbLexicalEntry.track_multiple(lexes_composite_list, int(request.cookies.get('locale_id') or 2),
                                              publish=True, accept=True)

        lexical_entries_list = list()
        for entry in lexical_entries:
            entities = []
            for ent in entry['contains']:
                del ent["contains"]
                del ent["level"]
                del ent["accepted"]
                del ent["published"]
                if "link_client_id" in ent and "link_object_id" in ent:
                    ent["link_id"] = (ent["link_client_id"], ent["link_object_id"])
                else:
                    ent["link_id"] = None
                ent["field_id"] = (ent["field_client_id"], ent["field_object_id"])
                if "self_client_id" in ent and "self_object_id" in ent:
                    ent["self_id"] = (ent["self_client_id"], ent["self_object_id"])
                else:
                    ent["self_id"] = None
                if "content" not in ent:
                    ent["content"] = None
                if "additional_metadata" in ent:
                    ent["additional_metadata_string"] = ent["additional_metadata"]
                    del ent["additional_metadata"]
                if 'entity_type' in ent:
                    del ent['entity_type']

                gr_entity_object = Entity(id=[ent['client_id'],
                                              ent['object_id']],
                                          # link_id = (ent["link_client_id"], ent["link_object_id"]),
                                          parent_id=(ent["parent_client_id"], ent["parent_object_id"]),
                                          **ent  # all other args from sub_result
                                          )
                entities.append(gr_entity_object)

            del entry["published"]
            del entry["contains"]
            del entry["level"]
            gr_lexicalentry_object = LexicalEntry(id=[entry['client_id'],
                                                      entry['object_id']],
                                                  entities=entities, **entry)

            lexical_entries_list.append(gr_lexicalentry_object)
        return lexical_entries_list

    @client_id_check()
    def resolve_user_blobs(self, info, data_type=None, is_global=None):
        allowed_global_types = ["sociolinguistics"]
        client_id = info.context.get('client_id')
        client = DBSession.query(Client).filter_by(id=client_id).first()
        if data_type:
            if not is_global:
                user_blobs = DBSession.query(dbUserBlobs).filter_by(user_id=client.user_id, data_type=data_type).all()
            else:
                if data_type in allowed_global_types:
                    user_blobs = DBSession.query(dbUserBlobs).filter_by(data_type=data_type).all()
                else:
                    raise ResponseError(message="Error: you can not list that data type globally.")
        else:
            user_blobs = DBSession.query(dbUserBlobs).filter_by(user_id=client.user_id).all()
        user_blobs_list = [UserBlobs(id=[blob.client_id, blob.object_id],
                                     name=blob.name,
                                     content=blob.content,
                                     data_type=blob.data_type,
                                     created_at=blob.created_at) for blob in user_blobs]
        return user_blobs_list

    def resolve_userrequest(self, info, id):
        """
        query myQuery {
          userrequest(id: 6) {
                id
           }
        }
        """
        return UserRequest(id=id)

    #@client_id_check()
    def resolve_userrequests(self, info):
        """
        query myQuery {
          userrequests {
                id
                sender_id
                type
           }
        }
        """
        client_id = info.context.get('client_id')

        client = DBSession.query(Client).filter_by(id=client_id).first()
        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        if not user:
            raise ResponseError(message="This client id is orphaned. Try to logout and then login once more.")

        userrequests = DBSession.query(dbUserRequest).filter(dbUserRequest.recipient_id == user.id).order_by(
            dbUserRequest.created_at).all()

        userrequests_list = [UserRequest(id=userrequest.id,
                                         sender_id=userrequest.sender_id,
                                         recipient_id=userrequest.recipient_id,
                                         broadcast_uuid=userrequest.broadcast_uuid,
                                         type=userrequest.type,
                                         subject=userrequest.subject,
                                         message=userrequest.message,
                                         created_at=userrequest.message) for userrequest in userrequests]

        return userrequests_list

    def resolve_all_basegroups(self, info):  # tested
        basegroups = list()
        for basegroup_object in DBSession.query(dbBaseGroup).all():
            basegroup = BaseGroup(id=basegroup_object.id)
            basegroup.dbObject = basegroup_object
            basegroups.append(basegroup)
        return basegroups

    def resolve_grant(self, info, id):
        grant = DBSession.query(dbGrant).filter_by(id=id).first()
        if not grant:
            raise ResponseError(message="No such grant in the system")

        return Grant(id=grant.id,
                     issuer_translation_gist_id=[grant.issuer_translation_gist_client_id, grant.issuer_translation_gist_object_id],
                     translation_gist_id=[grant.translation_gist_client_id, grant.translation_gist_object_id],
                     issuer_url=grant.issuer_url,
                     grant_number=grant.grant_number,
                     owners=grant.owners,
                     begin=grant.begin.strftime("%d.%m.%Y"),
                     end=grant.end.strftime("%d.%m.%Y"),
                     created_at=grant.created_at)

    def resolve_grants(self, info):
        """
        query myQuery {
          grants {
                id
           }
        }
        """
        grants = DBSession.query(dbGrant).order_by(dbGrant.grant_number).all()

        grants_list = [Grant(id=grant.id,
                     issuer_translation_gist_id=[grant.issuer_translation_gist_client_id, grant.issuer_translation_gist_object_id],
                     translation_gist_id=[grant.translation_gist_client_id, grant.translation_gist_object_id],
                     issuer_url=grant.issuer_url,
                     grant_number=grant.grant_number,
                     owners=grant.owners,
                     begin=grant.begin.strftime("%d.%m.%Y"),
                     end=grant.end.strftime("%d.%m.%Y"),
                     created_at=grant.created_at) for grant in grants]
        return grants_list

    def resolve_phonology(self, info, perspective_id, group_by_description, only_first_translation,
                          vowel_selection, maybe_tier_list, maybe_tier_set=None, limit=None,
                            limit_exception=None, limit_no_vowel=None, limit_result=None, synchronous=False):
        """
        query MyQuery {
           phonology(perspective_id: [671, 15155], group_by_description: false, only_first_translation: false, vowel_selection: false, maybe_tier_list: [])
        }
        """
        perspective_cid, perspective_oid = perspective_id
        locale_id = info.context.get('locale_id')
        request = info.context.get('request')

        utils_phonology(request, group_by_description, only_first_translation, perspective_cid, perspective_oid,
                  synchronous, vowel_selection, maybe_tier_list, maybe_tier_set, limit,
                  limit_exception, limit_no_vowel, limit_result, locale_id)

        return True


class MyMutations(graphene.ObjectType):
    """
    Mutation classes.
    It may be replaced by
    create_field = gql_field.CreateField.Field()
    for more beautiful imports
    """
    create_field = CreateField.Field()
    update_field = UpdateField.Field()
    delete_field = DeleteField.Field()
    create_entity = CreateEntity.Field()
    update_entity = UpdateEntity.Field()
    delete_entity = DeleteEntity.Field()
    bulk_create_entity = BulkCreateEntity.Field()
    create_user = CreateUser.Field()
    update_user = UpdateUser.Field()
    create_language = CreateLanguage.Field()
    update_language = UpdateLanguage.Field()
    delete_language = DeleteLanguage.Field()
    create_dictionary = CreateDictionary.Field()
    update_dictionary = UpdateDictionary.Field()
    update_dictionary_status = UpdateDictionaryStatus.Field()
    update_dictionary_roles = UpdateDictionaryRoles.Field()
    delete_dictionary = DeleteDictionary.Field()
    create_organization = CreateOrganization.Field()
    update_organization = UpdateOrganization.Field()
    delete_organization = DeleteOrganization.Field()
    create_translationatom = CreateTranslationAtom.Field()
    update_translationatom = UpdateTranslationAtom.Field()
    create_translationgist = CreateTranslationGist.Field()
    delete_translationgist = DeleteTranslationGist.Field()
    create_lexicalentry = CreateLexicalEntry.Field()
    delete_lexicalentry = DeleteLexicalEntry.Field()
    bulk_create_lexicalentry = BulkCreateLexicalEntry.Field()
    create_perspective = CreateDictionaryPerspective.Field()
    update_perspective = UpdateDictionaryPerspective.Field()
    update_perspective_status = UpdatePerspectiveStatus.Field()
    update_perspective_roles = UpdatePerspectiveRoles.Field()
    delete_perspective = DeleteDictionaryPerspective.Field()
    create_perspective_to_field = CreateDictionaryPerspectiveToField.Field()
    update_perspective_to_field = UpdateDictionaryPerspectiveToField.Field()
    delete_perspective_to_field = DeleteDictionaryPerspectiveToField.Field()
    create_grant = CreateGrant.Field()
    update_grant = UpdateGrant.Field()
    delete_grant = DeleteGrant.Field()
    create_userblob = CreateUserBlob.Field()
    delete_userblob = DeleteUserBlob.Field()
    create_grant_permission = CreateGrantPermission.Field()
    add_dictionary_to_grant = AddDictionaryToGrant.Field()
    administrate_org = AdministrateOrg.Field()
    participate_org = ParticipateOrg.Field()
    accept_userrequest = AcceptUserRequest.Field()
    delete_userrequest = DeleteUserRequest.Field()

schema = graphene.Schema(query=Query, auto_camelcase=False, mutation=MyMutations)

class Context(dict):
    """
    Context for graphene query execution, works as dict for arbitrary key-value associations and supports
    ACL-based permission checking.
    """

    def __init__(self, context_dict):
        """
        Initializes query execution context by initializing context key-value dictionary and, hopefully,
        getting client id and request data.
        """

        dict.__init__(self, context_dict)

        self.client_id = context_dict.get('client_id')
        self.request = context_dict.get('request')
        self.locale_id = context_dict.get('locale_id')
        self.headers = context_dict.get('headers')
        self.cookies = context_dict.get('cookies')

        self.cache = {}

    def acl_check_if(self, action, subject, subject_id):
        """
        Checks if the client has permission to perform given action on a specified subject via ACL.
        """
        if type(subject_id) is list:
            subject_id = tuple(subject_id)

        if (action, subject, subject_id) in self.cache:
            return self.cache[(action, subject, subject_id)]

        result = acl.check_direct(self.client_id, self.request, action, subject, subject_id)
        self.cache[(action, subject, subject_id)] = result

        return result

    def acl_check(self, action, subject, subject_id):
        """
        Checks if the client has permission to perform given action on a specified subject via ACL, raises
        permission exception otherwise.
        """

        if not self.acl_check_if(action, subject, subject_id):
            raise PermissionException(self.client_id, action, subject, subject_id)

    def acl_check_with_id_if(self, action, subject, args):
        """
        Checks via ACL if the client has permission to perform given action on a specified subject, with
        subject identifier extracted from query execution arguments.
        """

        return self.acl_check_if(action, subject, args.get('id'))
