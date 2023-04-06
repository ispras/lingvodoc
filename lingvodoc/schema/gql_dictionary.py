from collections import defaultdict
import datetime
import logging
import pprint

import graphene

from lingvodoc.cache.caching import CACHE

from lingvodoc.models import (
    BaseGroup as dbBaseGroup,
    Client as dbClient,
    DBSession,
    Dictionary as dbDictionary,
    DictionaryPerspective as dbPerspective,
    Entity as dbEntity,
    Grant as dbGrant,
    Group as dbGroup,
    JSONB,
    Language as dbLanguage,
    LexicalEntry as dbLexicalEntry,
    ObjectTOC,
    PublishingEntity as dbPublishingEntity,
    TranslationAtom as dbTranslationAtom,
    TranslationGist as dbTranslationGist,
    ValencySourceData as dbValencySourceData,
    ValencySentenceData as dbValencySentenceData,
    ValencyInstanceData as dbValencyInstanceData,
    ValencyAnnotationData as dbValencyAnnotationData,
)

from lingvodoc.utils.creation import create_gists_with_atoms, update_metadata, add_user_to_group

from lingvodoc.schema.gql_holders import (
    LingvodocObjectType,
    CommonFieldsComposite,
    StateHolder,
    fetch_object,
    del_object,
    undel_object,
    client_id_check,
    ResponseError,
    ObjectVal,
    acl_check_by_id,
    LingvodocID,
    UserAndOrganizationsRoles,
    get_published_translation_gist_id_cte_query
)

import sqlalchemy
from sqlalchemy import and_, cast, column, extract, func, or_, tuple_, literal
from sqlalchemy.orm import aliased
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.sql.expression import Grouping

from lingvodoc.utils import statistics, explain_analyze
from lingvodoc.utils.creation import (create_perspective,
                                      create_dbdictionary,
                                      create_dictionary_persp_to_field,
                                      edit_role)
from lingvodoc.utils.deletion import real_delete_dictionary
from lingvodoc.utils.search import translation_gist_search


# Setting up logging.
log = logging.getLogger(__name__)


class UserToRoles(graphene.ObjectType):
    id_user = graphene.Int()
    roles = graphene.List(graphene.Int)

    def resolve_roles(self, info):
        return self.user_id

    def resolve_id_user(self, info):
        return self.roles


class Dictionary(LingvodocObjectType):  # tested
    # TODO: resolve_dataType(?)
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
     #category                         | bigint                      |
     #domain                           | bigint                      |
     #additional_metadata              | jsonb                       |
     + status
     + .translation
     + dataType
    Test:
    query myQuery {
      dictionary(id: [126, 3]) {
        id
        translation
        created_at
        parent_id
        marked_for_deletion
        translation_gist_id
        additional_metadata {
          blob_description
        }
         perspectives{id translation}
         roles{
             roles_users
             roles_organizations
         }
      }
    }
    or

          dictionary(id: [126, 3], starting_time: 0, ending_time: 100) { statistic   ... # todo timestamp
    """

    dbType = dbDictionary
    category = graphene.Int()
    domain = graphene.Int()
    roles = graphene.Field(UserAndOrganizationsRoles)
    statistic = graphene.Field(ObjectVal, starting_time=graphene.Int(), ending_time=graphene.Int())
    last_modified_at = graphene.Float()

    # If the dictionary in 'Published' or 'Limited access' state and has at least one 'Published' or
    # 'Limited access' perspective with some additional checks based on whether the dictionary is deleted or
    # not.
    #
    # The same as parameter 'published' of the field 'dictionaries' of Language type, see
    # gql_language.py.
    #
    published = graphene.Boolean()

    tree = graphene.List(CommonFieldsComposite)

    perspectives = graphene.List(
        'lingvodoc.schema.gql_dictionaryperspective.DictionaryPerspective',
        with_phonology_data = graphene.Boolean(),
        with_verb_data = graphene.Boolean())

    persp = graphene.Field('lingvodoc.schema.gql_dictionaryperspective.DictionaryPerspective')
    class Meta:
        interfaces = (CommonFieldsComposite, StateHolder)


    @property
    def persp_class(self):
        return self._meta.fields['persp'].type

    @fetch_object('last_modified_at')
    def resolve_last_modified_at(self, info):
        """
        Dictionary's last modification time, defined as latest time of creation or deletion of the
        dictionary and all its perspectives, lexical entries and entities.
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
                ObjectTOC.client_id == self.id[0],
                ObjectTOC.object_id == self.id[1],
                ObjectTOC.additional_metadata != JSONB.NULL))

        # Query for last modification time of the dictionary's perspectives, lexical entries and entities.

        sql_str = ('''

            select

              max(
                greatest(

                  extract(epoch from P.created_at),

                  (select
                    max((value ->> 'deleted_at') :: float)

                    from
                      jsonb_each(OP.additional_metadata)),

                  (select

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
                      L.parent_client_id = P.client_id and
                      L.parent_object_id = P.object_id and
                      OL.client_id = L.client_id and
                      OL.object_id = L.object_id and
                      OL.additional_metadata != 'null' :: jsonb)))

            from
              dictionaryperspective P,
              ObjectTOC OP

            where
              P.parent_client_id = :client_id and
              P.parent_object_id = :object_id and
              OP.client_id = P.client_id and
              OP.object_id = P.object_id and
              OP.additional_metadata != 'null' :: jsonb

            ''')

        # Complete query for the dictionary, excluding created_at which we already have.

        DBSession.execute(
            'set extra_float_digits to 3;');

        result = (

            DBSession

            .query(
                func.greatest(
                    deleted_at_query.label('deleted_at'),
                    Grouping(sqlalchemy.text(sql_str))))

            .params({
                'client_id': self.id[0],
                'object_id': self.id[1]})

            .scalar())

        if result is not None:

            return max(
                self.dbObject.created_at,
                result)

        else:

            return self.dbObject.created_at

    def published_search(
        self,
        __debug_flag__ = False):

        db_published_gist = translation_gist_search('Published')

        published_client_id = db_published_gist.client_id
        published_object_id = db_published_gist.object_id

        db_limited_gist = translation_gist_search('Limited access')

        limited_client_id = db_limited_gist.client_id
        limited_object_id = db_limited_gist.object_id

        if (
            (self.dbObject.state_translation_gist_client_id != published_client_id or
                self.dbObject.state_translation_gist_object_id != published_object_id) and
            (self.dbObject.state_translation_gist_client_id != limited_client_id or
                self.dbObject.state_translation_gist_object_id != limited_object_id)):

            return False

        perspective_query = (

            DBSession

                .query(literal(1))

                .filter(
                    dbPerspective.parent_client_id == self.id[0],
                    dbPerspective.parent_object_id == self.id[1])

                .filter(
                    or_(
                        and_(dbPerspective.state_translation_gist_client_id == published_client_id,
                            dbPerspective.state_translation_gist_object_id == published_object_id),
                        and_(dbPerspective.state_translation_gist_client_id == limited_client_id,
                            dbPerspective.state_translation_gist_object_id == limited_object_id))))

        if not self.dbObject.marked_for_deletion:

            perspective_query = (

                perspective_query.filter(
                    dbPerspective.marked_for_deletion == False))

        return (

            DBSession
                .query(perspective_query.exists())
                .scalar())

    def published_cte_str(
        self,
        __debug_flag__ = False):

        sql_str = ('''

            with translation_gist_id_set as
            (
              select
              T.client_id, T.object_id

              from
              translationgist T,
              translationatom A

              where
              T.marked_for_deletion = false and
              T.type = 'Service' and
              A.parent_client_id = T.client_id and
              A.parent_object_id = T.object_id and
              A.locale_id = 2 and
              A.marked_for_deletion = false and
              (A.content = 'Published' or
                A.content = 'Limited access')
            )

            select

            (:state_translation_gist_client_id,
              :state_translation_gist_object_id) in
              (select * from translation_gist_id_set)

              and

              exists (
                select 1
                from dictionaryperspective P
                where
                P.parent_client_id = :client_id and
                P.parent_object_id = :object_id and
                {0}
                (P.state_translation_gist_client_id,
                  P.state_translation_gist_object_id) in
                  (select * from translation_gist_id_set));

            '''.format(
                '' if self.dbObject.marked_for_deletion else
                    'P.marked_for_deletion = false and'))

        param_dict = {
            'client_id': self.id[0],
            'object_id': self.id[1],
            'state_translation_gist_client_id': self.dbObject.state_translation_gist_client_id,
            'state_translation_gist_object_id': self.dbObject.state_translation_gist_object_id}

        if __debug_flag__:

            row_list = (

                DBSession.execute(
                    'explain analyze\n' + sql_str,
                    param_dict).fetchall())

            log.debug(''.join(
                '\n' + row[0] for row in row_list))

        return (DBSession
            .execute(sql_str, param_dict)
            .scalar())

    def published_cte_orm(
        self,
        __debug_flag__ = False):

        # NOTE: we have to use pubished CTE query and not just published CTE because otherwise the CTE won't
        # be used as proper via WITH and will be just inserted literally two times.

        published_cte_query = (
            get_published_translation_gist_id_cte_query())

        perspective_query = (DBSession

            .query(dbPerspective)

            .filter(
                dbPerspective.parent_client_id == self.id[0],
                dbPerspective.parent_object_id == self.id[1],

                tuple_(
                    dbPerspective.state_translation_gist_client_id,
                    dbPerspective.state_translation_gist_object_id)

                    .in_(published_cte_query)))

        if not self.dbObject.marked_for_deletion:

            perspective_query = perspective_query.filter(
                dbPerspective.marked_for_deletion == False)

        published_query = (DBSession

            .query(

                and_(

                    tuple_(
                        self.dbObject.state_translation_gist_client_id,
                        self.dbObject.state_translation_gist_object_id)

                        .in_(published_cte_query),

                    perspective_query.exists())))

        if __debug_flag__:

            log.debug(str(
                published_query.statement.compile(compile_kwargs = {'literal_binds': True})))

            row_list = (
                DBSession.execute(
                    explain_analyze(published_query)).fetchall())

            log.debug(''.join(
                '\n' + row[0] for row in row_list))

        return published_query.scalar()

    @fetch_object()
    def resolve_published(self, info, __debug_flag__ = False):

        if __debug_flag__:

            import time

            t0 = time.time()

            for i in range(256):
                self.published_search()

            t1 = time.time()

            for i in range(256):
                self.published_cte_str()

            t2 = time.time()

            for i in range(256):
                self.published_cte_orm()

            t3 = time.time()

            log.warn(
                f'\nt1 - t0: {t1 - t0:.6f}s'
                f'\nt2 - t1: {t2 - t1:.6f}s'
                f'\nt3 - t2: {t3 - t2:.6f}s')

            result_search = self.published_search(True)

            result_str = self.published_cte_str(True)
            result_orm = self.published_cte_orm(True)

            log.warn((result_search, result_str, result_orm))

            return result_orm

        # Testing shows that direct query is the most optimal.

        return self.published_cte_str()

    @fetch_object()
    def resolve_tree(self, info):

        from .gql_language import Language

        language_db = self.dbObject.parent
        language = Language(id = language_db.id)

        return [self] + language.resolve_tree(info)

    @fetch_object()
    def resolve_statistic(self, info, starting_time=None, ending_time=None):
        #print(starting_time)
        if starting_time is None or ending_time is None:
            raise ResponseError(message="Time period is not chosen")
        locale_id = info.context.get('locale_id')
        current_statistics = statistics.stat_dictionary(self.id,
                                   starting_time,
                                   ending_time,
                                   locale_id=locale_id
                                                        )
        new_format_statistics = []

        for key, stat_dict in current_statistics.items():

            new_dict = {
                'user_id': key,
                'name': stat_dict['name']}

            # NOTE: 'lexical_entries' with underscore '_' for the new format.

            if 'lexical entries' in stat_dict:
                new_dict['lexical_entries'] = stat_dict['lexical entries']

            if 'entities' in stat_dict:
                new_dict['entities'] = stat_dict['entities']

            new_format_statistics.append(new_dict)

        log.debug(
            '\nnew format:\n{0}'.format(
                pprint.pformat(new_format_statistics, width = 144)))

        return new_format_statistics

    @fetch_object('perspectives')
    def resolve_perspectives(
        self,
        info,
        with_phonology_data = None,
        with_verb_data = None):

        if not self.id:
            raise ResponseError(message="Dictionary with such ID doesn`t exists in the system")

        child_persps_query = (

            DBSession

                .query(dbPerspective)

                .filter_by(
                    parent_client_id = self.id[0],
                    parent_object_id = self.id[1],
                    marked_for_deletion = False))

        # If required, filtering out pespectives without phonology data.
        #
        # Apparently, as comment in def resolve_perspectives() in query.py claims, filtering through id in
        # select group by is faster than through exists subquery. But what about join group by? Maybe an
        # experiment for later.

        if with_phonology_data is not None:

            dbMarkup = aliased(dbEntity, name = 'Markup')
            dbSound = aliased(dbEntity, name = 'Sound')

            dbPublishingMarkup = aliased(dbPublishingEntity, name = 'PublishingMarkup')
            dbPublishingSound = aliased(dbPublishingEntity, name = 'PublishingSound')

            phonology_query = (

                DBSession

                    .query(
                        dbLexicalEntry.parent_client_id,
                        dbLexicalEntry.parent_object_id)

                    .filter(
                        dbLexicalEntry.marked_for_deletion == False,
                        dbMarkup.parent_client_id == dbLexicalEntry.client_id,
                        dbMarkup.parent_object_id == dbLexicalEntry.object_id,
                        dbMarkup.marked_for_deletion == False,
                        dbMarkup.additional_metadata.contains({'data_type': 'praat markup'}),
                        dbPublishingMarkup.client_id == dbMarkup.client_id,
                        dbPublishingMarkup.object_id == dbMarkup.object_id,
                        dbPublishingMarkup.published == True,
                        dbPublishingMarkup.accepted == True,
                        dbSound.client_id == dbMarkup.self_client_id,
                        dbSound.object_id == dbMarkup.self_object_id,
                        dbSound.marked_for_deletion == False,
                        dbPublishingSound.client_id == dbSound.client_id,
                        dbPublishingSound.object_id == dbSound.object_id,
                        dbPublishingSound.published == True,
                        dbPublishingSound.accepted == True)

                    .group_by(
                        dbLexicalEntry.parent_client_id,
                        dbLexicalEntry.parent_object_id))

            id_tuple = (

                tuple_(
                    dbPerspective.client_id,
                    dbPerspective.object_id))

            child_persps_query = (

                child_persps_query.filter(

                    (id_tuple.in_ if with_phonology_data else
                        id_tuple.notin_)(

                        DBSession.query(
                            phonology_query.cte()))))

        # If required, filtering out perspectives without accepted verb valency data.

        if with_verb_data is not None:

            accepted_query = (

                DBSession

                    .query(
                        dbValencySourceData.perspective_client_id,
                        dbValencySourceData.perspective_object_id)

                    .filter(
                        dbValencySourceData.id == dbValencySentenceData.source_id,
                        dbValencySentenceData.id == dbValencyInstanceData.sentence_id,
                        dbValencyInstanceData.id == dbValencyAnnotationData.instance_id,
                        dbValencyAnnotationData.accepted == True)

                    .group_by(
                        dbValencySourceData.perspective_client_id,
                        dbValencySourceData.perspective_object_id))

            id_tuple = (

                tuple_(
                    dbPerspective.client_id,
                    dbPerspective.object_id))

            child_persps_query = (

                child_persps_query.filter(

                    (id_tuple.in_ if with_verb_data else
                        id_tuple.notin_)(

                        DBSession.query(
                            accepted_query.cte()))))

        perspectives = list()
        for persp in child_persps_query.all():
            persp_object = self.persp_class(id=[persp.client_id, persp.object_id])
            persp_object.dbObject = persp
            perspectives.append(persp_object)
        return perspectives

    @fetch_object(ACLSubject='dictionary_role', ACLKey='id')
    def resolve_roles(self, info):
        client_id, object_id = self.id
        # dictionary = DBSession.query(dbDictionary).filter_by(client_id=client_id, object_id=object_id).first()
        dictionary = CACHE.get(objects =
            {
                dbDictionary : ((client_id, object_id), )
            },
        DBSession=DBSession)
        if not dictionary or dictionary.marked_for_deletion:
            raise ResponseError(message="Dictionary with such ID doesn`t exists in the system")


        bases = DBSession.query(dbBaseGroup).filter_by(dictionary_default=True)
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

    @fetch_object('category')
    def resolve_category(self, info):
        return self.dbObject.category

    @fetch_object('domain')
    def resolve_domain(self, info):
        return self.dbObject.domain
###
# CrUd functions
#
###



class CreateDictionary(graphene.Mutation):
    """
    example:
    mutation {
      create_dictionary(id: [449, 2527], translation_gist_id: [714, 3], parent_id: [500, 121],
      additional_metadata: {hash: "1234567"}) {
        triumph
        dictionary {
          id
          translation
          marked_for_deletion
          created_at
          translation
          additional_metadata {
            hash
          }
        }
      }
    }

    complex_create:
    mutation CreateDictionaryMutation($parentId: LingvodocID!, $dictionaryTranslations: [ObjectVal]!, $perspectives: [ObjectVal]!) {
      create_dictionary(parent_id: $parentId, translation_atoms: $dictionaryTranslations, perspectives: $perspectives) {
        triumph
        __typename
      }
    }

    ============================
      # variables:
    ============================
    {
        "parentId": [
            508,
            36
        ],
        "dictionaryTranslations": [
            {
                "locale_id": 1,
                "content": "Test dict"
            }
        ],
        "perspectives": [
            {
                "translation_atoms": [
                    {
                        "locale_id": 1,
                        "content": "One"
                    }
                ],
                "fake_id": "0ce97e69-ece9-400b-a625-e7a20110246e3A",
                "fields": [
                    {
                        "field_id": [
                            1,
                            213
                        ],
                            "link_id": "2e3684b7-6d81-4d103-a10e10-295517ad2f75B"

                    },
                    {
                        "fake_id": "2914bee7-4ef8-4275-869b-af8cdf268631",
                        "self_id": null,
                        "link_id": null,
                        "field_id": [
                            66,
                            6
                        ]
                    },
                    {
                        "fake_id": "b33baa65-0314-4aa8-9c99-ab182bae765d",
                        "self_id": null,
                        "link_id": null,
                        "field_id": [
                            66,
                            8
                        ]
                    },
                    {
                        "fake_id": "386a5913-c209-47de-aafa-f5a14f59612e",
                        "self_id": null,
                        "link_id": null,
                        "field_id": [
                            66,
                            10
                        ]
                    },
                    {
                        "fake_id": "6aebd1a7-d105-495e-af2f-b118e53d939d",
                        "self_id": null,
                        "link_id": null,
                        "field_id": [
                            66,
                            12
                        ]
                    },
                    {
                        "fake_id": "8a8c9c8b-c127-42e7-a8bb-b51ac714331c",
                        "self_id": "6aebd1a7-d105-495e-af2f-b118e53d939d",
                        "link_id": null,
                        "field_id": [
                            66,
                            23
                        ]
                    }
                ]
            },
            {
                "translation_atoms": [
                    {
                        "locale_id": 1,
                        "content": "Two"
                    }
                ],
                "fake_id": "2e3684b7-6d81-4d103-a10e10-295517ad2f75B",
                "fields": [
                    {
                        "fake_id": "ZZ",
                        "self_id": null,
                        "link_id": null,
                        "field_id": [
                            66,
                            12
                        ]
                    },
                    {
                        "field_id": [
                            1,
                            213
                        ],


                            "link_id": "0ce97e69-ece9-400b-a625-e7a20110246e3A"

                    }
                ]
            }
        ]
    }
    """

    class Arguments:
        id = LingvodocID()
        translation_gist_id = LingvodocID()
        parent_id = LingvodocID(required=True)
        additional_metadata = ObjectVal()
        perspectives = graphene.List(ObjectVal)
        translation_atoms = graphene.List(ObjectVal)
        category = graphene.Int()
        domain = graphene.Int()

    class FieldInfo(object):
        id = None
        fake_id = None
        link_id = None
        field_id = None
        #field_fake_id = None
        self_id = None
        perspective_obj = None
        def __init__(self, perspective_obj=None):
            self.perspective_obj = perspective_obj

    dictionary = graphene.Field(Dictionary)
    triumph = graphene.Boolean()
    perspectives = graphene.List(Dictionary)
    translation_atoms = graphene.List(ObjectVal)

    @staticmethod
    def get_by_fake_id(fake_to_id, fake_id):
        if fake_id not in fake_to_id:
            raise ResponseError(message="Fake_ids don`t match")
        return fake_to_id[fake_id]

    @staticmethod
    @client_id_check()  # tested
    def mutate(root, info, **args):
        # TODO: complex_create with fields
        ids = args.get("id")
        client_id = ids[0] if ids else info.context["client_id"]
        object_id = ids[1] if ids else None
        parent_id = args.get('parent_id')
        tr_atoms = args.get("translation_atoms")
        translation_gist_id = args.get('translation_gist_id')
        translation_gist_id = create_gists_with_atoms(tr_atoms,
                                                      translation_gist_id,
                                                      [client_id,object_id],
                                                      gist_type="Dictionary")
        additional_metadata = args.get("additional_metadata")
        category = args.get("category")
        domain = args.get("domain")
        ids = [client_id, object_id]
        dbdictionary_obj = create_dbdictionary(id=ids,
                                               parent_id=parent_id,
                                               translation_gist_id=translation_gist_id,
                                               additional_metadata=additional_metadata,
                                               category=category,
                                               domain=domain)
        dictionary = Dictionary(id=[dbdictionary_obj.client_id, dbdictionary_obj.object_id])
        dictionary.dbObject = dbdictionary_obj

        persp_args = args.get("perspectives")
        # TODO:  rename it
        persp_fake_ids = dict()
        field_fake_ids = dict()
        persp_fields_list = defaultdict(list)
        if persp_args:
            for next_persp in persp_args:
                atoms_to_create = next_persp.get("translation_atoms")
                persp_translation_gist_id = next_persp.get("translation_gist_id")
                persp_translation_gist_id = create_gists_with_atoms(atoms_to_create,
                                                                    persp_translation_gist_id,
                                                                    [client_id,object_id],
                                                                    gist_type="Perspective")
                parent_id = [dbdictionary_obj.client_id, dbdictionary_obj.object_id]
                new_persp = create_perspective(id=(client_id, None),
                                        parent_id=parent_id,  # TODO: use all object attrs
                                        translation_gist_id=persp_translation_gist_id
                                        )

                if "fake_id" in next_persp:
                    perspective_fake_id = next_persp['fake_id']
                    persp_fake_ids[perspective_fake_id] = new_persp

                if "fields" in next_persp:
                    new_fields = next_persp["fields"]
                    for new_ptofield in new_fields:
                        field_info = CreateDictionary.FieldInfo(perspective_obj=new_persp)
                        if not "field_id" in new_ptofield:
                            raise ResponseError(message="One of fields in list has not field_id")
                        field_info.field_id = new_ptofield["field_id"]
                        if "self_id" in new_ptofield:
                            field_info.self_id = new_ptofield["self_id"]
                        if 'fake_id' in new_ptofield:
                            field_info.fake_id = new_ptofield['fake_id']
                        if "link_id" in new_ptofield:
                            field_info.link_id = new_ptofield['link_id']
                        persp_fields_list[new_persp].append(field_info)
            for persp in persp_fields_list:
                counter = 0
                fields = persp_fields_list[persp]
                for field in fields:
                    counter += 1
                    link_id = field.link_id
                    field_id = field.field_id
                    fake_id = field.fake_id
                    self_id = field.self_id
                    parent_id = (persp.client_id, persp.object_id)
                    if link_id:
                        persp_to_link = CreateDictionary.get_by_fake_id(persp_fake_ids, link_id)
                        link_id=(persp_to_link.client_id, persp_to_link.object_id)
                    if self_id:
                        parent_field = CreateDictionary.get_by_fake_id(field_fake_ids, self_id)
                        self_id = (parent_field.client_id, parent_field.object_id)
                    persp_to_field = create_dictionary_persp_to_field(id=(client_id, None),
                                                     parent_id=parent_id,
                                                     field_id=field_id,
                                                     self_id=self_id,
                                                     link_id=link_id,
                                                     position=counter)
                    if fake_id:
                        field_fake_ids[fake_id] = persp_to_field

        return CreateDictionary(dictionary=dictionary,
                                triumph=True)


class UpdateDictionary(graphene.Mutation):
    """
    example:
    mutation  {
        update_dictionary(id:[949,2492], additional_metadata: {hash:"new hash"}) {
            triumph
            dictionary{
                id
                translation
                marked_for_deletion
                created_at
                translation
                            additional_metadata{
             hash
            }
            }
        }
    }

    (this example works)
    returns:
    {
      "update_dictionary": {
        "triumph": true,
        "dictionary": {
          "id": [
            949,
            2492
          ],
          "translation": "Словарь башкирского языка",
          "marked_for_deletion": false,
          "created_at": "2017-08-16T10:25:35",
          "additional_metadata": {
            "hash": "new hash"
          }
        }
      }
    }
    """
    class Arguments:
        id = LingvodocID(required=True)
        translation_gist_id = LingvodocID()
        parent_id = LingvodocID()
        additional_metadata = ObjectVal()


    dictionary = graphene.Field(Dictionary)
    triumph = graphene.Boolean()

    @staticmethod
    def update_dictionary(ids,
                          parent_id=None,
                          translation_gist_id=None,
                          additional_metadata=None,
                          ):
        if not ids:
            raise ResponseError(message="dict id not found")
        # client_id, object_id = ids
        # db_dictionary = DBSession.query(dbDictionary).filter_by(client_id=client_id, object_id=object_id).first()
        db_dictionary = CACHE.get(objects =
            {
                dbDictionary : (ids, )
            },
        DBSession=DBSession)
        if not db_dictionary or db_dictionary.marked_for_deletion:
            raise ResponseError(message="Error: No such dictionary in the system")

        if parent_id:
            language_client_id, language_object_id = parent_id
            parent = DBSession.query(dbLanguage).filter_by(client_id=language_client_id, object_id = language_object_id)
            if not parent:
                raise ResponseError(message="Error: No such language in the system")
            db_dictionary.parent_client_id = language_client_id
            db_dictionary.parent_object_id = language_object_id
        if translation_gist_id:
            db_dictionary.translation_gist_client_id, translation_gist_object_id = translation_gist_id
        # location hook
        if additional_metadata:

            if "location" in additional_metadata:
                child_persps = DBSession.query(dbPerspective)\
                    .filter_by(parent=db_dictionary).all()
                for persp in child_persps:
                    if not persp.additional_metadata:
                        persp.additional_metadata = dict()
                    persp.additional_metadata["location"] = {
                                                                "location":
                                                                 {
                                                                  "type":"location",
                                                                  "content":
                                                                      additional_metadata["location"]
                                                                  }
                                                             }
                    flag_modified(persp, 'additional_metadata')

            if "authors" in additional_metadata:
                child_persps = DBSession.query(dbPerspective)\
                    .filter_by(parent=db_dictionary).all()
                for persp in child_persps:
                    if not persp.additional_metadata:
                        persp.additional_metadata = dict()
                    persp.additional_metadata['authors'] = {
                                                                 "type":"authors",
                                                                 "content": ",".join(additional_metadata["authors"])
                                                            }
                    flag_modified(persp, 'additional_metadata')
            if "blobs" in additional_metadata:
                additional_metadata['blobs'] = [{"client_id": i[0], "object_id": i[1]} for i in additional_metadata['blobs']]
                child_persps = DBSession.query(dbPerspective)\
                    .filter_by(parent=db_dictionary).all()
                for persp in child_persps:
                    if not persp.additional_metadata:
                        persp.additional_metadata = dict()
                    old_format_blobs = []
                    for blob in additional_metadata["blobs"]:
                        old_format_blobs.append( {'info': {'content':
                                                               blob,
                                                           'type': 'blob'

                                                           }
                                                  }
                                                )
                    persp.additional_metadata['info'] = {'content': old_format_blobs, 'type': 'list'}
                    flag_modified(persp, 'additional_metadata')

            if "sociolinguistics" in additional_metadata:

                child_persps = DBSession.query(dbPerspective) \
                    .filter_by(parent=db_dictionary).all()
                for persp in child_persps:
                    if not persp.additional_metadata:
                        persp.additional_metadata = dict()
                    persp.additional_metadata['sociolinguistics'] = {
                        "type": "sociolinguistics",
                        "content": additional_metadata["sociolinguistics"]
                    }
                    flag_modified(persp, 'additional_metadata')

        update_metadata(db_dictionary, additional_metadata)
        CACHE.set(objects = [db_dictionary,], DBSession=DBSession)
        return db_dictionary

    @staticmethod
    @acl_check_by_id('edit', 'dictionary')  # tested
    def mutate(root, info, **args):  # tested
        ids = args.get('id')
        if not ids:
            ids = (info.context["client_id"], None)
        parent_id = args.get('parent_id')
        translation_gist_id = args.get('translation_gist_id')
        additional_metadata = args.get('additional_metadata')
        dbdictionary = UpdateDictionary.update_dictionary(ids,
                                                          parent_id=parent_id,
                                                          translation_gist_id=translation_gist_id,
                                                          additional_metadata=additional_metadata,
                                                          )
        dictionary = Dictionary(id=[dbdictionary.client_id, dbdictionary.object_id])
        dictionary.dbObject = dbdictionary
        return UpdateDictionary(dictionary=dictionary, triumph=True)

class UpdateDictionaryStatus(graphene.Mutation):
    """
    mutation  {
        update_dictionary_status(id:[475, 2], state_translation_gist_id: [1, 123]) {
            triumph
            dictionary{
                id
                translation
                marked_for_deletion
                created_at
                status
                translation
            additional_metadata{
             hash
            }
            }
        }
    }
    """
    class Arguments:
        id = LingvodocID(required=True)
        state_translation_gist_id = LingvodocID(required=True)

    dictionary = graphene.Field(Dictionary)
    triumph = graphene.Boolean()

    @staticmethod
    @acl_check_by_id("edit", "dictionary_status")
    def mutate(root, info, **args):
        client_id, object_id = args.get('id')
        state_translation_gist_client_id, state_translation_gist_object_id = args.get('state_translation_gist_id')
        # dbdictionary = DBSession.query(dbDictionary).filter_by(client_id=client_id, object_id=object_id).first()
        dbdictionary = CACHE.get(objects =
            {
                dbDictionary : ((client_id, object_id), )
            },
        DBSession=DBSession)
        if dbdictionary and not dbdictionary.marked_for_deletion:
            dbdictionary.state_translation_gist_client_id = state_translation_gist_client_id
            dbdictionary.state_translation_gist_object_id = state_translation_gist_object_id
            atom = DBSession.query(dbTranslationAtom).filter_by(parent_client_id=state_translation_gist_client_id,
                                                              parent_object_id=state_translation_gist_object_id,
                                                              locale_id=info.context.get('locale_id')).first()
            dictionary = Dictionary(id=[dbdictionary.client_id, dbdictionary.object_id], status=atom.content)
            dictionary.dbObject = dbdictionary
            CACHE.set(objects = [dbdictionary,], DBSession=DBSession)
            return UpdateDictionaryStatus(dictionary=dictionary, triumph=True)
        raise ResponseError(message="No such dictionary in the system")


class UpdateDictionaryAtom(graphene.Mutation):
    """
    example:
mutation up{
	update_dictionary_atom(id: [2138, 5], locale_id: 2, content: "test6"){
		triumph
	}

}

    now returns:

    {
        "data": {
            "update_dictionary_atom": {
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
    dictionary = graphene.Field(Dictionary)

    @staticmethod
    @acl_check_by_id('edit', 'dictionary')  # tested
    def mutate(root, info, **args):
        content = args.get('content')
        client_id, object_id = args.get('id')


        # dbdictionary = DBSession.query(dbDictionary).filter_by(client_id=client_id, object_id=object_id).first()
        dbdictionary = CACHE.get(objects =
            {
                dbDictionary : ((client_id, object_id), )
            },
        DBSession=DBSession)
        if not dbdictionary:
            raise ResponseError(message="No such dictionary in the system")
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
                        parent_client_id=dbdictionary.translation_gist_client_id,
                        parent_object_id=dbdictionary.translation_gist_object_id,
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
                    raise ResponseError(message="No such dictionary in the system")
                args_atom = DBSession.query(dbTranslationAtom).filter_by(client_id=atom_client_id,
                                                                         object_id=atom_object_id).first()
                if not args_atom:
                    raise ResponseError(message="No such dictionary in the system")
                dbtranslationatom.locale_id = locale_id
        else:
            client = DBSession.query(dbClient).filter_by(id=client_id).first()
            user = client.user
            dbtranslationatom = dbTranslationAtom(client_id=client_id,
                                                object_id=None,
                                                parent_client_id=dbdictionary.translation_gist_client_id,
                                                parent_object_id=dbdictionary.translation_gist_object_id,
                                                locale_id=locale_id,
                                                content=content)
            DBSession.add(dbtranslationatom)
            DBSession.flush()
            if not object_id:
                basegroups = []
                basegroups += [DBSession.query(dbBaseGroup).filter_by(name="Can edit translationatom").first()]
                if not object_id:
                    groups = []
                    for base in basegroups:
                        group = dbGroup(subject_client_id=dbtranslationatom.client_id,
                                        subject_object_id=dbtranslationatom.object_id,
                                        parent=base)
                        groups += [group]
                    for group in groups:
                        add_user_to_group(user, group)

        dictionary = Dictionary(id=[dbdictionary.client_id, dbdictionary.object_id])
        dictionary.dbObject = dbdictionary
        return UpdateDictionaryAtom(dictionary=dictionary, triumph=True)

class AddDictionaryRoles(graphene.Mutation):
    """
        mutation myQuery {
            add_dictionary_roles(id: [1279,4], user_id:2 , roles_users:[7,10,11,14,19,25,17,33]){
						triumph

					}
        }
    """
    class Arguments:
        id = LingvodocID(required=True)
        user_id = graphene.Int(required=True)
        roles_users = graphene.List(graphene.Int)
        roles_organizations = graphene.List(graphene.Int)

    dictionary = graphene.Field(Dictionary)
    triumph = graphene.Boolean()

    @staticmethod
    @acl_check_by_id("create", "dictionary_role")
    def mutate(root, info, **args):
        dictionary_client_id, dictionary_object_id = args.get('id')
        user_id = args.get("user_id")
        roles_users = args.get('roles_users')
        roles_organizations = args.get('roles_organizations')
        # dbdictionary = DBSession.query(dbDictionary).filter_by(client_id=dictionary_client_id, object_id=dictionary_object_id).first()
        dbdictionary = CACHE.get(objects =
            {
                dbDictionary : (args.get('id'), )
            },
        DBSession=DBSession)
        client_id = info.context.get('client_id')
        if not dbdictionary or dbdictionary.marked_for_deletion:
            raise ResponseError(message="No such dictionary in the system")
        if roles_users:
            for role_id in roles_users:
                edit_role(dbdictionary, user_id, role_id, client_id, dictionary_default=True)
        if roles_organizations:
            for role_id in roles_organizations:
                edit_role(dbdictionary, user_id, role_id, client_id, dictionary_default=True, organization=True)
        dictionary = Dictionary(id=[dbdictionary.client_id, dbdictionary.object_id])
        dictionary.dbObject = dbdictionary
        CACHE.set(objects = [dbdictionary,], DBSession=DBSession)
        return AddDictionaryRoles(dictionary=dictionary, triumph=True)

class DeleteDictionaryRoles(graphene.Mutation):
    """
        mutation myQuery {
            delete_dictionary_roles(id: [1279,4], user_id:2 , roles_users:[7]){
                        triumph

                    }
        }
    """
    class Arguments:
        id = LingvodocID(required=True)
        user_id = graphene.Int(required=True)
        roles_users = graphene.List(graphene.Int)
        roles_organizations = graphene.List(graphene.Int)

    dictionary = graphene.Field(Dictionary)
    triumph = graphene.Boolean()

    @staticmethod
    @acl_check_by_id("delete", "dictionary_role")
    def mutate(root, info, **args):
        dictionary_client_id, dictionary_object_id = args.get('id')
        user_id = args.get("user_id")
        roles_users = args.get('roles_users')
        roles_organizations = args.get('roles_organizations')
        # dbdictionary = DBSession.query(dbDictionary).filter_by(client_id=dictionary_client_id, object_id=dictionary_object_id).first()
        dbdictionary = CACHE.get(objects =
            {
                dbDictionary : (args.get('id'), )
            },
        DBSession=DBSession)

        client_id = info.context.get('client_id')

        if not dbdictionary or dbdictionary.marked_for_deletion:
            raise ResponseError(message="No such dictionary in the system")
        if roles_users:
            for role_id in roles_users:
                edit_role(dbdictionary, user_id, role_id, client_id, dictionary_default=True, action="delete")

        if roles_organizations:
            for role_id in roles_organizations:
                edit_role(dbdictionary, user_id, role_id, client_id, dictionary_default=True, organization=True,
                          action="delete")


        dictionary = Dictionary(id=[dbdictionary.client_id, dbdictionary.object_id])
        dictionary.dbObject = dbdictionary
        CACHE.set(objects = [dbdictionary,], DBSession=DBSession)
        return DeleteDictionaryRoles(dictionary=dictionary, triumph=True)



class DeleteDictionary(graphene.Mutation):
    """
    mutation {
      delete_dictionary(id: [449, 2491]) {
        triumph
        dictionary {
          id
          translation
          created_at
          translation
          marked_for_deletion
          additional_metadata {
            hash
          }
        }
      }
    }
    """
    class Arguments:
        id = LingvodocID(required=True)

    dictionary = graphene.Field(Dictionary)
    triumph = graphene.Boolean()

    @staticmethod
    @acl_check_by_id('delete', 'dictionary')
    def mutate(root, info, **args):

        ids = args.get('id')
        client_id, object_id = ids
        # dbdictionary_obj = DBSession.query(dbDictionary).filter_by(client_id=client_id, object_id=object_id).first()
        dbdictionary_obj = CACHE.get(objects =
            {
                dbDictionary : (args.get('id'), )
            },
        DBSession=DBSession)

        if not dbdictionary_obj or dbdictionary_obj.marked_for_deletion:
            raise ResponseError(message="Error: No such dictionary in the system")

        grant_id_list = []

        for grant in DBSession.query(dbGrant).all():
            dict_id = {'client_id': client_id, 'object_id': object_id}

            if grant.additional_metadata and grant.additional_metadata.get('participant') and dict_id in grant.additional_metadata['participant']:
                grant.additional_metadata['participant'].remove(dict_id)
                flag_modified(grant, 'additional_metadata')
                grant_id_list.append(grant.id)

        settings = info.context["request"].registry.settings

        if 'desktop' in settings:
            real_delete_dictionary(dbdictionary_obj, settings)

        else:
            del_object(
                dbdictionary_obj, "delete_dictionary", info.context.get('client_id'),
                grant_id_list = sorted(grant_id_list))

        dictionary = Dictionary(id=[dbdictionary_obj.client_id, dbdictionary_obj.object_id])
        dictionary.dbObject = dbdictionary_obj

        return DeleteDictionary(dictionary=dictionary, triumph=True)


class UndeleteDictionary(graphene.Mutation):

    class Arguments:
        id = LingvodocID(required=True)

    dictionary = graphene.Field(Dictionary)
    triumph = graphene.Boolean()

    @staticmethod
    @acl_check_by_id('delete', 'dictionary')
    def mutate(root, info, **args):
        ids = args.get('id')
        client_id, object_id = ids
        # dbdictionary_obj = DBSession.query(dbDictionary).filter_by(client_id=client_id, object_id=object_id).first()
        dbdictionary_obj = CACHE.get(objects =
            {
                dbDictionary : (args.get('id'), )
            },
        DBSession=DBSession)
        

        if not dbdictionary_obj:
            raise ResponseError(message="Error: No such dictionary in the system")
        if not dbdictionary_obj.marked_for_deletion:
            raise ResponseError(message="Error: Dictionary is not deleted")

        objecttoc_obj = DBSession.query(ObjectTOC).filter_by(client_id=client_id, object_id=object_id).first()

        # Restoring grant membership, if required.

        additional_metadata = (
            objecttoc_obj.additional_metadata)

        additional_info = (
            additional_metadata and additional_metadata.get('__additional_info__'))

        if additional_info:

            grant_id_list = additional_info.get('grant_id_list')

            if grant_id_list:

                grant_list = DBSession.query(dbGrant).filter(dbGrant.id.in_(grant_id_list)).all()

                dict_id = {
                    'client_id': client_id,
                    'object_id': object_id}

                for grant in grant_list:

                    if grant.additional_metadata is None:
                        grant.additional_metadata = {}

                    participant_list = grant.additional_metadata.get('participant')

                    if participant_list is None:

                        participant_list = []
                        grant.additional_metadata['participant'] = participant_list

                    if dict_id not in participant_list:

                        participant_list.append(dict_id)
                        flag_modified(grant, 'additional_metadata')

                        log.debug(participant_list)

        # Undeleting dictionary object with its translations.

        settings = info.context["request"].registry.settings

        if 'desktop' in settings:
            raise NotImplementedError
        else:
            undel_object(dbdictionary_obj, "undelete_dictionary", info.context.get('client_id'))

        dictionary = Dictionary(id=[dbdictionary_obj.client_id, dbdictionary_obj.object_id])
        dictionary.dbObject = dbdictionary_obj
        return UndeleteDictionary(dictionary=dictionary, triumph=True)
