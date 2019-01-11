import itertools

import graphene
from collections import  defaultdict
from sqlalchemy import and_

from lingvodoc.cache.caching import CACHE
from lingvodoc.models import (
    DictionaryPerspective as dbPerspective,
    Dictionary as dbDictionary,
    TranslationAtom as dbTranslationAtom,
    Language as dbLanguage,
    LexicalEntry as dbLexicalEntry,
    Client as dbClient,
    User as dbUser,
    TranslationGist as dbTranslationGist,
    BaseGroup as dbBaseGroup,
    Group as dbGroup,
    Entity as dbEntity,
    Organization as dbOrganization,
    ObjectTOC,
    DBSession,
    DictionaryPerspectiveToField as dbColumn,
    PublishingEntity as dbPublishingEntity,
    )

from lingvodoc.schema.gql_holders import (
    LingvodocObjectType,
    LingvodocID,
    CommonFieldsComposite,
    TranslationHolder,
    StateHolder,
    fetch_object,
    client_id_check,
    del_object,
    ResponseError,
    acl_check_by_id,
    ObjectVal
)

from lingvodoc.schema.gql_dictionary import Dictionary
from lingvodoc.schema.gql_column import Column
from lingvodoc.schema.gql_lexicalentry import LexicalEntry
from lingvodoc.schema.gql_language import Language
from lingvodoc.schema.gql_entity import Entity
from lingvodoc.schema.gql_user import User
from lingvodoc.utils.search import translation_gist_search

from sqlalchemy.sql.expression import case, true, false

from lingvodoc.views.v2.translations import translationgist_contents
from lingvodoc.utils import statistics
from pyramid.request import Request
from lingvodoc.utils.creation import (
    create_perspective,
    create_gists_with_atoms,
    add_user_to_group,
    translationgist_contents,
    edit_role
)
from lingvodoc.utils.deletion import real_delete_perspective

from sqlalchemy import (
    func,
    or_,
    and_,
    tuple_
)

from lingvodoc.schema.gql_holders import UserAndOrganizationsRoles

def group_by_lex(entity_with_published):
    entity = entity_with_published[0]
    return (entity.parent_client_id, entity.parent_object_id)


def gql_entity_with_published(cur_entity, cur_publishing):
    ent = Entity(id=(cur_entity.client_id, cur_entity.object_id))
    ent.dbObject = cur_entity
    ent.publishingentity = cur_publishing
    return ent

def gql_lexicalentry(cur_lexical_entry, cur_entities):
    lex = LexicalEntry(id=(cur_lexical_entry.client_id, cur_lexical_entry.object_id))
    lex.gql_Entities = cur_entities
    lex.dbObject = cur_lexical_entry
    return lex

def entries_with_entities(lexes, accept, delete, mode, publish):
    if mode == 'debug':
        return [gql_lexicalentry(lex, None) for lex in lexes]
    lex_id_to_obj = dict()
    lexes_composite_list = list()
    for lex_obj in lexes.yield_per(100).all():
        lexes_composite_list.append((lex_obj.client_id, lex_obj.object_id,
                                    lex_obj.parent_client_id, lex_obj.parent_object_id))
        lex_id_to_obj[(lex_obj.client_id, lex_obj.object_id)] = lex_obj

    if mode == 'not_accepted':
        accept = False
        delete = False

    entities = dbLexicalEntry.graphene_track_multiple(lexes_composite_list,
                                                      publish=publish,
                                                      accept=accept,
                                                      delete=delete)
    entities_list = list([x for x in entities])
    ent_iter = itertools.chain(entities_list)
    result_lexes = list()
    for lex_ids, entity_with_published in itertools.groupby(ent_iter, key=group_by_lex):
        gql_entities_list = [gql_entity_with_published(cur_entity=x[0], cur_publishing=x[1])
                             for x in entity_with_published]
        lexical_entry = lex_id_to_obj[lex_ids]
        if (lexical_entry.client_id, lexical_entry.object_id) == lex_ids:
            result_lexes.append((lexical_entry, gql_entities_list))
    lexical_entries = [gql_lexicalentry(cur_lexical_entry=lex[0], cur_entities=lex[1]) for lex in result_lexes]

    return lexical_entries

class DictionaryPerspective(LingvodocObjectType):
    """
     #created_at                       | timestamp without time zone | NOT NULL
     #object_id                        | bigint                      | NOT NULL
     #client_id                        | bigint                      | NOT NULL
     #parent_object_id                 | bigint                      |
     #parent_client_id                 | bigint                      |
     #translation_gist_client_id       | bigint                      | NOT NULL
     #translation_gist_object_id       | bigint                      | NOT NULL
     #state_translation_gist_client_id | bigint                      | NOT NULL
     #state_translation_gist_object_id | bigint                      | NOT NULL
     #marked_for_deletion              | boolean                     | NOT NULL
     #is_template                      | boolean                     | NOT NULL
     #import_source                    | text                        |
     #import_hash                      | text                        |
     #additional_metadata              | jsonb                       |
     + .translation
     + status
     + tree

    query myQuery {
      perspective(id: [78, 4]) {
        id
        statistic(starting_time: 0, ending_time: 1506812557)
        entities(mode: "all") {
          id
          parent_id
          published
          accepted
        }
        lexical_entries(ids: [[78, 6], [78, 8]]) {
          id
        }
            columns{
                id
                field_id
            }
      }
    }

    """
    data_type = graphene.String()

    status = graphene.String()
    import_source = graphene.String()
    import_hash = graphene.String()

    tree = graphene.List(CommonFieldsComposite, )  # TODO: check it
    columns = graphene.List(Column)
    # entities = graphene.List(Entity, mode=graphene.String())
    # entities_old = graphene.List(Entity, mode=graphene.String())
    lexical_entries = graphene.List(LexicalEntry, ids = graphene.List(LingvodocID), mode=graphene.String())
    authors = graphene.List('lingvodoc.schema.gql_user.User')
    # stats = graphene.String() # ?
    roles = graphene.Field(UserAndOrganizationsRoles)
    statistic = graphene.Field(ObjectVal, starting_time=graphene.Int(), ending_time=graphene.Int())
    is_template = graphene.Boolean()
    # counters = graphene.Field(PerspectiveCounters)
    counter = graphene.Int(mode=graphene.String())

    dbType = dbPerspective

    class Meta:
        interfaces = (CommonFieldsComposite, StateHolder)

    # @fetch_object()
    # def resolve_additional_metadata(self, args, context, info):
    #     return self.dbObject.additional_metadata

    # @fetch_object('translation')
    # def resolve_translation(self, args, context, info):
    #     return self.dbObject.get_translation(context.get('locale_id'))

    @fetch_object('is_template')
    def resolve_is_template(self, info):
        return self.dbObject.is_template

    @fetch_object('status') # tested
    def resolve_status(self, info):
        atom = DBSession.query(dbTranslationAtom.content).filter_by(
            parent_client_id=self.dbObject.state_translation_gist_client_id,
            parent_object_id=self.dbObject.state_translation_gist_object_id,
            locale_id=int(info.context.get('locale_id'))
        ).first()
        if atom:
            return atom[0]
        else:
            return None

    @fetch_object() # tested
    def resolve_tree(self, info):
        result = list()
        iteritem = self.dbObject
        while iteritem:
            id = [iteritem.client_id, iteritem.object_id]
            if type(iteritem) == dbPerspective:
                gql_persp = DictionaryPerspective(id=id)
                gql_persp.dbObject = iteritem
                result.append(gql_persp)
            if type(iteritem) == dbDictionary:
                result.append(Dictionary(id=id))
            if type(iteritem) == dbLanguage:
                result.append(Language(id=id))
            iteritem = iteritem.parent

        return result

    @fetch_object() # tested
    def resolve_columns(self, info):
        columns = DBSession.query(dbColumn).filter_by(parent=self.dbObject, marked_for_deletion=False).order_by(dbColumn.position).all()
        result = list()
        for dbfield in columns:
            gr_field_obj = Column(id=[dbfield.client_id, dbfield.object_id])
            gr_field_obj.dbObject = dbfield
            result.append(gr_field_obj)
        return result

    #@acl_check_by_id('view', 'approve_entities')
    # @fetch_object()
    # def resolve_lexical_entries(self, info, ids=None):
    #     lex_list = list()
    #     query = DBSession.query(dbLexicalEntry, dbEntity)
    #     if ids is None:
    #         query = query.filter(dbLexicalEntry.parent == self.dbObject, dbLexicalEntry.marked_for_deletion == False)
    #     else:
    #         query = query.filter(tuple_(dbLexicalEntry.client_id, dbLexicalEntry.object_id).in_(ids), dbLexicalEntry.parent == self.dbObject, dbLexicalEntry.marked_for_deletion == False)
    #     for lex in query.all():
    #         lex_object = LexicalEntry(id=[lex.client_id, lex.object_id])
    #         lex_object.dbObject = lex
    #         lex_list.append(lex_object)
    #     return lex_list


    # @fetch_object()
    # def resolve_counters(self, info):
    #     lexes = DBSession.query(dbLexicalEntry).filter(dbLexicalEntry.parent == self.dbObject)
    #     lexes = lexes.join(dbLexicalEntry.entity).join(dbEntity.publishingentity)
    #     all_count = lexes.filter(dbPublishingEntity.accepted == True, dbLexicalEntry.marked_for_deletion == False,
    #                              dbEntity.marked_for_deletion == False).count()
    #     published_count = lexes.filter(dbPublishingEntity.published == True, dbLexicalEntry.marked_for_deletion == False,
    #                              dbEntity.marked_for_deletion == False).count()
    #     not_accepted_count = lexes.filter(dbPublishingEntity.accepted == False, dbLexicalEntry.marked_for_deletion == False,
    #                              dbEntity.marked_for_deletion == False).count()
    #     return PerspectiveCounters(all=all_count, published=published_count, not_accepted=not_accepted_count)

    @fetch_object()
    def resolve_counter(self, info, mode):
        lexes = DBSession.query(dbLexicalEntry).filter(dbLexicalEntry.parent == self.dbObject)
        lexes = lexes.join(dbLexicalEntry.entity).join(dbEntity.publishingentity)
        if mode == 'all':
            # info.context.acl_check('view', 'lexical_entries_and_entities',
            #                        (self.dbObject.client_id, self.dbObject.object_id))
            counter_query = lexes.filter(dbPublishingEntity.accepted == True, dbLexicalEntry.marked_for_deletion == False,
                                 dbEntity.marked_for_deletion == False)
        elif mode == 'published':
            counter_query = lexes.filter(dbPublishingEntity.published == True, dbLexicalEntry.marked_for_deletion == False,
                                 dbEntity.marked_for_deletion == False)
        elif mode == 'not_accepted':
            counter_query = lexes.filter(dbPublishingEntity.accepted == False, dbLexicalEntry.marked_for_deletion == False,
                                 dbEntity.marked_for_deletion == False)
        else:
            raise ResponseError(message="mode: <all|published|not_accepted>")
        counter = counter_query.group_by(dbLexicalEntry).count()
        return counter

    @fetch_object()
    def resolve_lexical_entries(self, info, ids=None, mode=None, authors=None, clients=None, start_date=None, end_date=None,
                             position=1):
        result = list()
        request = info.context.get('request')
        if mode == 'all':
            publish = None
            accept = True
            delete = False
            info.context.acl_check('view', 'lexical_entries_and_entities',
                                   (self.dbObject.client_id, self.dbObject.object_id))
        elif mode == 'published':
            publish = True
            accept = True
            delete = False
        elif mode == 'not_accepted':
            publish = None
            accept = False
            delete = False
        elif mode == 'deleted':
            publish = None
            accept = None
            delete = True
            info.context.acl_check('view', 'lexical_entries_and_entities',
                                   (self.dbObject.client_id, self.dbObject.object_id))
        elif mode == 'all_with_deleted':
            publish = None
            accept = None
            delete = None
            info.context.acl_check('view', 'lexical_entries_and_entities',
                                   (self.dbObject.client_id, self.dbObject.object_id))
        elif mode == 'debug':
            publish = None
            accept = True
            delete = False
            info.context.acl_check('view', 'lexical_entries_and_entities',
                                   (self.dbObject.client_id, self.dbObject.object_id))
        else:
            raise ResponseError(message="mode: <all|published|not_accepted|deleted|all_with_deleted>")

        # dbcolumn = DBSession.query(dbColumn).filter_by(parent=self.dbObject, position=position, self_client_id=None,
        #                                                self_object_id=None).first()
        # if not dbcolumn:
        #     dbcolumn = DBSession.query(dbColumn).filter_by(parent=self.dbObject, self_client_id=None,
        #                                                self_object_id=None).first()
        lexes = DBSession.query(dbLexicalEntry).filter(dbLexicalEntry.parent == self.dbObject)
        if ids is not None:
            ids = list(ids)
            lexes = lexes.filter(tuple_(dbLexicalEntry.client_id, dbLexicalEntry.object_id).in_(ids))
        if authors or start_date or end_date:
            lexes = lexes.join(dbLexicalEntry.entity).join(dbEntity.publishingentity)

        # if publish is not None:
        #     lexes = lexes.filter(dbPublishingEntity.published == publish)
        # if accept is not None:
        #     lexes = lexes.filter(dbPublishingEntity.accepted == accept)
        if delete is not None:
            if authors or start_date or end_date:
                lexes = lexes.filter(or_(dbLexicalEntry.marked_for_deletion == delete, dbEntity.marked_for_deletion == delete))
            else:
                lexes = lexes.filter(dbLexicalEntry.marked_for_deletion == delete)
        if authors:
            lexes = lexes.join(dbClient, dbEntity.client_id == dbClient.id).join(dbClient.user).filter(dbUser.id.in_(authors))
        if start_date:
            lexes = lexes.filter(dbEntity.created_at >= start_date)
        if end_date:
            lexes = lexes.filter(dbEntity.created_at <= end_date)

        db_la_gist = translation_gist_search('Limited access')
        limited_client_id, limited_object_id = db_la_gist.client_id, db_la_gist.object_id

        if self.dbObject.state_translation_gist_client_id == limited_client_id and self.dbObject.state_translation_gist_object_id == limited_object_id and mode != 'not_accepted':
            if not info.context.acl_check_if('view', 'lexical_entries_and_entities',
                                   (self.dbObject.client_id, self.dbObject.object_id)):
                lexes = lexes.limit(20)

        # lexes = lexes \
        #     .order_by(func.min(case(
        #     [(or_(dbEntity.field_client_id != dbcolumn.field_client_id,
        #           dbEntity.field_object_id != dbcolumn.field_object_id),
        #       'яяяяяя')],
        #     else_=dbEntity.content))) \
        #     .group_by(dbLexicalEntry)
        lexical_entries = entries_with_entities(lexes, accept, delete, mode, publish)
        return lexical_entries


    @fetch_object()
    def resolve_authors(self, info):
        client_id, object_id = self.dbObject.client_id, self.dbObject.object_id

        parent = DBSession.query(dbPerspective).filter_by(client_id=client_id, object_id=object_id).first()
        if parent and not parent.marked_for_deletion:
            authors = DBSession.query(dbUser).join(dbUser.clients).join(dbEntity, dbEntity.client_id == dbClient.id) \
                .join(dbEntity.parent).join(dbEntity.publishingentity) \
                .filter(dbLexicalEntry.parent_client_id == parent.client_id,# TODO: filter by accepted==True
                        dbLexicalEntry.parent_object_id == parent.object_id,
                        dbLexicalEntry.marked_for_deletion == False,
                        dbEntity.marked_for_deletion == False)

            authors_list = [User(id=author.id,
                                 name=author.name,
                                 intl_name=author.intl_name,
                                 login=author.login) for author in authors]
            return authors_list
        raise ResponseError(message="Error: no such perspective in the system.")

    @fetch_object(ACLSubject='perspective_role', ACLKey='id')
    def resolve_roles(self, info):
        client_id, object_id = self.dbObject.client_id, self.dbObject.object_id
        perspective = DBSession.query(dbPerspective).filter_by(client_id=client_id, object_id=object_id).first()
        if not perspective or perspective.marked_for_deletion:
            raise ResponseError(message="Perspective with such ID doesn`t exists in the system")


        bases = DBSession.query(dbBaseGroup).filter_by(perspective_default=True)
        roles_users = defaultdict(list)
        roles_organizations = defaultdict(list)
        for base in bases:
            group = DBSession.query(dbGroup).filter_by(base_group_id=base.id,
                                                     subject_object_id=object_id,
                                                     subject_client_id=client_id).first()
            if not group:
                continue
            for user in group.users:
                roles_users[user.id].append(base.id)
            for org in group.organizations:
                roles_organizations[org.id].append(base.id)
        roles_users = [{"user_id": x, "roles_ids": roles_users[x]} for x in roles_users]
        roles_organizations = [{"user_id": x, "roles_ids": roles_organizations[x]} for x in roles_organizations]
        return UserAndOrganizationsRoles(roles_users=roles_users, roles_organizations=roles_organizations)

    @fetch_object()
    def resolve_statistic(self, info, starting_time=None, ending_time=None):
        if starting_time is None or ending_time is None:
            raise ResponseError(message="Bad time period")
        locale_id = info.context.get('locale_id')
        current_statistics = statistics.stat_perspective((self.dbObject.client_id, self.dbObject.object_id),
                                                         starting_time,
                                                         ending_time,
                                                         locale_id=locale_id
                                                         )
        new_format_statistics = [
            {"user_id": key, "name": current_statistics[key]['name'], "entities": current_statistics[key]['entities']}
            for key in current_statistics]
        return new_format_statistics


class CreateDictionaryPerspective(graphene.Mutation):
    """
    example:
    mutation  {
            create_perspective( parent_id:[66,4], translation_gist_id: [714, 3],is_template: true
             additional_metadata: {hash:"1234567"}, import_source: "source", import_hash: "hash") {
                triumph

                perspective{
					is_template
                    id
                }
            }
    }
    (this example works)
    returns:
    {
        "data": {
            "create_perspective": {
                "triumph": true,
                "perspective": {
                    "id": [
                        1197,
                        320
                    ]
                }
            }
        }
    }
    with atoms:
    mutation {
      create_perspective(parent_id: [1198, 16], translation_atoms: [{locale_id: 2, content: "123"}], additional_metadata: {hash: "1234567"}, import_source: "source", import_hash: "hash") {
        triumph
        perspective {
          id
          translation
        }
      }
    }

    """

    class Arguments:
        id = LingvodocID()
        parent_id = LingvodocID(required=True)
        translation_gist_id = LingvodocID()
        translation_atoms = graphene.List(ObjectVal)
        additional_metadata = ObjectVal()
        import_source = graphene.String()
        import_hash = graphene.String()
        is_template = graphene.Boolean()

    perspective = graphene.Field(DictionaryPerspective)
    triumph = graphene.Boolean()


    @staticmethod
    @client_id_check()
    @acl_check_by_id('create', 'perspective', id_key = "parent_id")
    def mutate(root, info, **args):
        id = args.get("id")
        client_id = id[0] if id else info.context["client_id"]
        object_id = id[1] if id else None
        id = [client_id, object_id]
        parent_id = args.get('parent_id')
        translation_gist_id = args.get('translation_gist_id')
        translation_atoms = args.get("translation_atoms")

        translation_gist_id = create_gists_with_atoms(translation_atoms,
                                                      translation_gist_id,
                                                      [client_id,object_id],
                                                      gist_type="Perspective")
        import_source = args.get('import_source')
        import_hash = args.get('import_hash')
        additional_metadata = args.get('additional_metadata')
        is_template = args.get("is_template")
        dbperspective = create_perspective(id=id,
                                parent_id=parent_id,
                                translation_gist_id=translation_gist_id,
                                additional_metadata=additional_metadata,
                                import_source=import_source,
                                import_hash=import_hash,
                                is_template=is_template
                                )
        perspective = DictionaryPerspective(id=[dbperspective.client_id, dbperspective.object_id])
        perspective.dbObject = dbperspective
        return CreateDictionaryPerspective(perspective=perspective, triumph=True)


class UpdateDictionaryPerspective(graphene.Mutation):
    """
    example:
      mutation  {
            update_perspective(id:[949,2491], parent_id:[449,2491], translation_gist_id: [714, 3]) {
                triumph
                perspective{
                    id
                }
            }
    }

    (this example works)
    returns:

    {
      "update_perspective": {
        "triumph": true,
        "perspective": {
          "id": [
            949,
            2491
          ],
        }
      }
    }
    """
    class Arguments:
        id = LingvodocID(required=True)  #List(graphene.Int) # lingvidicID
        translation_gist_id = LingvodocID()
        parent_id = LingvodocID()

    perspective = graphene.Field(DictionaryPerspective)
    triumph = graphene.Boolean()

    @staticmethod
    @acl_check_by_id('edit', 'perspective')
    def mutate(root, info, **args):
        id = args.get("id")
        client_id = id[0]
        object_id = id[1]
        parent_id = args.get('parent_id')
        dbperspective = DBSession.query(dbPerspective).filter_by(client_id=client_id, object_id=object_id).first()
        if not dbperspective or dbperspective.marked_for_deletion:
            raise ResponseError(message="Error: No such perspective in the system")

        # dictionaryperspective_parent_object_id_fkey  (parent_object_id, parent_client_id)=(2491, 449)  in dictionary
        translation_gist_id = args.get("translation_gist_id")
        translation_gist_client_id = translation_gist_id[0] if translation_gist_id else None
        translation_gist_object_id = translation_gist_id[1] if translation_gist_id else None
        if translation_gist_client_id:
            dbperspective.translation_gist_client_id = translation_gist_client_id
        if translation_gist_object_id:
            dbperspective.translation_gist_object_id = translation_gist_object_id  # TODO: refactor like dictionaries
        if parent_id:
            parent_client_id, parent_object_id = parent_id
            dbparent_dictionary = DBSession.query(dbDictionary).filter_by(client_id=parent_client_id,
                                                                          object_id=parent_object_id).first()
            if not dbparent_dictionary:
                raise ResponseError(message="Error: No such dictionary in the system")
            dbperspective.parent_client_id = parent_client_id
            dbperspective.parent_object_id = parent_object_id


        perspective = DictionaryPerspective(id=[dbperspective.client_id, dbperspective.object_id])
        perspective.dbObject = dbperspective
        return UpdateDictionaryPerspective(perspective=perspective, triumph=True)

class UpdatePerspectiveStatus(graphene.Mutation):
    """
    mutation  {
    update_perspective_status(id:[66, 5], state_translation_gist_id: [1, 192]) {
        triumph
        perspective{
            id
        }
    }
    }

    """
    class Arguments:
        id = LingvodocID(required=True)
        state_translation_gist_id = LingvodocID(required=True)

    perspective = graphene.Field(DictionaryPerspective)
    triumph = graphene.Boolean()

    @staticmethod
    @acl_check_by_id("edit", "perspective_status")
    def mutate(root, info, **args):
        client_id, object_id = args.get('id')
        state_translation_gist_client_id, state_translation_gist_object_id = args.get('state_translation_gist_id')
        dbperspective = DBSession.query(dbPerspective).filter_by(client_id=client_id, object_id=object_id).first()
        if dbperspective and not dbperspective.marked_for_deletion:
            dbperspective.state_translation_gist_client_id = state_translation_gist_client_id
            dbperspective.state_translation_gist_object_id = state_translation_gist_object_id
            atom = DBSession.query(dbTranslationAtom).filter_by(parent_client_id=state_translation_gist_client_id,
                                                              parent_object_id=state_translation_gist_object_id,
                                                              locale_id=info.context.get('locale_id')).first()
            perspective = DictionaryPerspective(id=[dbperspective.client_id, dbperspective.object_id],
                                                status=atom.content)
            perspective.dbObject = dbperspective
            return UpdatePerspectiveStatus(perspective=perspective, triumph=True)

class AddPerspectiveRoles(graphene.Mutation):
    """
        mutation myQuery {
            add_perspective_roles(id: [1279,7], user_id:2 , roles_users:[8,12,13,15,20,21,22,23,24,26,16,34]){
						triumph

					}
        }
    """
    class Arguments:
        id = LingvodocID(required=True)
        user_id = graphene.Int(required=True)
        roles_users = graphene.List(graphene.Int)
        roles_organizations = graphene.List(graphene.Int)

    perspective = graphene.Field(DictionaryPerspective)
    triumph = graphene.Boolean()

    @staticmethod
    @acl_check_by_id("create", "perspective_role")
    def mutate(root, info, **args):
        perspective_client_id, perspective_object_id = args.get('id')
        user_id = args.get("user_id")
        roles_users = args.get('roles_users')
        roles_organizations = args.get('roles_organizations')
        dbperspective = DBSession.query(dbPerspective).filter_by(client_id=perspective_client_id, object_id=perspective_object_id).first()
        client_id = info.context.get('client_id')
        if not dbperspective or dbperspective.marked_for_deletion:
            raise ResponseError(message="No such perspective in the system")
        if roles_users:
            for role_id in roles_users:
                edit_role(dbperspective, user_id, role_id, client_id, perspective_default=True)
        if roles_organizations:
            for role_id in roles_organizations:
                edit_role(dbperspective, user_id, role_id, client_id, perspective_default=True, organization=True)
        perspective = Dictionary(id=[dbperspective.client_id, dbperspective.object_id])
        perspective.dbObject = dbperspective
        return AddPerspectiveRoles(perspective=perspective, triumph=True)


class DeletePerspectiveRoles(graphene.Mutation):
    class Arguments:
        id = LingvodocID(required=True)
        user_id = graphene.Int(required=True)
        roles_users = graphene.List(graphene.Int)
        roles_organizations = graphene.List(graphene.Int)

    perspective = graphene.Field(Dictionary)
    triumph = graphene.Boolean()

    @staticmethod
    @acl_check_by_id("delete", "perspective_role")
    def mutate(root, info, **args):
        perspective_client_id, perspective_object_id = args.get('id')
        user_id = args.get("user_id")
        roles_users = args.get('roles_users')
        roles_organizations = args.get('roles_organizations')
        dbperspective = DBSession.query(dbPerspective).filter_by(client_id=perspective_client_id,
                                                                 object_id=perspective_object_id).first()
        client_id = info.context.get('client_id')
        if not dbperspective or dbperspective.marked_for_deletion:
            raise ResponseError(message="No such perspective in the system")
        if roles_users:
            for role_id in roles_users:
                edit_role(dbperspective, user_id, role_id, client_id, perspective_default=True, action="delete")

        if roles_organizations:
            for role_id in roles_organizations:
                edit_role(dbperspective, user_id, role_id, client_id, perspective_default=True, organization=True,
                          action="delete")
        perspective = DictionaryPerspective(id=[dbperspective.client_id, dbperspective.object_id])
        perspective.dbObject = dbperspective
        return DeletePerspectiveRoles(perspective=perspective, triumph=True)


class UpdatePerspectiveAtom(graphene.Mutation):
    """
    example:
mutation up{
	update_perspective_atom(id: [2138, 6], locale_id: 2, content: "test6"){
		triumph
	}

}

    now returns:

{
	"data": {
		"update_perspective_atom": {
			"triumph": true
		}
	}
}
    """

    class Arguments:
        id = LingvodocID(required=True)
        content = graphene.String()
        locale_id = graphene.Int()
        atom_id = LingvodocID()

    #translationatom = graphene.Field(TranslationAtom)
    triumph = graphene.Boolean()
    locale_id = graphene.Int()
    perspective = graphene.Field(DictionaryPerspective)

    @staticmethod
    @acl_check_by_id('edit', 'perspective')
    def mutate(root, info, **args):
        content = args.get('content')
        client_id, object_id = args.get('id')
        dbperspective = DBSession.query(dbPerspective).filter_by(client_id=client_id, object_id=object_id).first()
        if not dbperspective:
            raise ResponseError(message="No such perspective in the system")
        locale_id = args.get("locale_id")


        dbtranslationatom = DBSession.query(dbTranslationAtom).filter_by(parent_client_id=dbperspective.translation_gist_client_id,
                                                            parent_object_id=dbperspective.translation_gist_object_id,
                                                            locale_id=locale_id).first()
        if dbtranslationatom:
            if dbtranslationatom.locale_id == locale_id:
                key = "translation:%s:%s:%s" % (
                    str(dbtranslationatom.parent_client_id),
                    str(dbtranslationatom.parent_object_id),
                    str(dbtranslationatom.locale_id))
                CACHE.rem(key)
                if content:
                    dbtranslationatom.content = content
            else:
                if args.get('atom_id'):
                    atom_client_id, atom_object_id = args.get('atom_id')
                else:
                    raise ResponseError(message="atom field is empty")
                args_atom = DBSession.query(dbTranslationAtom).filter_by(client_id=atom_client_id,
                                                                         object_id=atom_object_id).first()
                if not args_atom:
                    raise ResponseError(message="No such dictionary in the system")
                dbtranslationatom.locale_id = locale_id
        else:
            dbtranslationatom = dbTranslationAtom(client_id=client_id,
                                                object_id=None,
                                                parent_client_id=dbperspective.translation_gist_client_id,
                                                parent_object_id=dbperspective.translation_gist_object_id,
                                                locale_id=locale_id,
                                                content=content)
            DBSession.add(dbtranslationatom)
            DBSession.flush()

        perspective = DictionaryPerspective(id=[dbPerspective.client_id, dbPerspective.object_id])
        perspective.dbObject = dbPerspective
        return UpdatePerspectiveAtom(perspective=perspective, triumph=True)

class DeleteDictionaryPerspective(graphene.Mutation):
    """
    example:
      mutation  {
            delete_perspective(id:[949,2491], parent_id:[449,2491]) {
                triumph
                perspective{
                    id
                }
            }
    }

    (this example works)
    returns:

    {
      "delete_perspective": {
        "triumph": true,
        "perspective": {
          "id": [
            949,
            2491
          ],
        }
      }
    }
    """
    class Arguments:
        id = LingvodocID(required=True)

    perspective = graphene.Field(DictionaryPerspective)
    triumph = graphene.Boolean()

    @staticmethod
    @acl_check_by_id('delete', 'perspective')
    def mutate(root, info, **args):
        id = args.get("id")
        client_id, object_id = id
        dbperspective = DBSession.query(dbPerspective).filter_by(client_id=client_id, object_id=object_id).first()
        if not dbPerspective or dbperspective.marked_for_deletion:
            raise ResponseError(message="No such perspective in the system")
        settings = info.context["request"].registry.settings
        if 'desktop' in settings:
            real_delete_perspective(dbperspective, settings)
        else:
            del_object(dbperspective)

        perspective = DictionaryPerspective(id=[dbperspective.client_id, dbperspective.object_id])
        perspective.dbObject = dbperspective
        return DeleteDictionaryPerspective(perspective=perspective, triumph=True)

