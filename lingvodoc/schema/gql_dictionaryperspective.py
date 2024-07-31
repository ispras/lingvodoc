
# Standard library imports.

from collections import  defaultdict
import datetime
import itertools
import logging
import pprint

# External imports.

import graphene

import sqlalchemy

from sqlalchemy import (
    and_,
    cast,
    column,
    extract,
    func,
    literal,
    or_,
    tuple_,
    union)

from sqlalchemy.sql.expression import Grouping

# Lingvodoc imports.

from lingvodoc.cache.caching import CACHE

from lingvodoc.models import (
    BaseGroup as dbBaseGroup,
    Client as dbClient,
    DBSession,
    Dictionary as dbDictionary,
    DictionaryPerspective as dbPerspective,
    DictionaryPerspectiveToField as dbColumn,
    Entity as dbEntity,
    Group as dbGroup,
    JSONB,
    Language as dbLanguage,
    LexicalEntry as dbLexicalEntry,
    PerspectivePage as dbPerspectivePage,
    ObjectTOC,
    ParserResult as dbParserResult,
    PublishingEntity as dbPublishingEntity,
    TranslationAtom as dbTranslationAtom,
    TranslationGist as dbTranslationGist,
    User as dbUser,
    user_to_group_association,
    ValencyEafData as dbValencyEafData,
    ValencyParserData as dbValencyParserData,
    ValencySourceData as dbValencySourceData,
    ValencySentenceData as dbValencySentenceData,
    AdverbInstanceData as dbAdverbInstanceData)

from lingvodoc.schema.gql_column import Column
from lingvodoc.schema.gql_dictionary import Dictionary
from lingvodoc.schema.gql_entity import Entity

from lingvodoc.schema.gql_holders import (
    acl_check_by_id,
    client_id_check,
    CommonFieldsComposite,
    del_object,
    fetch_object,
    LingvodocID,
    LingvodocObjectType,
    ObjectVal,
    ResponseError,
    StateHolder,
    undel_object,
    UserAndOrganizationsRoles)

from lingvodoc.schema.gql_language import Language
from lingvodoc.schema.gql_lexicalentry import LexicalEntry
from lingvodoc.schema.gql_user import User

from lingvodoc.utils import statistics

from lingvodoc.utils.creation import (
    create_dictionary_persp_to_field,
    create_gists_with_atoms,
    create_perspective,
    edit_role,
    update_metadata)

from lingvodoc.utils.deletion import real_delete_perspective
from lingvodoc.utils.search import translation_gist_search
from pdb import set_trace as A


# Setting up logging.
log = logging.getLogger(__name__)


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

def entries_with_entities(lexes, mode, check_perspective = True, **kwargs):

    if mode == 'debug':
        return [gql_lexicalentry(lex, None) for lex in lexes]

    lex_id_to_obj = dict()
    lexes_composite_list = list()

    for lex_obj in (
        lexes if isinstance(lexes, list) else
        lexes.yield_per(100).all()):

        entry_id = (lex_obj.client_id, lex_obj.object_id)

        # If we don't need to check for perspective deletion, we don't need perspective ids.
        if check_perspective:
            lexes_composite_list.append((lex_obj.client_id, lex_obj.object_id,
                                         lex_obj.parent_client_id, lex_obj.parent_object_id))
        else:
            lexes_composite_list.append(entry_id)

        lex_id_to_obj[entry_id] = lex_obj

    if mode == 'not_accepted':
        accept = False
        delete = False

    (entities, empty_lexes) = (

        dbLexicalEntry.graphene_track_multiple(lexes_composite_list,
                                               check_perspective=check_perspective,
                                               **kwargs))

    lexical_entries = list()

    # We got empty lexes only if is_edit_mode
    for lex_ids in empty_lexes:

        lexical_entries.append(
            gql_lexicalentry(
                cur_lexical_entry = lex_id_to_obj[lex_ids],
                cur_entities = []))

    ent_iter = itertools.chain(list(entities))

    for lex_ids, entity_with_published in itertools.groupby(ent_iter, key = group_by_lex):

        gql_entities_list = [
            gql_entity_with_published(cur_entity = x[0], cur_publishing = x[1])
            for x in entity_with_published]

        lexical_entries.append(
            gql_lexicalentry(
                cur_lexical_entry = lex_id_to_obj[lex_ids],
                cur_entities = gql_entities_list))

    return lexical_entries


class PerspectivePage(graphene.ObjectType):

    lexical_entries = graphene.List(LexicalEntry)
    entries_total = graphene.Int()

    dbType = dbPerspectivePage

    class Meta:
        pass


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

    import_source = graphene.String()
    import_hash = graphene.String()

    tree = graphene.List(CommonFieldsComposite, )  # TODO: check it
    columns = graphene.List(Column)

    lexical_entries = graphene.List(
        LexicalEntry,
        ids = graphene.List(LingvodocID),
        mode = graphene.String())

    perspective_page = graphene.Field(
        PerspectivePage,
        ids = graphene.List(LingvodocID),
        mode = graphene.String(),
        filter = graphene.String(),
        sort_by_field = LingvodocID(),
        is_edit_mode = graphene.Boolean(),
        is_case_sens = graphene.Boolean(),
        is_ascending = graphene.Boolean(),
        offset = graphene.Int(),
        limit = graphene.Int())

    authors = graphene.List('lingvodoc.schema.gql_user.User')
    roles = graphene.Field(UserAndOrganizationsRoles)
    role_check = graphene.Boolean(subject = graphene.String(required = True), action = graphene.String(required = True))

    statistic = (

        graphene.Field(
            ObjectVal,
            starting_time = graphene.Int(),
            ending_time = graphene.Int(),
            disambiguation_flag = graphene.Boolean()))

    is_template = graphene.Boolean()
    counter = graphene.Int(mode=graphene.String())
    last_modified_at = graphene.Float()

    is_hidden_for_client = graphene.Boolean()
    has_valency_data = graphene.Boolean()
    has_adverb_data = graphene.Boolean()
    new_valency_data_count = graphene.Int()
    new_adverb_data_count = graphene.Int()

    dbType = dbPerspective

    entries_total = 0

    class Meta:
        interfaces = (CommonFieldsComposite, StateHolder)

    def check_is_hidden_for_client(self, info):
        """
        Checks if the perspective is hidden for the current client.

        Perspective is hidden for the current client if either it or its dictionary status is 'Hidden' and
        it is not in the 'Available dictionaries' list for the client, see 'def resolve_dictionaries()' in
        query.py switching based on 'mode'.
        """

        try:
            return self.is_hidden_for_client_flag

        except AttributeError:
            pass

        # See get_hidden() in models.py.

        hidden_id = (

            DBSession

                .query(
                    dbTranslationGist.client_id,
                    dbTranslationGist.object_id)

                .join(dbTranslationAtom)

                .filter(
                    dbTranslationGist.type == 'Service',
                    dbTranslationAtom.content == 'Hidden',
                    dbTranslationAtom.locale_id == 2)

                .first())

        # Checking if either the perspective or its dictionary has 'Hidden' status.

        is_hidden = (
            self.dbObject.state_translation_gist_client_id == hidden_id[0] and
            self.dbObject.state_translation_gist_object_id == hidden_id[1])

        if not is_hidden:

            is_hidden = (

                DBSession

                    .query(
                        and_(
                            dbDictionary.state_translation_gist_client_id == hidden_id[0],
                            dbDictionary.state_translation_gist_object_id == hidden_id[1]))

                    .filter(
                        dbDictionary.client_id == self.dbObject.parent_client_id,
                        dbDictionary.object_id == self.dbObject.parent_object_id)

                    .scalar())

        if not is_hidden:

            self.is_hidden_for_client_flag = False
            return False

        # Perspective is hidden, checking if it's hidden for the client.

        client_id = info.context.request.authenticated_userid

        if not client_id:

            self.is_hidden_for_client_flag = True
            return True

        user = dbClient.get_user_by_client_id(client_id)

        if user.id == 1:

            self.is_hidden_for_client_flag = False
            return False

        # Not an admin, we check if the perspective's dictionary is available for the client, see 'available
        # dictionaries' branch in resolve_dictionaries() in query.py.

        exists_query = (

            DBSession

                .query(
                    literal(1))

                .filter(
                    user_to_group_association.c.user_id == user.id,
                    dbGroup.id == user_to_group_association.c.group_id,
                    dbBaseGroup.id == dbGroup.base_group_id,

                    or_(
                        and_(
                            dbGroup.subject_override,
                            or_(
                                dbBaseGroup.dictionary_default,
                                dbBaseGroup.perspective_default)),
                        and_(
                            dbGroup.subject_client_id == self.dbObject.client_id,
                            dbGroup.subject_object_id == self.dbObject.object_id),
                        and_(
                            dbGroup.subject_client_id == self.dbObject.parent_client_id,
                            dbGroup.subject_object_id == self.dbObject.parent_object_id,
                            dbBaseGroup.dictionary_default)))

                .exists())

        is_available = (

            DBSession
                .query(exists_query)
                .scalar())

        self.is_hidden_for_client_flag = not is_available
        return self.is_hidden_for_client_flag

    # @fetch_object()
    # def resolve_additional_metadata(self, args, context, info):
    #     return self.dbObject.additional_metadata

    # @fetch_object('translation')
    # def resolve_translation(self, args, context, info):
    #     return self.dbObject.get_translation(context.get('locale_id'))

    @fetch_object('is_template')
    def resolve_is_template(self, info):
        return self.dbObject.is_template

    @fetch_object('tree') # tested
    def resolve_tree(self, info):

        dictionary_db = self.dbObject.parent
        dictionary = Dictionary(id = dictionary_db.id)

        return [self] + dictionary.resolve_tree(info)

    @fetch_object('columns') # tested
    def resolve_columns(self, info):
        columns = DBSession.query(dbColumn).filter_by(parent=self.dbObject, marked_for_deletion=False).order_by(dbColumn.position).all()
        result = list()
        for dbfield in columns:
            gr_field_obj = Column(id=[dbfield.client_id, dbfield.object_id])
            gr_field_obj.dbObject = dbfield
            result.append(gr_field_obj)
        return result

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

    @fetch_object('last_modified_at')
    def resolve_last_modified_at(self, info):
        """
        Perspective's last modification time, defined as latest time of creation or deletion of the
        perspective and all its lexical entries and entities.
        """

        # select
        #   max((value ->> 'deleted_at') :: float)
        #
        #   from
        #     ObjectTOC,
        #     jsonb_each(additional_metadata)
        #
        #   where
        #     client_id = <client_id> and
        #     object_id = <object_id>;

        deleted_at_query = (

            DBSession

            .query(
                func.max(cast(
                    column('value').op('->>')('deleted_at'),
                    sqlalchemy.Float)))

            .select_from(
                ObjectTOC,
                func.jsonb_each(ObjectTOC.additional_metadata))

            .filter(
                ObjectTOC.client_id == self.dbObject.client_id,
                ObjectTOC.object_id == self.dbObject.object_id,
                ObjectTOC.additional_metadata != JSONB.NULL))

        # Query for last modification time of the perspective's lexical entries and entities.

        sql_str = ('''

            select

              max(
                greatest(

                  extract(epoch from L.created_at),

                  (select
                    max((value ->> 'deleted_at') :: float)

                    from
                      jsonb_each(OL.additional_metadata)),

                  (select

                    max(
                      greatest(

                        extract(epoch from E.created_at),

                        (select
                          max((value ->> 'deleted_at') :: float)

                          from
                            jsonb_each(OE.additional_metadata))))

                    from
                      public.entity E,
                      ObjectTOC OE

                    where
                      E.parent_client_id = L.client_id and
                      E.parent_object_id = L.object_id and
                      OE.client_id = E.client_id and
                      OE.object_id = E.object_id and
                      OE.additional_metadata != 'null' :: jsonb)))

            from
              lexicalentry L,
              ObjectTOC OL

            where
              L.parent_client_id = :client_id and
              L.parent_object_id = :object_id and
              OL.client_id = L.client_id and
              OL.object_id = L.object_id and
              OL.additional_metadata != 'null' :: jsonb

            ''')

        # Complete query for the perspective, excluding created_at which we already have.

        DBSession.execute(
            'set extra_float_digits to 3;')

        result = (

            DBSession

            .query(
                  func.greatest(
                      deleted_at_query.label('deleted_at'),
                      Grouping(sqlalchemy.text(sql_str))))

            .params({
                'client_id': self.dbObject.client_id,
                'object_id': self.dbObject.object_id})

            .scalar())

        if result is not None:

            return max(
                self.dbObject.created_at,
                result)

        else:

            return self.dbObject.created_at

    @fetch_object()
    def resolve_is_hidden_for_client(self, info):
        """
        If the perspective is hidden for the current client.
        """

        return self.check_is_hidden_for_client(info)

    def resolve_has_valency_data(self, info):
        """
        If the perspective has valency annotation data.
        """

        exists_query = (

            DBSession

                .query(
                    literal(1))

                .filter(
                    dbValencySourceData.perspective_client_id == self.id[0],
                    dbValencySourceData.perspective_object_id == self.id[1])

                .exists())

        return (

            DBSession
                .query(exists_query)
                .scalar())

    def resolve_has_adverb_data(self, info):
        """
        If the perspective has adverb annotation data.
        """

        exists_query = (
            DBSession

                .query(
                    literal(1))

                .filter(
                    dbValencySourceData.perspective_client_id == self.id[0],
                    dbValencySourceData.perspective_object_id == self.id[1],
                    dbValencyParserData.id == dbValencySourceData.id,
                    dbValencyParserData.hash_adverb != '')

                .exists())

        return (
            DBSession
                .query(exists_query)
                .scalar())

    def resolve_new_valency_data_count(self, info):
        """
        How many unprocessed valency sources perspective has.
        """

        debug_flag = False

        total_hash_union = (

            union(

                DBSession

                    .query(

                        func.encode(
                            func.digest(
                                dbParserResult.content, 'sha256'),
                            'hex')

                            .label('hash'))

                    .filter(
                        dbLexicalEntry.parent_client_id == self.id[0],
                        dbLexicalEntry.parent_object_id == self.id[1],
                        dbLexicalEntry.marked_for_deletion == False,
                        dbEntity.parent_client_id == dbLexicalEntry.client_id,
                        dbEntity.parent_object_id == dbLexicalEntry.object_id,
                        dbEntity.marked_for_deletion == False,
                        dbPublishingEntity.client_id == dbEntity.client_id,
                        dbPublishingEntity.object_id == dbEntity.object_id,
                        dbPublishingEntity.published == True,
                        dbPublishingEntity.accepted == True,
                        dbParserResult.entity_client_id == dbEntity.client_id,
                        dbParserResult.entity_object_id == dbEntity.object_id,
                        dbParserResult.marked_for_deletion == False),

                DBSession

                    .query(

                        cast(
                            dbEntity.additional_metadata['hash'],
                            sqlalchemy.UnicodeText)

                            .label('hash'))

                    .filter(
                        dbLexicalEntry.parent_client_id == self.id[0],
                        dbLexicalEntry.parent_object_id == self.id[1],
                        dbLexicalEntry.marked_for_deletion == False,
                        dbEntity.parent_client_id == dbLexicalEntry.client_id,
                        dbEntity.parent_object_id == dbLexicalEntry.object_id,
                        dbEntity.marked_for_deletion == False,
                        dbEntity.content.ilike('%.eaf'),
                        dbEntity.additional_metadata.contains({'data_type': 'elan markup'}),
                        dbPublishingEntity.client_id == dbEntity.client_id,
                        dbPublishingEntity.object_id == dbEntity.object_id,
                        dbPublishingEntity.published == True,
                        dbPublishingEntity.accepted == True))

                .alias())

        total_hash_subquery = (

            DBSession
                .query(total_hash_union)
                .subquery())

        total_hash_count = (

            DBSession
                .query(total_hash_union)
                .count())

        if debug_flag:
            log.debug(
                f'total_hash_count: {total_hash_count}')

        has_hash_union = (

            union(

                DBSession

                    .query(
                        dbValencyParserData.hash)

                    .filter(
                        dbValencySourceData.perspective_client_id == self.id[0],
                        dbValencySourceData.perspective_object_id == self.id[1],
                        dbValencyParserData.id == dbValencySourceData.id),

                DBSession

                    .query(
                        dbValencyEafData.hash)

                    .filter(
                        dbValencySourceData.perspective_client_id == self.id[0],
                        dbValencySourceData.perspective_object_id == self.id[1],
                        dbValencyEafData.id == dbValencySourceData.id))

                .alias())

        has_hash_count = (

            DBSession
                .query(has_hash_union)
                .count())

        if debug_flag:
            log.debug(
                f'has_hash_count: {has_hash_count}')

        new_hash_count = (

            DBSession

                .query(
                    total_hash_subquery.c.hash)

                .filter(
                    total_hash_subquery.c.hash.notin_(
                        has_hash_union))

                .count())

        if debug_flag:

            log.debug(
                f'new_hash_count: {new_hash_count}')

        return new_hash_count + (has_hash_count > total_hash_count)

    def resolve_new_adverb_data_count(self, info):
        """
        How many unprocessed adverb sources perspective has.
        """

        debug_flag = False

        ready_hash_subquery = (
            DBSession

                .query(

                    func.encode(
                        func.digest(
                            dbParserResult.content, 'sha256'),
                        'hex')

                        .label('hash'))

                .filter(
                    dbLexicalEntry.parent_client_id == self.id[0],
                    dbLexicalEntry.parent_object_id == self.id[1],
                    dbLexicalEntry.marked_for_deletion == False,
                    dbEntity.parent_client_id == dbLexicalEntry.client_id,
                    dbEntity.parent_object_id == dbLexicalEntry.object_id,
                    dbEntity.marked_for_deletion == False,
                    dbPublishingEntity.client_id == dbEntity.client_id,
                    dbPublishingEntity.object_id == dbEntity.object_id,
                    dbPublishingEntity.published == True,
                    dbPublishingEntity.accepted == True,
                    dbParserResult.entity_client_id == dbEntity.client_id,
                    dbParserResult.entity_object_id == dbEntity.object_id,
                    dbParserResult.marked_for_deletion == False)

                .subquery())

        ready_hash_count = (
            DBSession
                .query(ready_hash_subquery)
                .count())

        has_hash_subquery = (
            DBSession

                .query(
                    dbValencyParserData.hash_adverb)

                .filter(
                    dbValencySourceData.perspective_client_id == self.id[0],
                    dbValencySourceData.perspective_object_id == self.id[1],
                    dbValencyParserData.id == dbValencySourceData.id,
                    dbValencyParserData.hash_adverb != '')

                .subquery())

        has_hash_count = (
            DBSession
                .query(has_hash_subquery)
                .count())

        if debug_flag:
            log.debug(
                f'ready_hash_count: {ready_hash_count}\n'
                f'has_hash_count: {has_hash_count}')

        new_hash_count = (
            DBSession

                .query(
                    ready_hash_subquery.c.hash)

                .filter(
                    ready_hash_subquery.c.hash.notin_(
                        has_hash_subquery))

                .count())

        if debug_flag:

            log.debug(
                f'new_hash_count: {new_hash_count}')

        # Actually here we answer if database has sources with old hash_adverbs,
        # with wrong (maybe deleted) related parser results or duplicate sources
        return new_hash_count + (has_hash_count > ready_hash_count)

    @fetch_object()
    def resolve_lexical_entries(self, info, ids=None,
                                mode=None, authors=None, clients=None,
                                start_date=None, end_date=None, position=1,
                                offset = 0, limit = 0, **kwargs):

        if self.check_is_hidden_for_client(info):
            return []

        # result = list()
        # request = info.context.get('request')

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
        lexical_entries = (
            entries_with_entities(lexes, accept, delete, mode, publish, check_perspective = False, **kwargs))

        # If we were asked for specific lexical entries, we try to return them in creation order.

        if ids is not None:
            lexical_entries.sort(key = lambda e: (e.dbObject.created_at, e.dbObject.object_id))

        self.entries_total = len(lexical_entries)

        # Pagination
        lexical_entries = lexical_entries[offset:]
        if limit > 0:
            lexical_entries = lexical_entries[:offset + limit]

        return lexical_entries

    def resolve_perspective_page(
            self,
            info,
            **kwargs):

        return PerspectivePage(
            lexical_entries = self.resolve_lexical_entries(info, **kwargs),
            entries_total = self.entries_total)

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
    def resolve_role_check(self, info, subject = '', action = ''):

        # Checking for specified permission for the current user for the perspective.

        return (
            info.context.acl_check_if(
                action, subject, (self.dbObject.client_id, self.dbObject.object_id)))

    @fetch_object()
    def resolve_statistic(
        self,
        info,
        starting_time = None,
        ending_time = None,
        disambiguation_flag = False):

        return (

            statistics.new_format(
                statistics.stat_perspective(
                    self.id,
                    starting_time,
                    ending_time,
                    disambiguation_flag,
                    locale_id = info.context.locale_id)))


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
        fields = graphene.List(ObjectVal)

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

        field_info_list = args.get('fields')

        dbperspective = create_perspective(id=id,
                                parent_id=parent_id,
                                translation_gist_id=translation_gist_id,
                                additional_metadata=additional_metadata,
                                import_source=import_source,
                                import_hash=import_hash,
                                is_template=is_template
                                )

        perspective_id = (
            (dbperspective.client_id, dbperspective.object_id))

        perspective = DictionaryPerspective(id = perspective_id)
        perspective.dbObject = dbperspective

        # Creating fields, if required.

        if field_info_list:

            log.debug(
                '\nfield_info_list:\n' +
                pprint.pformat(
                    field_info_list, width = 192))

            counter = 0
            fake_id_dict = {}

            for field_info in field_info_list:

                counter += 1

                self_id = field_info['self_id']

                if self_id is not None:

                    if self_id not in fake_id_dict:
                        raise ResponseError(f'Unknown fake id \'{self_id}\'.')

                    self_id = fake_id_dict[self_id]

                persp_to_field = (

                    create_dictionary_persp_to_field(
                        id = (client_id, None),
                        parent_id = perspective_id,
                        field_id = field_info['field_id'],
                        self_id = self_id,
                        link_id = field_info['link_id'],
                        position = counter))

                if 'id' in field_info:

                    fake_id_dict[field_info['id']] = (
                        (persp_to_field.client_id, persp_to_field.object_id))

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
        additional_metadata = ObjectVal()

    perspective = graphene.Field(DictionaryPerspective)
    triumph = graphene.Boolean()

    @staticmethod
    @acl_check_by_id('edit', 'perspective')
    def mutate(root, info, **args):
        id = args.get("id")
        client_id = id[0]
        object_id = id[1]
        parent_id = args.get('parent_id')
        additional_metadata = args.get('additional_metadata')
        # dbperspective = DBSession.query(dbPerspective).filter_by(client_id=client_id, object_id=object_id).first()
        dbperspective = CACHE.get(objects =
            {
                dbPerspective : ((client_id, object_id), )
            },
        DBSession=DBSession)
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
            # dbparent_dictionary = DBSession.query(dbDictionary).filter_by(client_id=parent_client_id,
            #                                                               object_id=parent_object_id).first()
            dbparent_dictionary = CACHE.get(objects=
                {
                    dbDictionary : (parent_id, )
                },
            DBSession=DBSession)
            if not dbparent_dictionary:
                raise ResponseError(message="Error: No such dictionary in the system")
            dbperspective.parent_client_id = parent_client_id
            dbperspective.parent_object_id = parent_object_id

        update_metadata(dbperspective, additional_metadata)

        CACHE.set(objects = [dbperspective,], DBSession=DBSession)
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
        # dbperspective = DBSession.query(dbPerspective).filter_by(client_id=client_id, object_id=object_id).first()
        dbperspective = CACHE.get(objects =
            {
                dbPerspective : ((client_id, object_id), )
            },
        DBSession=DBSession)
        if dbperspective and not dbperspective.marked_for_deletion:
            dbperspective.state_translation_gist_client_id = state_translation_gist_client_id
            dbperspective.state_translation_gist_object_id = state_translation_gist_object_id
            atom = DBSession.query(dbTranslationAtom).filter_by(parent_client_id=state_translation_gist_client_id,
                                                              parent_object_id=state_translation_gist_object_id,
                                                              locale_id=info.context.get('locale_id')).first()
            perspective = DictionaryPerspective(id=[dbperspective.client_id, dbperspective.object_id],
                                                status=atom.content)
            perspective.dbObject = dbperspective
            CACHE.set(objects = [dbperspective,], DBSession=DBSession)
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
        # dbperspective = DBSession.query(dbPerspective).filter_by(client_id=perspective_client_id, object_id=perspective_object_id).first()
        dbperspective = CACHE.get(objects =
            {
                dbPerspective : (args.get('id'), )
            },
        DBSession=DBSession)
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
        CACHE.set(objects = [dbperspective,], DBSession=DBSession)
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
        # dbperspective = DBSession.query(dbPerspective).filter_by(client_id=perspective_client_id,
        #                                                          object_id=perspective_object_id).first()
        dbperspective = CACHE.get(objects =
            {
                dbPerspective : (args.get('id'), )
            },
        DBSession=DBSession)
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
        CACHE.set(objects = [dbperspective,], DBSession=DBSession)
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

    triumph = graphene.Boolean()
    locale_id = graphene.Int()
    perspective = graphene.Field(DictionaryPerspective)

    @staticmethod
    @acl_check_by_id('edit', 'perspective')
    def mutate(root, info, **args):
        content = args.get('content')
        client_id, object_id = args.get('id')
        # dbperspective = DBSession.query(dbPerspective).filter_by(client_id=client_id, object_id=object_id).first()
        dbperspective = CACHE.get(objects =
            {
                dbPerspective : ((client_id, object_id), )
            },
        DBSession=DBSession)
        if not dbperspective:
            raise ResponseError(message="No such perspective in the system")
        locale_id = args.get("locale_id")

        if 'atom_id' in args:

            atom_id = args['atom_id']

            dbtranslationatom = (

                DBSession
                    .query(dbTranslationAtom)
                    .filter_by(
                        client_id = atom_id[0],
                        object_id = atom_id[1])
                    .first())

        else:

            dbtranslationatom = (

                DBSession
                    .query(dbTranslationAtom)
                    .filter_by(
                        parent_client_id=dbperspective.translation_gist_client_id,
                        parent_object_id=dbperspective.translation_gist_object_id,
                        locale_id=locale_id)
                    .first())

        if dbtranslationatom:
            if dbtranslationatom.locale_id == locale_id:
                key = "translation:%s:%s:%s" % (
                    str(dbtranslationatom.parent_client_id),
                    str(dbtranslationatom.parent_object_id),
                    str(dbtranslationatom.locale_id))
                CACHE.rem(key)
                key = "translations:%s:%s" % (
                    str(dbtranslationatom.parent_client_id),
                    str(dbtranslationatom.parent_object_id))
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
        if not dbperspective or dbperspective.marked_for_deletion:
            raise ResponseError(message="No such perspective in the system")
        settings = info.context["request"].registry.settings
        if 'desktop' in settings:
            real_delete_perspective(dbperspective, settings)
        else:
            del_object(dbperspective, "delete_perspective", info.context.get('client_id'))
        perspective = DictionaryPerspective(id=[dbperspective.client_id, dbperspective.object_id])
        perspective.dbObject = dbperspective
        return DeleteDictionaryPerspective(perspective=perspective, triumph=True)


class UndeleteDictionaryPerspective(graphene.Mutation):

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
        if not dbperspective:
            raise ResponseError(message="No such perspective in the system")
        if not dbperspective.marked_for_deletion:
            raise ResponseError(message="Perspective is not deleted")
        undel_object(dbperspective, "undelete_perspective", info.context.get('client_id'))
        perspective = DictionaryPerspective(id=[dbperspective.client_id, dbperspective.object_id])
        perspective.dbObject = dbperspective
        return UndeleteDictionaryPerspective(perspective=perspective, triumph=True)
