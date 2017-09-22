import graphene

from lingvodoc.schema.gql_entity import (
    Entity,
    CreateEntity,
    UpdateEntity,
    DeleteEntity
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
from lingvodoc.schema.gql_publishingentity import (
    PublishingEntity
)
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
    CreateUserBlob
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
    DeleteDictionary
)

from lingvodoc.schema.gql_lexicalentry import (
    LexicalEntry,
    CreateLexicalEntry,
    DeleteLexicalEntry
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
from lingvodoc.schema.gql_email import (
    Email
)
from lingvodoc.schema.gql_holders import (
    PermissionException,
    ResponseError,
    ObjectVal
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
    Client
)
from pyramid.request import Request

from sqlalchemy import (
    func,
    and_,
    or_,
    tuple_
)

from sqlalchemy.orm import aliased

from sqlalchemy.sql.functions import coalesce

from pyramid.security import authenticated_userid

RUSSIAN_LOCALE = 1
ENGLISH_LOCALE = 2


class Query(graphene.ObjectType):
    client = graphene.String()
    dictionaries = graphene.List(Dictionary, published=graphene.Boolean())
    dictionary = graphene.Field(Dictionary, id=graphene.List(graphene.Int))
    perspectives = graphene.List(DictionaryPerspective, published=graphene.Boolean())
    perspective = graphene.Field(DictionaryPerspective, id=graphene.List(graphene.Int))
    entity = graphene.Field(Entity, id=graphene.List(graphene.Int))
    language = graphene.Field(Language, id=graphene.List(graphene.Int))
    languages = graphene.List(Language)
    user = graphene.Field(User, id=graphene.Int())
    users = graphene.List(User, search=graphene.String())
    field = graphene.Field(Field, id=graphene.List(graphene.Int))
    translationatom = graphene.Field(TranslationAtom, id=graphene.List(graphene.Int))
    organization = graphene.Field(Organization, id=graphene.List(graphene.Int))
    organizations = graphene.List(Organization)
    lexicalentry = graphene.Field(LexicalEntry, id=graphene.List(graphene.Int))
    lexicalentries = graphene.List(LexicalEntry, searchstring=graphene.String(), can_add_tags=graphene.Boolean(),
                                   perspective_id=graphene.List(graphene.Int), field_id=graphene.List(graphene.Int),
                                   search_in_published=graphene.Boolean())
    advancedlexicalentries = graphene.List(LexicalEntry, searchstrings=graphene.List(ObjectVal),
                                            perspectives=graphene.List(graphene.List(graphene.Int)),
                                            adopted=graphene.Boolean(),
                                            adopted_type=graphene.List(graphene.Int),
                                            with_entimology=graphene.Boolean())
    translationgist = graphene.Field(TranslationGist, id = graphene.List(graphene.Int))
    translationgists = graphene.List(TranslationGist)

    all_locales = graphene.List(ObjectVal)
    userblob = graphene.Field(UserBlobs, id=graphene.List(graphene.Int))

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
        if published:
            subreq = Request.blank('/translation_service_search')
            subreq.method = 'POST'
            subreq.headers = request.headers
            subreq.json = {'searchstring': 'Published'}
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
            subreq.json = {'searchstring': 'Limited access'}
            headers = {'Cookie': request.headers['Cookie']}
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

    def resolve_email(self, info, id):
        return Email(id=id)

    def resolve_grant(self, info, id):
        return Grant(id=id)

    def resolve_group(self, info, id):
        return Group(id=id)

    def resolve_organization(self, info, id):
        return Organization(id=id)

    def resolve_organizations(self, info):
        organizations = DBSession.query(dbOrganization).filter_by(marked_for_deletion=False).all()
        organizations_list = [Organization(name=organization.name,
                                           about=organization.about) for organization in organizations]
        return organizations_list

    # def resolve_passhash(self, args, context, info):
    #     id = args.get('id')
    #     return Passhash(id=id)

    # def resolve_objecttoc(self, args, context, info):
    #     id = args.get('id')
    #     return ObjectTOC(id=id)

    def resolve_publishingentity(self, info, id):
        return PublishingEntity(id=id)

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

    def resolve_userblobs(self, info, id):
        return UserBlobs(id=id)

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

    def resolve_advancedlexicalentries(self, info, searchstrings, perspectives=None, adopted=None,
                                        adopted_type=None, with_etimology=None): #advanced_search() function

        """
        query EntriesList {
            advancedlexicalentries(searchstrings: [{searchstring: "смотреть следить"}]) {
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
    create_user = CreateUser.Field()
    update_user = UpdateUser.Field()
    create_language = CreateLanguage.Field()
    update_language = UpdateLanguage.Field()
    delete_language = DeleteLanguage.Field()
    create_dictionary = CreateDictionary.Field()
    update_dictionary = UpdateDictionary.Field()
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
    create_perspective = CreateDictionaryPerspective.Field()
    update_perspective = UpdateDictionaryPerspective.Field()
    delete_perspective = DeleteDictionaryPerspective.Field()
    create_perspective_to_field = CreateDictionaryPerspectiveToField.Field()
    update_perspective_to_field = UpdateDictionaryPerspectiveToField.Field()
    delete_perspective_to_field = DeleteDictionaryPerspectiveToField.Field()
    create_grant = CreateGrant.Field()
    update_grant = UpdateGrant.Field()
    delete_grant = DeleteGrant.Field()
    create_userblob = CreateUserBlob.Field()

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
