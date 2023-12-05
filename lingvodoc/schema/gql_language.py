
# Standard library imports.

import collections
import logging
import pprint
import types
import uuid

# External imports.

import graphene

import sqlalchemy

from sqlalchemy import (
    and_,
    Boolean,
    cast,
    func,
    literal,
    or_,
    tuple_)

from sqlalchemy.orm import aliased

from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm.util import identity_key

# Lingvodoc imports.

import lingvodoc.cache.caching as caching

import lingvodoc.models as models

from lingvodoc.models import (
    Column as dbColumn,
    DBSession,
    Dictionary as dbDictionary,
    DictionaryPerspective as dbPerspective,
    Language as dbLanguage,
    SLBigInteger,
    TranslationAtom as dbTranslationAtom,
    ValencyAnnotationData as dbValencyAnnotationData,
    ValencyInstanceData as dbValencyInstanceData,
    ValencySentenceData as dbValencySentenceData,
    ValencySourceData as dbValencySourceData)

from lingvodoc.schema.gql_column import Column
from lingvodoc.schema.gql_dictionary import Dictionary

from lingvodoc.schema.gql_holders import (
    acl_check_by_id,
    AdditionalMetadata,
    client_id_check,
    CommonFieldsComposite,
    CreatedAt,
    del_object,
    fetch_object,
    get_published_translation_gist_id_cte_query,
    get_published_translation_gist_id_subquery_query,
    gql_none_value,
    LingvodocID,
    LingvodocObjectType,
    ObjectVal,
    ResponseError,
    TranslationHolder)

from lingvodoc.schema.gql_translationgist import TranslationGistInterface

from lingvodoc.utils import (
    ids_to_id_query,
    render_statement,
    statistics)

from lingvodoc.utils.creation import (
    create_dblanguage,
    create_gists_with_atoms,
    update_metadata)

from lingvodoc.utils.deletion import real_delete_language

from lingvodoc.utils.search import (
    recursive_sort,
    translation_gist_search)


# Setting up logging.
log = logging.getLogger(__name__)


class Language(LingvodocObjectType):
    """
     #created_at                 | timestamp without time zone | NOT NULL
     #object_id                  | bigint                      | NOT NULL
     #client_id                  | bigint                      | NOT NULL
     #parent_object_id           | bigint                      |
     #parent_client_id           | bigint                      |
     #translation_gist_client_id | bigint                      | NOT NULL
     #translation_gist_object_id | bigint                      | NOT NULL
     #marked_for_deletion        | boolean                     | NOT NULL
     #additional_metadata        | jsonb                       |
     + translation
    """
    dbType = dbLanguage

    dictionaries = graphene.List(Dictionary,
        deleted=graphene.Boolean(),
        published=graphene.Boolean(),
        category=graphene.Int())

    languages = graphene.List('lingvodoc.schema.gql_language.Language',
        deleted=graphene.Boolean())

    locale_exist = graphene.Boolean()
    dataType = graphene.String()

    tree = graphene.List('lingvodoc.schema.gql_language.Language')

    dictionary_count = (

        graphene.Int(
            recursive = graphene.Boolean(),
            category = graphene.Int(),
            published = graphene.Boolean()))

    in_toc = graphene.Boolean()

    statistic = (

        graphene.Field(
            ObjectVal,
            starting_time = graphene.Int(),
            ending_time = graphene.Int(),
            disambiguation_flag = graphene.Boolean(),
            dictionaries = graphene.Boolean(),
            corpora = graphene.Boolean()))

    class Meta:
        interfaces = (CommonFieldsComposite, TranslationHolder, TranslationGistInterface)

    @fetch_object()
    def resolve_locale_exists(self):
        return self.dbObject.locale

    @fetch_object('dictionaries')
    def resolve_dictionaries(self, info, deleted = None, published = None, category = None):

        # Dictionaries of the language, in standard order, from newest to oldest.

        dictionary_query = (

            DBSession
                
                .query(dbDictionary)
                
                .filter_by(
                    parent_client_id = self.id[0],
                    parent_object_id = self.id[1])
                    
                .order_by(
                    dbDictionary.created_at.desc(),
                    dbDictionary.client_id.desc(),
                    dbDictionary.object_id.desc()))

        if deleted is not None:

            dictionary_query = (

                dictionary_query.filter(
                    dbDictionary.marked_for_deletion == deleted))

        if category is not None:

            dictionary_query = (

                dictionary_query.filter(
                    dbDictionary.category == category))

        # Do we need to filter dictionaries by their published state?

        if published is not None:

            db_published_gist = translation_gist_search('Published')

            published_client_id = db_published_gist.client_id
            published_object_id = db_published_gist.object_id

            db_limited_gist = translation_gist_search('Limited access')

            limited_client_id = db_limited_gist.client_id
            limited_object_id = db_limited_gist.object_id

            # If we need only published or limited dictionaries, we also filter dictionaries through their
            # perspectives.
            # 
            # See dictionaries_list(), published_dictionaries_list() in lingvodoc/views/v2/dictionary.py.
            #
            # Additionally, we do it differently based on if the dictionary is deleted or not.
            #
            # If the dictionary is not deleted, we check its not deleted perspectives.
            #
            # If the dictionary is deleted, we check both its not deleted and deleted perspectives.

            perspective_query = (DBSession

                .query(literal(1))

                .filter(
                    dbPerspective.parent_client_id == dbDictionary.client_id,
                    dbPerspective.parent_object_id == dbDictionary.object_id,

                    or_(
                        and_(dbPerspective.state_translation_gist_client_id == published_client_id,
                            dbPerspective.state_translation_gist_object_id == published_object_id),
                        and_(dbPerspective.state_translation_gist_client_id == limited_client_id,
                            dbPerspective.state_translation_gist_object_id == limited_object_id))))

            if deleted is None:

                perspective_query = perspective_query.filter(

                    or_(
                        dbDictionary.marked_for_deletion,
                        dbPerspective.marked_for_deletion == False))

            elif not deleted:

                perspective_query = perspective_query.filter(
                    dbPerspective.marked_for_deletion == False)

            # Applying dictionary filtering.

            if published:

                dictionary_query = (dictionary_query

                    .filter(
                        
                        or_(
                            and_(dbDictionary.state_translation_gist_client_id == published_client_id,
                                dbDictionary.state_translation_gist_object_id == published_object_id),
                            and_(dbDictionary.state_translation_gist_client_id == limited_client_id,
                                dbDictionary.state_translation_gist_object_id == limited_object_id)),
                            
                        perspective_query.exists()))

            else:

                dictionary_query = (dictionary_query

                    .filter(

                        or_(
                        
                            and_(
                                or_(dbDictionary.state_translation_gist_client_id != published_client_id,
                                    dbDictionary.state_translation_gist_object_id != published_object_id),
                                or_(dbDictionary.state_translation_gist_client_id != limited_client_id,
                                    dbDictionary.state_translation_gist_object_id != limited_object_id)),
                            
                            ~perspective_query.exists())))

        # Returning found dictionaries.

        result = list()

        for dictionary in dictionary_query:

            gql_dictionary = Dictionary(id =
                [dictionary.client_id, dictionary.object_id])

            gql_dictionary.dbObject = dictionary
            result.append(gql_dictionary)

        return result

    @fetch_object('languages')
    def resolve_languages(self, info, deleted = None):

        query = (

            DBSession

                .query(dbLanguage)

                .filter(
                    dbLanguage.parent_client_id == self.id[0],
                    dbLanguage.parent_object_id == self.id[1]))

        if deleted is not None:
            query = query.filter(dbLanguage.marked_for_deletion == deleted)

        result = list()

        for language in query:
            gql_language = Language(id=[language.client_id, language.object_id])
            gql_language.dbObject = language
            result.append(gql_language)

        return result

    @fetch_object('tree')
    def resolve_tree(self, info):

        #
        # So this is an attempt to optimize tree retrieval, but apparently it does not always work faster.
        #
        # For a single language query, like 
        # language(id: [33, 90]) { id translations tree { id translations } },
        # it is faster.
        #
        # For many-language query like
        # languages(only_in_toc: true) { id translations tree { id translations } }
        # it is apparently slower.
        #
        # Looks like with many-language queries retrieving parents one by one takes full advantage of the
        # SQLAlchemy identity map instance cache, while recursive retrieval, even with optimization of first
        # trying to get from the cache, results in heavier DB usage and so is slower.
        #
        # So, if we would like to make getting trees faster for multi-language queries, we'll have to
        # optimize retrieval of tree data when we efficiently get the queried languages.
        #

        if False:

            result = [self]
            parent_client_id, parent_object_id = self.dbObject.parent_id

            # First trying to get instances from the SQLAlchemy identity map instance cache.

            while parent_client_id is not None:

                language_db = (
                    DBSession.identity_map.get(
                        identity_key(dbLanguage, (parent_object_id, parent_client_id))))

                if not language_db:
                    break

                language = Language(id = (parent_client_id, parent_object_id))
                language.dbObject = language_db

                result.append(language)
                parent_client_id, parent_object_id = language_db.parent_id

            # Then, if we need, we retrieve any parent languages left all at once via recursive CTE query.

            if parent_client_id is not None:

                base_cte = (

                    DBSession

                        .query(
                            dbLanguage)

                        .filter(
                            dbLanguage.client_id == parent_client_id,
                            dbLanguage.object_id == parent_object_id)

                        .cte(recursive = True))

                recursive_query = (

                    DBSession

                        .query(
                            dbLanguage)

                        .filter(
                            dbLanguage.client_id == base_cte.c.parent_client_id,
                            dbLanguage.object_id == base_cte.c.parent_object_id))

                language_list = (

                    DBSession

                        .query(
                            aliased(
                                dbLanguage,
                                base_cte.union(recursive_query),
                                adapt_on_names = True))

                        .all())

                language_dict = {
                    language.id: language
                    for language in language_list}

                parent_id = (
                    parent_client_id, parent_object_id)

                while parent_id != (None, None):

                    language_db = language_dict[parent_id]

                    language = Language(id = parent_id)
                    language.dbObject = language_db

                    result.append(language)
                    parent_id = language_db.parent_id

            return result

        # Simple per-object retrieval.

        result = [self]
        iteritem = self.dbObject.parent

        while iteritem:

            language = Language(id = iteritem.id)
            language.dbObject = iteritem

            result.append(language)

            iteritem = iteritem.parent

        return result

    @fetch_object('dictionary_count')
    def resolve_dictionary_count(
        self,
        info,
        recursive = False,
        category = None,
        published = None):

        if published is not None:
            raise NotImplementedError

        category_str = (
            '' if category is None else
            f'\nand category = {category}')

        if recursive:

            sql_str = f'''

                with recursive

                ids_cte (client_id, object_id) as (

                  values ({self.id[0]} :: bigint, {self.id[1]} :: bigint)

                  union

                  select
                    L.client_id,
                    L.object_id

                  from
                    language L,
                    ids_cte I

                  where
                    L.parent_client_id = I.client_id and
                    L.parent_object_id = I.object_id and
                    L.marked_for_deletion = false
                )

                select count(*)

                from dictionary

                where
                  (parent_client_id, parent_object_id) in (select * from ids_cte) and
                  marked_for_deletion = false{category_str};

                '''

        else:

            sql_str = f'''

                select
                  count(*)

                from
                  dictionary

                where
                  parent_client_id = {self.id[0]} and
                  parent_object_id = {self.id[1]} and
                  marked_for_deletion = false{category_str};

                '''

        return (
            DBSession
                .execute(sql_str)
                .fetchall()
                    [0][0])

    @fetch_object('in_toc')
    def resolve_in_toc(self, info):

        metadata = (
            self.dbObject.additional_metadata)

        return (
            metadata is not None and
            metadata.get('toc_mark', False))

    @fetch_object()
    def resolve_statistic(
        self,
        info,
        starting_time = None,
        ending_time = None,
        disambiguation_flag = False,
        dictionaries = False,
        corpora = False):

        return (

            statistics.new_format(
                statistics.stat_language(
                    self.id,
                    starting_time,
                    ending_time,
                    disambiguation_flag,
                    dictionaries,
                    corpora,
                    locale_id = info.context.locale_id)))


class CreateLanguage(graphene.Mutation):
    """
    example:
       mutation  {
        create_language(id: [949,18], translation_gist_id: [662, 3], parent_id: [1, 47], locale_exist: true) {
            language {
                id
                translation_gist_id
            }
        }
    }

    (this example works)
    {
      "create_language": {
        "language": {
          "id": [
            949,
            18
          ],
          "translation_gist_id": [
            662,
            3
          ]
        }
      }
    }
    """

    class Arguments:
        client_id = graphene.Int()
        translation_gist_id = LingvodocID()
        parent_id = LingvodocID()
        translation_atoms = graphene.List(ObjectVal)
        additional_metadata = ObjectVal()

    language = graphene.Field(Language)
    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    def mutate(
        root,
        info,
        client_id = None,
        parent_id = None,
        translation_gist_id = None,
        translation_atoms = None,
        additional_metadata = None):

        context = info.context

        # When creating object, we check, if a client id was supplied, if it's compatible.

        client_id = (

            context.effective_client_id(
                client_id))

        translation_gist_id = (

            create_gists_with_atoms(
                translation_atoms,
                translation_gist_id,
                [client_id, None],
                gist_type = 'Language'))

        db_language = (

            create_dblanguage(
                client_id = client_id,
                parent_id = parent_id,
                translation_gist_id = translation_gist_id,
                additional_metadata = additional_metadata))

        return (

            CreateLanguage(
                language = Language(db_language),
                triumph = True))


def move_language(language, parent_id, previous_sibling):
    previous = None
    if not parent_id:
        parent_id = [None, None]
    if previous_sibling:
        previous = DBSession.query(dbLanguage).filter(dbLanguage.client_id == previous_sibling[0],
                                           dbLanguage.object_id == previous_sibling[1],
                                                        dbLanguage.marked_for_deletion == False).first()
        if not previous:
            raise ResponseError(message='no such previous sibling')
        if [previous.parent_client_id, previous.parent_object_id] != parent_id:
            raise ResponseError(message='no such pair of this parent/previous_sibling')
    lang_ids = [language.client_id, language.object_id]
    ids = lang_ids
    older_siblings = DBSession.query(dbLanguage).filter(dbLanguage.parent_client_id == language.parent_client_id,
                                                        dbLanguage.parent_object_id == language.parent_object_id,
                                                        dbLanguage.marked_for_deletion == False,
                                                        dbLanguage.additional_metadata['younger_siblings'].contains(
                                                            [ids])).all()
    for lang in older_siblings:
        lang.additional_metadata['younger_siblings'].remove(lang_ids)
        flag_modified(lang, 'additional_metadata')

    parent = DBSession.query(dbLanguage).filter(dbLanguage.client_id==parent_id[0], dbLanguage.object_id==parent_id[1]).first()
    if parent:
        while parent is not None:
            tmp_ids = [parent.client_id, parent.object_id]
            if tmp_ids == lang_ids:
                raise ResponseError(message='cannot cycle parent-child in tree')
            parent = parent.parent
    language.parent_client_id = parent_id[0]
    language.parent_object_id = parent_id[1]
    older_siblings = DBSession.query(dbLanguage).filter(dbLanguage.parent_client_id == parent_id[0],
                                                        dbLanguage.parent_object_id == parent_id[1],
                                                        dbLanguage.marked_for_deletion == False,
                                                        or_(dbLanguage.client_id != language.client_id, dbLanguage.object_id != language.object_id))
    if previous:
        ids = previous_sibling
        older_siblings = older_siblings.filter(dbLanguage.additional_metadata['younger_siblings'].contains(
                                               [ids]))
    older_siblings = older_siblings.all()
    if previous:
        new_meta = list(previous.additional_metadata['younger_siblings'])
    else:
        new_meta = []
    for lang in older_siblings:
        siblings = lang.additional_metadata.get('younger_siblings')
        if not siblings:
            lang.additional_metadata['younger_siblings'] = list()
            siblings = lang.additional_metadata['younger_siblings']
        if previous_sibling:
            index = siblings.index(previous_sibling)
        else:
            index = -1
        lang.additional_metadata['younger_siblings'].insert(index + 1, [language.client_id, language.object_id])
        flag_modified(lang, 'additional_metadata')
    language.additional_metadata['younger_siblings'] = new_meta
    if previous_sibling:
        language.additional_metadata['younger_siblings'].append(previous_sibling)
    flag_modified(language, 'additional_metadata')


class MoveLanguage(graphene.Mutation):
    """
    example:
       mutation  {
        update_language(id: [949,18], translation_gist_id: [660, 4]) {
            language {
                id
                translation_gist_id
            }
        }
    }

    (this example works)
    returns:
   {
      "update_language": {
        "language": {
          "id": [
            949,
            18
          ],
          "translation_gist_id": [
            660,
            4
          ]
        }
      }
    }
    """
    class Arguments:
        id = LingvodocID(required=True)
        parent_id = LingvodocID()
        previous_sibling = LingvodocID()

    language = graphene.Field(Language)
    triumph = graphene.Boolean()


    @staticmethod
    @acl_check_by_id('edit', 'language')
    def mutate(root, info, **args):
        id = args.get('id')
        client_id = id[0]
        object_id = id[1]
        dblanguage = DBSession.query(dbLanguage).filter_by(client_id=client_id, object_id=object_id).first()

        if not dblanguage or dblanguage.marked_for_deletion:
            raise ResponseError(message="Error: No such language in the system")
        parent_id = args.get('parent_id')
        previous_sibling = args.get('previous_sibling')
        move_language(dblanguage, parent_id, previous_sibling)
        language = Language(id=[dblanguage.client_id, dblanguage.object_id])
        language.dbObject = dblanguage
        return UpdateLanguage(language=language, triumph=True)


class UpdateLanguage(graphene.Mutation):
    """
    example:
       mutation  {
        update_language(id: [949,18], translation_gist_id: [660, 4]) {
            language {
                id
                translation_gist_id
            }
        }
    }

    (this example works)
    returns:
   {
      "update_language": {
        "language": {
          "id": [
            949,
            18
          ],
          "translation_gist_id": [
            660,
            4
          ]
        }
      }
    }
    """
    class Arguments:
        id = LingvodocID(required=True)
        translation_gist_id = LingvodocID()
        additional_metadata = ObjectVal()
        add_user_id = graphene.Int()
        del_user_id = graphene.Int()

    language = graphene.Field(Language)
    triumph = graphene.Boolean()


    @staticmethod
    @acl_check_by_id('edit', 'language')
    def mutate(root, info, **args):
        id = args.get('id')
        client_id = id[0]
        object_id = id[1]
        dblanguage = DBSession.query(dbLanguage).filter_by(client_id=client_id, object_id=object_id).first()

        if not dblanguage or dblanguage.marked_for_deletion:
            raise ResponseError(message="Error: No such language in the system")

        translation_gist_id = args.get('translation_gist_id')
        if translation_gist_id:
            dblanguage.translation_gist_client_id = translation_gist_id[0]
            dblanguage.translation_gist_object_id = translation_gist_id[1]

        additional_metadata = args.get('additional_metadata')
        if additional_metadata:
            update_metadata(dblanguage, additional_metadata)

        new_user = args.get('add_user_id')
        if new_user:
            user_list = (
                dblanguage.additional_metadata
                .get('attached_users') or []
            )
            if new_user not in user_list:
                user_list.append(new_user)
            update_metadata(dblanguage, {'attached_users': user_list})

        del_user = args.get('del_user_id')
        if del_user:
            user_list = (
                dblanguage.additional_metadata
                .get('attached_users') or []
            )
            if del_user in user_list:
                user_list.remove(del_user)
            update_metadata(dblanguage, {'attached_users': user_list})

        language = Language(id=[dblanguage.client_id, dblanguage.object_id])
        language.dbObject = dblanguage
        return UpdateLanguage(language=language, triumph=True)


class UpdateLanguageAtom(graphene.Mutation):
    """
    example:
    mutation up{
        update_language_atom(id: [2138, 6], locale_id: 2, content: "test6"){
            triumph
        }

    }

        now returns:

    {
        "data": {
            "update_language_atom": {
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
    language = graphene.Field(Language)

    @staticmethod
    @acl_check_by_id('edit', 'language')
    def mutate(root, info, **args):
        content = args.get('content')
        client_id, object_id = args.get('id')
        dblanguage = DBSession.query(dbLanguage).filter_by(client_id=client_id, object_id=object_id).first()
        if not dblanguage:
            raise ResponseError(message="No such perspective in the system")
        locale_id = args.get("locale_id")


        dbtranslationatom = DBSession.query(dbTranslationAtom).filter_by(parent_client_id=dblanguage.translation_gist_client_id,
                                                            parent_object_id=dblanguage.translation_gist_object_id,
                                                            locale_id=locale_id).first()
        if dbtranslationatom:
            if dbtranslationatom.locale_id == locale_id:
                key = "translation:%s:%s:%s" % (
                    str(dbtranslationatom.parent_client_id),
                    str(dbtranslationatom.parent_object_id),
                    str(dbtranslationatom.locale_id))
                caching.CACHE.rem(key)
                key = "translations:%s:%s" % (
                    str(dbtranslationatom.parent_client_id),
                    str(dbtranslationatom.parent_object_id))
                caching.CACHE.rem(key)
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
                                                parent_client_id=dblanguage.translation_gist_client_id,
                                                parent_object_id=dblanguage.translation_gist_object_id,
                                                locale_id=locale_id,
                                                content=content)
            DBSession.add(dbtranslationatom)
            DBSession.flush()

        language = Language(id=[dblanguage.client_id, dblanguage.object_id])
        language.dbObject = dbLanguage
        return UpdateLanguageAtom(language=language, triumph=True)


class DeleteLanguage(graphene.Mutation):
    """
    example:
     mutation  {
        delete_language(id: [949,13]) {
            language {
                id
            }
        }
    }

    (this example works)
    {
      "delete_language": {
        "language": {
          "id": [
            949,
            13
          ]
        }
      }
    }
    """

    class Arguments:
        id = LingvodocID(required=True)

    language = graphene.Field(Language)
    triumph = graphene.Boolean()

    @staticmethod
    @acl_check_by_id('delete', 'language')
    def mutate(root, info, **args):
        id = args.get('id')
        client_id, object_id = id
        dblanguageobj = DBSession.query(dbLanguage).filter_by(client_id=client_id, object_id=object_id).first()

        if not dblanguageobj or dblanguageobj.marked_for_deletion:
            raise ResponseError(message="No such language in the system")


        del_lang_dictionaries = DBSession.query(dbDictionary).filter_by(parent=dblanguageobj, marked_for_deletion=False).first()
        if del_lang_dictionaries:
            raise ResponseError(message='This language contains dictionaries')

        child_langs = DBSession.query(dbLanguage).filter_by(parent=dblanguageobj, marked_for_deletion=False).first()
        if child_langs:
            raise ResponseError(message='This language contains child languages')

        settings = info.context["request"].registry.settings
        if 'desktop' in settings:
            real_delete_language(dblanguageobj, settings)
        else:
            lang_ids = [dblanguageobj.client_id, dblanguageobj.object_id]
            ids = lang_ids
            older_siblings = DBSession.query(dbLanguage).filter(
                dbLanguage.parent_client_id == dblanguageobj.parent_client_id,
                dbLanguage.parent_object_id == dblanguageobj.parent_object_id,
                dbLanguage.marked_for_deletion == False,
                dbLanguage.additional_metadata['younger_siblings'].contains(
                    [ids])).all()
            for lang in older_siblings:
                lang.additional_metadata['younger_siblings'].remove(lang_ids)
                flag_modified(lang, 'additional_metadata')
            del_object(dblanguageobj, "delete_language", info.context.get('client_id'))
        language = Language(id=id)
        language.dbObject = dblanguageobj
        return DeleteLanguage(language=language, triumph=True)


class LanguageTree(graphene.ObjectType):
    tree = ObjectVal()
    languages = graphene.List(Language)


class Resolver_Selection(object):
    """
    Stores a set of selected fields together with columns required to resolve them.
    """

    def __init__(self, field_column_dict):

        self.field_column_dict = field_column_dict

        self.field_set = set()
        self.column_set = set()

        self.column_list = []

        self.object_flag = False

    def __call__(self, *args):

        self.add(*args)

    def __contains__(self, field_str):

        return (
            field_str in self.field_column_dict)

    def add(self, *args):

        for value in args:

            if isinstance(value, str):

                if value in self.field_set:
                    return

                self.field_set.add(value)

                for column in (
                    self.field_column_dict.get(value, ())):

                    if column not in self.column_set:

                        self.column_set.add(column)
                        self.column_list.append(column)

            elif value not in self.column_set:

                self.column_set.add(value)
                self.column_list.append(value)

    def remove(self, *args):

        for arg in args:

            self.field_set.remove(arg)


def language_resolver_args(
    id_list = None,
    only_in_toc = False,
    only_with_dictionaries_recursive = False,
    dictionary_category = None,
    dictionary_published = None,
    language_id = None,
    by_grants = False,
    grant_id = None,
    by_organizations = False,
    organization_id = None,
    in_tree_order = False):

    return (

        types.SimpleNamespace(
            id_list = id_list,
            only_in_toc = only_in_toc,
            only_with_dictionaries_recursive = only_with_dictionaries_recursive,
            dictionary_category = dictionary_category,
            dictionary_published = dictionary_published,
            language_id = language_id,
            by_grants = by_grants,
            grant_id = grant_id,
            by_organizations = by_organizations,
            organization_id = organization_id,
            in_tree_order = in_tree_order))


def language_toc_sql(self):

    toc_table_name = (

        'toc_language_ids_' +
         str(uuid.uuid4()).replace('-', '_'))

    count_table_name = (

        'dictionary_counts_' +
         str(uuid.uuid4()).replace('-', '_'))

    result_table_name = (

        'recursive_counts_' +
         str(uuid.uuid4()).replace('-', '_'))

    sql_str = f'''

        create temporary table
          {toc_table_name}
          on commit drop as

          select
            client_id,
            object_id,
            parent_client_id,
            parent_object_id

          from
            language

          where
            marked_for_deletion = false and
            (additional_metadata -> 'toc_mark') :: boolean;

        create temporary table
          {count_table_name}
          on commit drop as

          with recursive

          underlying_language_ids as (

            select *
            from {toc_table_name}

            union

            select
              L.client_id,
              L.object_id,
              L.parent_client_id,
              L.parent_object_id

            from
              language L,
              underlying_language_ids U

            where
              L.marked_for_deletion = false and
              L.parent_client_id = U.client_id and
              L.parent_object_id = U.object_id
          )

          select
            L.*, count(D.*)

          from
            underlying_language_ids L

          left outer join
            dictionary D

          on
            D.parent_client_id = L.client_id and
            D.parent_object_id = L.object_id and
            D.marked_for_deletion = false and
            D.category = 0

          group by
            L.client_id,
            L.object_id,
            L.parent_client_id,
            L.parent_object_id;

        create temporary table

          {result_table_name} (
            client_id BIGINT,
            object_id BIGINT,
            count BIGINT
          )

        on commit drop;

        do $$

        begin

        while exists (
          select 1 from {count_table_name}) loop

          with

          iteration_counts as (

            select C1.*

              from
                {count_table_name} C1

              left outer join
                {count_table_name} C2

              on
                C1.client_id = C2.parent_client_id and
                C1.object_id = C2.parent_object_id

              where
                C2 is null
          ),

          delete_cte as (

            delete

            from
              {count_table_name} D

            using
              iteration_counts I

            where
              D.client_id = I.client_id and
              D.object_id = I.object_id
          ),

          update_cte as (

            update
              {count_table_name} D

            set
              count = D.count + S.sum

            from (

              select
                parent_client_id,
                parent_object_id,
                sum(count)

              from
                iteration_counts

              group by
                parent_client_id,
                parent_object_id

            ) S

            where
              D.client_id = S.parent_client_id and
              D.object_id = S.parent_object_id
          )

          insert into
            {result_table_name}

          select
            client_id,
            object_id,
            count

          from
            iteration_counts;

        end loop;

        end

        $$;

        select
          R.*

        from
          {result_table_name} R,
          {toc_table_name} T

        where
          R.client_id = T.client_id and
          R.object_id = T.object_id;

    '''

    return (

        DBSession
            .execute(sql_str)
            .fetchall())


def language_toc_python(self):

    # Getting base counts.

    toc_table_name = (

        'toc_language_ids_' +
         str(uuid.uuid4()).replace('-', '_'))

    sql_str = f'''

        create temporary table
          {toc_table_name}
          on commit drop as

          select
            client_id,
            object_id,
            parent_client_id,
            parent_object_id

          from
            language

          where
            marked_for_deletion = false and
            (additional_metadata -> 'toc_mark') :: boolean;

        with recursive

        underlying_language_ids as (

          select *
          from {toc_table_name}

          union

          select
            L.client_id,
            L.object_id,
            L.parent_client_id,
            L.parent_object_id

          from
            language L,
            underlying_language_ids U

          where
            L.marked_for_deletion = false and
            L.parent_client_id = U.client_id and
            L.parent_object_id = U.object_id
        )

        select
          U.*,
          count(D.*)
            filter (where D.client_id is not null)

        from
          underlying_language_ids U

        left outer join
          dictionary D

        on
          D.parent_client_id = U.client_id and
          D.parent_object_id = U.object_id and
          D.marked_for_deletion = false and
          D.category = 0

        group by
          U.client_id,
          U.object_id,
          U.parent_client_id,
          U.parent_object_id;

    '''

    count_list = (

        DBSession
            .execute(sql_str)
            .fetchall())

    from_to_dict = collections.defaultdict(list)

    count_dict = {}

    for client_id, object_id, parent_client_id, parent_object_id, count in count_list:

        id = (client_id, object_id)
        parent_id = (parent_client_id, parent_object_id)

        from_to_dict[parent_id].append(id)

        count_dict[id] = count

    # Getting language TOC ids, computing language TOC total counts.

    toc_id_list = [

        tuple(id) for id in

            DBSession
                .execute(f'select client_id, object_id from {toc_table_name}')
                .fetchall()]

    total_count_dict = {}

    def f(id):

        total_count = total_count_dict.get(id)

        if total_count is not None:
            return total_count

        total_count = (

            count_dict[id] +

            sum(f(to_id)
                for to_id in from_to_dict[id]))

        total_count_dict[id] = total_count

        return total_count

    return [
        (id[0], id[1], f(id))
        for id in toc_id_list]


def toc_translations_cache(self, toc_list):

    gist_id_list = (

        DBSession

            .query(
                dbLanguage.client_id,
                dbLanguage.object_id,
                dbLanguage.translation_gist_client_id,
                dbLanguage.translation_gist_object_id)

            .filter(

                tuple_(
                    dbLanguage.client_id,
                    dbLanguage.object_id)

                    .in_(
                        ids_to_id_query(
                            (client_id, object_id)
                            for client_id, object_id, count in toc_list)))

            .all())

    return {

        (client_id, object_id):
            models.get_translations(gist_client_id, gist_object_id)

        for client_id, object_id, gist_client_id, gist_object_id in gist_id_list}


def toc_translations_db(self, toc_list):

    translation_list = (

        DBSession

            .query(
                dbLanguage.client_id,
                dbLanguage.object_id,
                dbTranslationAtom.locale_id,
                dbTranslationAtom.content)

            .filter(

                tuple_(
                    dbLanguage.client_id,
                    dbLanguage.object_id)

                    .in_(
                        ids_to_id_query(
                            (client_id, object_id)
                            for client_id, object_id, count in toc_list)),

                dbTranslationAtom.parent_client_id == dbLanguage.translation_gist_client_id,
                dbTranslationAtom.parent_object_id == dbLanguage.translation_gist_object_id,
                dbTranslationAtom.marked_for_deletion == False)

            .all())

    content_dict = collections.defaultdict(list)

    for client_id, object_id, locale_id, content in translation_list:
        content_dict[(client_id, object_id)].append((locale_id, content))

    result_dict = {}

    for client_id, object_id, count in toc_list:

        id = (client_id, object_id)
        content_list = content_dict.get(id)

        result_dict[id] = (
            None if content_list is None else
                {str(key): value for key, value in content_list})

    return result_dict


class Language_Resolver(object):
    """
    Resolves list of languages, possibly with underlying dictionaries and their perspectives, for
    'languages' and 'language_tree' queries.
    """

    def __init__(
        self,
        info,
        field_asts,
        args,
        debug_flag = False):

        self.info = info

        self.field_asts = field_asts
        self.variable_values = info.variable_values

        self.args = args

        self.debug_flag = debug_flag

        self.dictionary_selection = None
        self.perspective_selection = None
        self.column_selection = None

        self.published_query = None
        self.published_condition_count = 0

    def argument_value(self, argument):

        try:

            return argument.value.value

        except AttributeError:

            return (

                self.variable_values.get(
                    argument.value.name.value, None))

    def parse_languages(self, field_asts):

        ls = (
            self.language_selection)

        already_set = set()

        if self.debug_flag:

            log.debug(
                f'\n field_asts (languages):\n {field_asts}')

        for field in field_asts:

            name_str = field.name.value

            if name_str in ls:

                ls(name_str)

            elif name_str == 'dictionary_count':

                if 'dictionary_count' in already_set:

                    ls.dictionary_count = None
                    continue

                already_set.add('dictionary_count')

                dc = (

                    types.SimpleNamespace(
                        recursive = None,
                        category = None,
                        published = None))

                ls.dictionary_count = dc

                for argument in field.arguments:

                    name_str = argument.name.value

                    if name_str == 'recursive':

                        dc.recursive = (
                            self.argument_value(argument))

                    elif name_str == 'category':

                        dc.category = (
                            self.argument_value(argument))

                    elif name_str == 'published':

                        dc.published = (
                            self.argument_value(argument))

                    else:

                        ls.dictionary_count = None
                        break

            elif name_str == 'dictionaries':

                if 'dictionaries' in already_set:

                    ls.dictionaries = None
                    continue

                already_set.add('dictionaries')

                d = (

                    types.SimpleNamespace(
                        deleted = None,
                        category = None,
                        published = None))

                ls.dictionaries = d

                for argument in field.arguments:

                    name_str = argument.name.value

                    if name_str == 'category':

                        d.category = (
                            self.argument_value(argument))

                    elif name_str == 'deleted':

                        d.deleted = (
                            self.argument_value(argument))

                    elif name_str == 'published':

                        d.published = (
                            self.argument_value(argument))

                    else:

                        ls.dictionaries = None
                        break

                if ls.dictionaries:

                    ds = (

                        Resolver_Selection({

                            'additional_metadata': (
                                dbDictionary.additional_metadata,),

                            'category': (
                                dbDictionary.category,),

                            'created_at': (
                                dbDictionary.created_at,),

                            'domain': (
                                dbDictionary.domain,),

                            'id': (
                                dbDictionary.client_id,
                                dbDictionary.object_id),

                            'marked_for_deletion': (
                                dbDictionary.marked_for_deletion,),

                            'parent_id': (
                                dbDictionary.parent_client_id,
                                dbDictionary.parent_object_id),

                            'state_translation_gist_id': (
                                dbDictionary.state_translation_gist_client_id,
                                dbDictionary.state_translation_gist_object_id),

                            'status_translations': (
                                dbDictionary.state_translation_gist_client_id,
                                dbDictionary.state_translation_gist_object_id),

                            'translation_gist_id': (
                                dbDictionary.translation_gist_client_id,
                                dbDictionary.translation_gist_object_id),

                            'translations': (
                                dbDictionary.translation_gist_client_id,
                                dbDictionary.translation_gist_object_id)}))

                    self.dictionary_selection = ds

                    self.parse_dictionaries(
                        field.selection_set.selections)

                    # Would need creation time to order dictionaries in a standard way, from newest to
                    # oldest.

                    ds('id')
                    ds('created_at')

                    ls('id')
                    ds('parent_id')

            elif name_str == 'translation':

                if 'translation' in already_set:

                    ls.translation = None
                    continue

                already_set.add('translation')

                t = (

                    types.SimpleNamespace(
                        locale_id = None))

                ls.translation = t

                for argument in field.arguments:

                    name_str = argument.name.value

                    if name_str == 'locale_id':

                        t.locale_id = (
                            self.argument_value(argument))

                    else:

                        ls.translation = None
                        break

                if ls.translation:

                    ls('translation_gist_id')
                    ls('translation')

            elif name_str != '__typename':

                ls.object_flag = True

        if (ls.dictionaries and
            ls.dictionaries.published is not None):

            self.published_condition_count += 1

    def parse_dictionaries(self, field_asts):

        ds = (
            self.dictionary_selection)

        ds.perspectives = None
        ds.status = None

        already_set = set()

        for field in field_asts:

            name_str = field.name.value

            if name_str in ds:

                ds(name_str)

            elif name_str == 'perspectives':

                if 'perspectives' in already_set:

                    ds.perspectives = None
                    continue

                already_set.add('perspectives')

                p = (

                    types.SimpleNamespace(
                        with_verb_data = None))

                ds.perspectives = p

                for argument in field.arguments:

                    name_str = argument.name.value

                    if name_str == 'with_verb_data':

                        p.with_verb_data = (
                            self.argument_value(argument))

                    else:

                        ds.perspectives = None
                        break

                if ds.perspectives:

                    ps = (

                        Resolver_Selection({

                            'additional_metadata': (
                                dbPerspective.additional_metadata,),

                            'created_at': (
                                dbPerspective.created_at,),

                            'id': (
                                dbPerspective.client_id,
                                dbPerspective.object_id),

                            'import_hash': (
                                dbPerspective.import_hash,),

                            'import_source': (
                                dbPerspective.import_source,),

                            'marked_for_deletion': (
                                dbPerspective.marked_for_deletion,),

                            'parent_id': (
                                dbPerspective.parent_client_id,
                                dbPerspective.parent_object_id),

                            'state_translation_gist_id': (
                                dbPerspective.state_translation_gist_client_id,
                                dbPerspective.state_translation_gist_object_id),

                            'status': (
                                dbPerspective.state_translation_gist_client_id,
                                dbPerspective.state_translation_gist_object_id),

                            'status_translations': (
                                dbPerspective.state_translation_gist_client_id,
                                dbPerspective.state_translation_gist_object_id),

                            'translation_gist_id': (
                                dbPerspective.translation_gist_client_id,
                                dbPerspective.translation_gist_object_id),

                            'translations': (
                                dbPerspective.translation_gist_client_id,
                                dbPerspective.translation_gist_object_id)}))

                    self.perspective_selection = ps

                    self.parse_perspectives(
                        field.selection_set.selections)

                    # Would need creation time to order perspectives from older to newer.

                    ps('id')
                    ps('created_at')

                    ds('id')
                    ps('parent_id')

            elif name_str == 'status':

                if 'status' in already_set:

                    ds.status = None
                    continue

                already_set.add('status')

                s = (

                    types.SimpleNamespace(
                        locale_id = None))

                ds.status = s

                for argument in field.arguments:

                    name_str = argument.name.value

                    if name_str == 'locale_id':

                        s.locale_id = (
                            self.argument_value(argument))

                    else:

                        ds.status = None
                        break

                if ds.status:

                    ds('state_translation_gist_id')
                    ds('status')

            elif name_str != '__typename':

                ds.object_flag = True

        ds.translations_flag = (
            'translations' in ds.field_set)

        ds.status_flag = (
            ds.status is not None)

        ds.status_translations_flag = (
            'status_translations' in ds.field_set)

    def parse_perspectives(self, field_asts):

        ps = (
            self.perspective_selection)

        ps.columns = None
        ps.status = None

        already_set = set()

        for field in field_asts:

            name_str = field.name.value

            if name_str in ps:

                ps(name_str)

            elif name_str == 'columns':

                if 'columns' in already_set:

                    ps.columns = None
                    continue

                already_set.add('columns')

                ps.columns = (
                    types.SimpleNamespace())

                for argument in field.arguments:

                    ps.columns = None
                    break

                if ps.columns:

                    cs = (

                        Resolver_Selection({

                            'created_at': (
                                dbColumn.created_at,),

                            'field_id': (
                                dbColumn.field_client_id,
                                dbColumn.field_object_id),

                            'id': (
                                dbColumn.client_id,
                                dbColumn.object_id),

                            'link_id': (
                                dbColumn.link_client_id,
                                dbColumn.link_object_id),

                            'marked_for_deletion': (
                                dbColumn.marked_for_deletion,),

                            'parent_id': (
                                dbColumn.parent_client_id,
                                dbColumn.parent_object_id),

                            'position': (
                                dbColumn.position,),

                            'self_id': (
                                dbColumn.self_client_id,
                                dbColumn.self_object_id)}))

                    self.column_selection = cs

                    self.parse_columns(
                        field.selection_set.selections)

                    cs('id')

                    ps('id')
                    cs('parent_id')

            elif name_str == 'status':

                if 'status' in already_set:

                    ps.status = None
                    continue

                already_set.add('status')

                s = (

                    types.SimpleNamespace(
                        locale_id = None))

                ps.status = s

                for argument in field.arguments:

                    name_str = argument.name.value

                    if name_str == 'locale_id':

                        s.locale_id = (
                            self.argument_value(argument))

                    else:

                        ps.status = None
                        break

                if ps.status:

                    ps('state_translation_gist_id')
                    ps('status')

            elif name_str != '__typename':

                ps.object_flag = True

        ps.translations_flag = (
            'translations' in ps.field_set)

        ps.status_flag = (
            ps.status is not None)

        ps.status_translations_flag = (
            'status_translations' in ps.field_set)

    def parse_columns(self, field_asts):

        cs = (
            self.column_selection)

        for field in field_asts:

            name_str = field.name.value

            if name_str in cs:

                cs(name_str)

            elif name_str != '__typename':

                cs.object_flag = True

    def published_condition(self, published):

        state_id_tuple = (

            tuple_(
                dbDictionary.state_translation_gist_client_id,
                dbDictionary.state_translation_gist_object_id))

        if self.published_query is None:

            # Query or CTE.
            #
            # NOTE:
            #
            # Need to use a subquery query in case we join with translationgist / translationatom
            # outside of it.

            self.published_query = (

                get_published_translation_gist_id_subquery_query()
                    if self.published_condition_count <= 1 else
                    get_published_translation_gist_id_cte_query())

        return (

            (state_id_tuple.in_
                if published else
                state_id_tuple.notin_)

                (self.published_query))

    def translations_join(
        self,
        selection,
        gist_client_id_str,
        gist_object_id_str,
        name):

        if selection.cte is not None:

            translation_query = (

                DBSession

                    .query(
                        selection.c.client_id,
                        selection.c.object_id)

                    .outerjoin(
                        dbTranslationAtom,

                        and_(
                            dbTranslationAtom.parent_client_id == getattr(selection.c, gist_client_id_str),
                            dbTranslationAtom.parent_object_id == getattr(selection.c, gist_object_id_str),
                            dbTranslationAtom.marked_for_deletion == False))

                    .add_columns(

                        func.jsonb_object_agg(
                            dbTranslationAtom.locale_id,
                            dbTranslationAtom.content)

                            .filter(dbTranslationAtom.locale_id != None)
                            .label(name))

                    .group_by(
                        selection.c.client_id,
                        selection.c.object_id)

                    .subquery())

            selection.query = (

                selection.query

                    .join(
                        translation_query,

                        and_(
                            translation_query.c.client_id == selection.c.client_id,
                            translation_query.c.object_id == selection.c.object_id))

                    .add_columns(
                        translation_query.c[name]))

        else:

            selection.query = (

                selection.query

                    .outerjoin(
                        dbTranslationAtom,

                        and_(
                            dbTranslationAtom.parent_client_id == getattr(selection.c, gist_client_id_str),
                            dbTranslationAtom.parent_object_id == getattr(selection.c, gist_object_id_str),
                            dbTranslationAtom.marked_for_deletion == False))

                    .add_columns(

                        func.jsonb_object_agg(
                            dbTranslationAtom.locale_id,
                            dbTranslationAtom.content)

                            .filter(dbTranslationAtom.locale_id != None)
                            .label(name))

                    .group_by(
                        selection.c.client_id,
                        selection.c.object_id))

    def translation_join(
        self,
        selection,
        locale_id,
        gist_client_id_str,
        gist_object_id_str,
        name):

        if selection.cte is not None:

            translation_query = (

                DBSession

                    .query(
                        selection.c.client_id,
                        selection.c.object_id)

                    .outerjoin(
                        dbTranslationAtom,

                        and_(
                            dbTranslationAtom.parent_client_id == getattr(selection.c, gist_client_id_str),
                            dbTranslationAtom.parent_object_id == getattr(selection.c, gist_object_id_str),
                            dbTranslationAtom.marked_for_deletion == False,
                            dbTranslationAtom.locale_id == locale_id))

                    .add_columns(

                        dbTranslationAtom.content
                            .label(name))

                    .distinct(
                        selection.c.client_id,
                        selection.c.object_id,
                        dbTranslationAtom.locale_id)

                    .order_by(
                        selection.c.client_id,
                        selection.c.object_id,
                        dbTranslationAtom.locale_id,
                        dbTranslationAtom.created_at.desc())

                    .subquery())

            selection.query = (

                selection.query

                    .join(
                        translation_query,

                        and_(
                            translation_query.c.client_id == selection.c.client_id,
                            translation_query.c.object_id == selection.c.object_id))

                    .add_columns(
                        translation_query.c[name]))

        else:

            selection.query = (

                selection.query

                    .outerjoin(
                        dbTranslationAtom,

                        and_(
                            dbTranslationAtom.parent_client_id == getattr(selection.c, gist_client_id_str),
                            dbTranslationAtom.parent_object_id == getattr(selection.c, gist_object_id_str),
                            dbTranslationAtom.marked_for_deletion == False,
                            dbTranslationAtom.locale_id == locale_id))

                    .add_columns(

                        dbTranslationAtom.content
                            .label(name))

                    .distinct(
                        selection.c.client_id,
                        selection.c.object_id,
                        dbTranslationAtom.locale_id)

                    .order_by(
                        selection.c.client_id,
                        selection.c.object_id,
                        dbTranslationAtom.locale_id,
                        dbTranslationAtom.created_at.desc()))

    def dictionary_condition_list(
        self, category, deleted, published):

        condition_list = []

        if category is not None:

            condition_list.append(
                dbDictionary.category == category)

        if deleted is not None:

            condition_list.append(
                dbDictionary.marked_for_deletion == deleted)

        if published is not None:

            condition_list.append(
                self.published_condition(published))

        if self.dictionary_id_c is not None:

            condition_list.append(

                tuple_(
                    dbDictionary.client_id,
                    dbDictionary.object_id)

                    .in_(
                        DBSession.query(
                            self.dictionary_id_c.client_id,
                            self.dictionary_id_c.object_id)))

        return condition_list

    def dictionary_count_join(
        self, name, category, deleted, published):

        ls = (
            self.language_selection)

        # Using a base language-dictionary CTE, if we have one.

        if self.ld_base_cte_args == (category, deleted, published):

            ld_base_c = self.ld_base_cte.c

            # Assuming that we have the language CTE due to at least two count joins, so a join to a
            # separate count query.

            count_query = (

                DBSession

                    .query(
                        ld_base_c.client_id,
                        ld_base_c.object_id,

                        func.count()
                            .filter(ld_base_c.dictionary_client_id != None)
                            .label(name))

                    .group_by(
                        ld_base_c.client_id,
                        ld_base_c.object_id)

                    .subquery())

            ls.query = (

                ls.query

                    .join(
                        count_query,

                        and_(
                            count_query.c.client_id == ls.c.client_id,
                            count_query.c.object_id == ls.c.object_id))

                    .add_columns(
                        count_query.c[name]))

            return

        # No base CTE, using join to the dictionaries.

        condition_list = (

            self.dictionary_condition_list(
                category,
                deleted,
                published))

        if ls.cte is not None:

            count_query = (

                DBSession

                    .query(
                        ls.c.client_id,
                        ls.c.object_id)

                    .outerjoin(
                        dbDictionary,

                        and_(
                            dbDictionary.parent_client_id == ls.c.client_id,
                            dbDictionary.parent_object_id == ls.c.object_id,
                            *condition_list))

                    .add_columns(

                        func.count()
                            .filter(dbDictionary.client_id != None)
                            .label(name))

                    .group_by(
                        ls.c.client_id,
                        ls.c.object_id)

                    .subquery())

            ls.query = (

                ls.query

                    .join(
                        count_query,

                        and_(
                            count_query.c.client_id == ls.c.client_id,
                            count_query.c.object_id == ls.c.object_id))

                    .add_columns(
                        count_query.c[name]))

        else:

            ls.query = (

                ls.query

                    .outerjoin(
                        dbDictionary,

                        and_(
                            dbDictionary.parent_client_id == ls.c.client_id,
                            dbDictionary.parent_object_id == ls.c.object_id,
                            *condition_list))

                    .add_columns(

                        func.count()
                            .filter(dbDictionary.client_id != None)
                            .label(name))

                    .group_by(
                        ls.c.client_id,
                        ls.c.object_id))

    def run(self):

        from lingvodoc.schema.gql_dictionaryperspective import DictionaryPerspective as Perspective

        # Analyzing query.

        if self.debug_flag:

            log.debug(
                f'\n field_asts:\n {self.field_asts}')

        ls = (

            Resolver_Selection({

                'additional_metadata': (
                    dbLanguage.additional_metadata,),

                'created_at': (
                    dbLanguage.created_at,),

                'id': (
                    dbLanguage.client_id,
                    dbLanguage.object_id),

                'in_toc': (
                    dbLanguage.additional_metadata,),

                'marked_for_deletion': (
                    dbLanguage.marked_for_deletion,),

                'parent_id': (
                    dbLanguage.parent_client_id,
                    dbLanguage.parent_object_id),

                'translation_gist_id': (
                    dbLanguage.translation_gist_client_id,
                    dbLanguage.translation_gist_object_id),

                'translations': (
                    dbLanguage.translation_gist_client_id,
                    dbLanguage.translation_gist_object_id)}))

        self.language_selection = ls

        ls.dictionary_count = None
        ls.dictionaries = None
        ls.translation = None

        for field in self.field_asts:

            if field.name.value != 'languages':
                continue

            self.parse_languages(
                field.selection_set.selections)

            break

        ls('id')

        ls.in_toc_flag = (
            'in_toc' in ls.field_set)

        ls.translation_flag = (
            ls.translation is not None)

        ls.translations_flag = (
            'translations' in ls.field_set)

        def recursive_count_f(count_dict):
            """
            Creates recursive count computing function.
            """

            recursive_count_dict = {}

            def f(id):

                recursive_count = recursive_count_dict.get(id)

                if recursive_count is not None:
                    return recursive_count

                recursive_count = (

                    count_dict[id] +

                    sum(f(to_id)
                        for to_id in self.from_to_dict[id]))

                recursive_count_dict[id] = recursive_count

                return recursive_count

            return f

        def simple_count_f(count_dict):
            """
            Creates simple count computing function.
            """

            def f(id):

                return count_dict.get(id, 0)

            return f

        # If we are both filtering by dictionary counts and sorting languages by grants / organizations,
        # we'll be using a base language-dictionary CTE for both.

        self.grant_or_organization_id = (

            self.args.grant_id is not None or
            self.args.organization_id is not None)

        self.grant_or_organization = (

            self.args.by_grants and
                self.args.grant_id is None or

            self.args.by_organizations and
                self.args.organization_id is None)

        self.ld_base_cte = None
        self.ld_base_cte_args = None

        if self.grant_or_organization:

            if self.args.only_with_dictionaries_recursive:

                self.ld_base_cte_args = (

                    self.args.dictionary_category,
                    False,
                    self.args.dictionary_published)

            # No common base CTE, it would be a separate join, we check if we'll be needing a published
            # condition check.

            elif self.args.dictionary_published is not None:

                self.published_condition_count += 1

            # For aggregate count representation.

            empty_count_dict = {}
            self.aggregate_count_dict = {}

        #
        # Determining if we'll need any dictionary count and other joins.
        #
        # NOTE:
        #
        # We have two ways to compute recursive dictionary counts for languages, fully on SQL side and
        # partially on Python side.
        #
        # For example, ToC languages.
        #
        # Full SQL computation required 3 temporary tables and a big SQL script, partially Python
        # computation has only 1 temporary table, will receive raw dictionary counts for 400+ related
        # languages with their ids and parent ids, and transfer around 100 less lines of SQL to the DB.
        #
        # Testing (with log level WARN instead of DEBUG):
        #
        #   t0 = time.time()
        #
        #   for i in range(256):
        #       language_toc_sql(self)
        #
        #   t1 = time.time()
        #
        #   result_1 = (
        #       sorted(language_toc_sql(self)))
        #
        #   print(len(result_1))
        #   pprint.pprint(result_1, width = 192)
        #   print(hashlib.md5(repr(result_1).encode('utf-8')).hexdigest())
        #
        #   t2 = time.time()
        #
        #   for i in range(256):
        #       language_toc_python(self)
        #
        #   t3 = time.time()
        #
        #   result_2 = (
        #       sorted(language_toc_python(self)))
        #
        #   print(len(result_2))
        #   pprint.pprint(result_2, width = 192)
        #   print(hashlib.md5(repr(result_2).encode('utf-8')).hexdigest())
        #
        #   log.debug(
        #       f'\nt1 - t0: {t1 - t0:.6f}s'
        #       f'\nt3 - t2: {t3 - t2:.6f}s')
        #
        # Looks like language_toc_python() is about 20% faster.
        #
        # So we should compute languages' recursive dictionary count via Python.
        #

        dictionary_count_dict = {}

        dictionary_filter_f = None
        dictionary_count_f = None

        ls.recursive_count_flag = False

        if (self.args.only_with_dictionaries_recursive and
            (dc := ls.dictionary_count) and
            dc.category == self.args.dictionary_category and
            dc.published == self.args.dictionary_published):

            # Single shared count.

            dc_args = (
                dc.category,
                False,
                dc.published)

            count_dict = {}

            dictionary_count_dict[dc_args] = (
                ('dictionary_count', count_dict))

            ls.recursive_count_flag = True

            if self.args.dictionary_published is not None:

                self.published_condition_count += 1

            dictionary_filter_f = (
                recursive_count_f(count_dict))

            dictionary_count_f = (

                dictionary_filter_f
                    if dc.recursive else
                    simple_count_f(count_dict))

        else:

            # Only one or two separate counts.

            if self.args.only_with_dictionaries_recursive:

                dc_args = (
                    self.args.dictionary_category,
                    False,
                    self.args.dictionary_published)

                count_dict = {}

                dictionary_count_dict[dc_args] = (
                    ('dictionary_count_0', count_dict))

                ls.recursive_count_flag = True

                if self.args.dictionary_published is not None:

                    self.published_condition_count += 1

                dictionary_filter_f = (
                    recursive_count_f(count_dict))

            if (dc := ls.dictionary_count):

                dc_args = (
                    dc.category,
                    False,
                    dc.published)

                count_dict = {}

                dictionary_count_dict[dc_args] = (
                    ('dictionary_count_1', count_dict))

                if dc.recursive:

                    ls.recursive_count_flag = True

                if dc.published is not None:

                    self.published_condition_count += 1

                dictionary_count_f = (

                    recursive_count_f(count_dict)
                        if dc.recursive else
                        simple_count_f(count_dict))

        join_count = (
            len(dictionary_count_dict))

        if self.grant_or_organization:
            join_count += 1

        if ls.translation_flag:
            join_count += 1

        if ls.translations_flag:
            join_count += 1

        # If we are returning languages in tree order and at the same time getting a translation, we have to
        # use a CTE because otherwise order by of translation's distinct on messes up tree order preliminary
        # order by.
        #
        # If we are constructing language trees by grants or organizations, we'll need to use a CTE due to
        # an involved multi-stage per grant / per organization dictionary count retrieval requiring it.

        ls.cte_flag = (
            self.args.in_tree_order and ls.translation_flag or
            self.grant_or_organization or
            join_count > 1)

        ls.join_flag = (
            join_count >= 1)

        if ls.object_flag:

            ls.column_list = [dbLanguage]

        else:

            # For ToC inclusion checking, if required.

            if ls.in_toc_flag:

                ls('additional_metadata')

            # For standard ordering.

            if self.args.in_tree_order:

                ls('parent_id')

                if ls.cte_flag:

                    ls('additional_metadata')

            # For computing recursive dictionary counts and/or getting languages bottom-up from
            # dictionaries.

            if (ls.recursive_count_flag or
                self.grant_or_organization_id):

                ls('parent_id')

        # Base language query.

        self.dictionary_id_c = None

        if (language_id := self.args.language_id) is not None:

            # Language subtree.

            if ls.dictionaries:

                column_list = (

                    dbLanguage.client_id,
                    dbLanguage.object_id)

            else:

                column_list = (

                    ls.column_list)

            base_cte = (

                DBSession

                    .query(
                        *column_list)

                    .filter(
                        dbLanguage.client_id == language_id[0],
                        dbLanguage.object_id == language_id[1],
                        dbLanguage.marked_for_deletion == False)

                    .cte(recursive = True))

            recursive_query = (

                DBSession

                    .query(
                        *column_list)

                    .filter(
                        dbLanguage.parent_client_id == base_cte.c.client_id,
                        dbLanguage.parent_object_id == base_cte.c.object_id,
                        dbLanguage.marked_for_deletion == False))

            language_cte = (
                base_cte.union(recursive_query))

            ls.c = language_cte.c

            if (ls.object_flag and
                not ls.dictionaries):

                language_cte = (

                    aliased(
                        dbLanguage,
                        language_cte,
                        adapt_on_names = True))

                ls.c = language_cte

            ls.query = (
                DBSession.query(language_cte))

        elif self.grant_or_organization_id:

            # Languages of a grant or of an organization.
            #
            # We'll have to get dictionary ids through raw SQL as SQLAlchemy is bad with PostgreSQL's
            # jsonb_to_recordset.

            sql_str = f'''

                select P.*

                from
                  {'public.grant'
                    if self.args.grant_id is not None else
                    'organization'} S

                cross join
                  jsonb_to_recordset(S.additional_metadata -> 'participant')
                    P (client_id bigint, object_id bigint)

                where S.id = {
                  self.args.grant_id
                    if self.args.grant_id is not None else
                    self.args.organization_id};

                '''

            dictionary_id_query = (

                sqlalchemy

                    .text(sql_str)

                    .columns(
                        client_id = SLBigInteger,
                        object_id = SLBigInteger)

                    .alias())

            self.dictionary_id_c = (
                dictionary_id_query.c)

            if ls.dictionaries:

                # If we are going to get dictionaries, we save dictionary ids in a temporary table to be
                # used for filtering later.

                dictionary_table_name = (

                    'dictionary_' +
                     str(uuid.uuid4()).replace('-', '_'))

                dictionary_id_table = (

                    sqlalchemy.Table(
                        dictionary_table_name,
                        models.Base.metadata,
                        sqlalchemy.Column('client_id', SLBigInteger),
                        sqlalchemy.Column('object_id', SLBigInteger),
                        prefixes = ['temporary'],
                        postgresql_on_commit = 'drop'))

                dictionary_id_table.create(
                    DBSession.connection())

                DBSession.execute(

                    dictionary_id_table

                        .insert()

                        .from_select(
                            (self.dictionary_id_c.client_id, self.dictionary_id_c.object_id),
                            dictionary_id_query))

                self.dictionary_id_c = (
                    dictionary_id_table.c)

            elif dictionary_count_dict:

                # Othwerwise, if we'll need to filter based on dictionary ids when getting dictionary
                # counts, we turn dictionary id query into a CTE.

                dictionary_id_cte = (
                    dictionary_id_query.cte())

                self.dictionary_id_c = (
                    dictionary_id_cte.c)

            # Getting languages bottom-up from dictionaries through recursive CTE.

            base_cte = (

                DBSession

                    .query(
                        *ls.column_list)

                    .filter(
                        dbDictionary.client_id == self.dictionary_id_c.client_id,
                        dbDictionary.object_id == self.dictionary_id_c.object_id,
                        dbLanguage.client_id == dbDictionary.parent_client_id,
                        dbLanguage.object_id == dbDictionary.parent_object_id,
                        dbLanguage.marked_for_deletion == False)

                    .group_by(
                        dbLanguage.client_id,
                        dbLanguage.object_id)

                    .cte(recursive = True))

            recursive_query = (

                DBSession

                    .query(
                        *ls.column_list)

                    .filter(
                        dbLanguage.client_id == base_cte.c.parent_client_id,
                        dbLanguage.object_id == base_cte.c.parent_object_id,
                        dbLanguage.marked_for_deletion == False)

                    .group_by(
                        dbLanguage.client_id,
                        dbLanguage.object_id))

            language_cte = (
                base_cte.union(recursive_query))

            ls.c = language_cte.c

            if ls.object_flag:

                language_cte = (

                    aliased(
                        dbLanguage,
                        language_cte,
                        adapt_on_names = True))

                ls.c = language_cte

            ls.query = (
                DBSession.query(language_cte))

        else:

            # Just all languages.

            ls.query = (

                DBSession

                    .query(
                        *ls.column_list)

                    .filter_by(
                        marked_for_deletion = False))

            ls.c = dbLanguage

        # Filtering by ids, if required.

        if self.args.id_list is not None:

            ls.query = (

                ls.query.filter(

                    tuple_(
                        ls.c.client_id,
                        ls.c.object_id)

                        .in_(
                            ids_to_id_query(
                                self.args.id_list))))

        # Filtering by language table of contents status, if required.

        if self.args.only_in_toc:

            ls.query = (

                ls.query.filter(

                    cast(
                        ls.c.additional_metadata['toc_mark'],
                        Boolean)))

        # If we are going to get dictionaries, we save language info in a temporary table, unless we've got
        # dictionary ids directly from grant or organization.
        #
        # We also might need language info to trace language tree paths up to the root to enable proper
        # ordering of languages in tree order or to get language / dictionary / perspective tree path info.

        if (ls.dictionaries and
            not self.grant_or_organization_id

            or

            self.args.in_tree_order and
            (self.args.id_list or self.args.only_in_toc)):

            self.language_table_name = (

                'language_' +
                 str(uuid.uuid4()).replace('-', '_'))

            # Testing shows that only id temporary table is slightly faster than the full one, like 7.55 to
            # 7.88 relative times.
            #
            # If we could, we should have used insert CTE, but as of now SQLAlchemy does not support adding
            # unrelated CTEs to queries.

            if True:

                language_table = (

                    sqlalchemy.Table(
                        self.language_table_name,
                        models.Base.metadata,
                        sqlalchemy.Column('client_id', SLBigInteger),
                        sqlalchemy.Column('object_id', SLBigInteger),
                        prefixes = ['temporary'],
                        postgresql_on_commit = 'drop'))

                language_table.create(
                    DBSession.connection())

                DBSession.execute(

                    language_table

                        .insert()

                        .from_select(
                            (ls.c.client_id, ls.c.object_id),
                            ls.query.with_entities(
                                ls.c.client_id, ls.c.object_id)))

                ls.query = (

                    DBSession

                        .query(
                            *ls.column_list)

                        .filter(

                            tuple_(
                                dbLanguage.client_id,
                                dbLanguage.object_id)

                                .in_(
                                    DBSession.query(language_table))))

                ls.c = dbLanguage

            else:

                language_table = (

                    sqlalchemy.Table(
                        self.language_table_name,
                        models.Base.metadata,
                        *(sqlalchemy.Column(column.name, column.type)
                            for column in ls.column_list),
                        prefixes = ['temporary'],
                        postgresql_on_commit = 'drop'))

                language_table.create(
                    DBSession.connection())

                DBSession.execute(

                    language_table

                        .insert()

                        .from_select(
                            ls.column_list,
                            ls.query))

                ls.query = (

                    DBSession.query(
                        language_table))

                ls.c = language_table.c

        # If we are going to query both translations and dictionary counts or other non-singular sets of
        # derived attributes, we'll need to use separate joins to a base CTE.

        ls.cte = None

        if ls.cte_flag:

            ls.cte = ls.query.cte()
            ls.c = ls.cte.c

            if ls.object_flag:

                ls.cte = (

                    aliased(
                        dbLanguage,
                        ls.cte,
                        adapt_on_names = True))

                ls.c = ls.cte

            ls.query = (
                DBSession.query(ls.cte))

        #
        # Getting translations through a join, if required.
        #
        # NOTE:
        #
        # Testing getting translations from cache / from DB with example of ToC languages
        # (with log level WARN instead of DEBUG):
        #
        #   t0 = time.time()
        #
        #   for i in range(256):
        #       toc_translations_cache(self, toc_list)
        #
        #   t1 = time.time()
        #
        #   result_1 = toc_translations_cache(self, toc_list)
        #
        #   print(len(result_1))
        #
        #   result_1_sorted = (
        #
        #       sorted(
        #           (key, None if value is None else sorted(value.items()))
        #           for key, value in result_1.items()))
        #
        #   pprint.pprint(result_1_sorted, width = 192)
        #
        #   print(
        #       hashlib.md5(
        #           repr(result_1_sorted).encode('utf-8'))
        #           .hexdigest())
        #
        #   t2 = time.time()
        #
        #   for i in range(256):
        #       toc_translations_db(self, toc_list)
        #
        #   t3 = time.time()
        #
        #   result_2 = toc_translations_db(self, toc_list)
        #
        #   print(len(result_2))
        #
        #   result_2_sorted = (
        #
        #       sorted(
        #           (key, None if value is None else sorted(value.items()))
        #           for key, value in result_2.items()))
        #
        #   pprint.pprint(result_2_sorted, width = 192)
        #
        #   print(
        #       hashlib.md5(
        #           repr(result_2_sorted).encode('utf-8'))
        #           .hexdigest())
        #
        #   log.debug(
        #       f'\nt1 - t0: {t1 - t0:.6f}s'
        #       f'\nt3 - t2: {t3 - t2:.6f}s')
        #
        # Looks like toc_translations_db() is about 2-3 times faster.
        #
        # So if possible, we should get translations from DB.
        #

        if ls.translation_flag:

            self.translation_join(
                ls,
                ls.translation.locale_id or self.info.context.locale_id,
                'translation_gist_client_id',
                'translation_gist_object_id',
                'translation')

        if ls.translations_flag:

            self.translations_join(
                ls,
                'translation_gist_client_id',
                'translation_gist_object_id',
                'translations')

        # Creating a base language-dictionary CTE, if required.

        if self.ld_base_cte_args:

            condition_list = (

                self.dictionary_condition_list(
                    *self.ld_base_cte_args))

            # Assuming that we have the language CTE due to at least two count joins.

            if ls.cte is None:
                raise NotImplementedError

            self.ld_base_cte = (

                DBSession

                    .query(
                        ls.c.client_id,
                        ls.c.object_id)

                    .outerjoin(
                        dbDictionary,

                        and_(
                            dbDictionary.parent_client_id == ls.c.client_id,
                            dbDictionary.parent_object_id == ls.c.object_id,
                            *condition_list))

                    .add_columns(
                        dbDictionary.client_id.label('dictionary_client_id'),
                        dbDictionary.object_id.label('dictionary_object_id'))

                    .cte('ld_base'))

        # Getting dictionary counts through a join, if required.

        for dc_args, dc_name_count in dictionary_count_dict.items():

            self.dictionary_count_join(
                dc_name_count[0], *dc_args)

        # Getting aggregate grant/organization counts, if required.
        #
        # In that case we'll have the language CTE due to an involved multi-stage per grant / per
        # organization dictionary count retrieval requiring it.

        if self.grant_or_organization:

            sql_str = f'''

                select
                  P.client_id,
                  P.object_id,
                  G.id

                from
                  {'public.grant'
                    if self.args.by_grants else
                    'organization'} G

                cross join
                  jsonb_to_recordset(G.additional_metadata -> 'participant')
                    P (client_id bigint, object_id bigint)

                {''
                  if self.args.by_grants else
                  'where G.marked_for_deletion = false'}

                '''

            participant_query = (

                sqlalchemy

                    .text(sql_str)

                    .columns(
                        client_id = SLBigInteger,
                        object_id = SLBigInteger,
                        id = SLBigInteger)

                    .alias('participant'))

            # Using a base language-dictionary CTE, if we have one.

            if self.ld_base_cte is not None:

                ld_base_c = self.ld_base_cte.c

                joint_query = (

                    DBSession

                        .query(
                            ld_base_c.client_id,
                            ld_base_c.object_id)

                        .outerjoin(
                            participant_query,

                            and_(
                                ld_base_c.dictionary_client_id == participant_query.c.client_id,
                                ld_base_c.dictionary_object_id == participant_query.c.object_id))

                        .add_columns(

                            sqlalchemy

                                .literal_column('''
                                    (case when ld_base.dictionary_client_id is null then null else
                                        coalesce(participant.id :: text, '') end)
                                    ''')

                                .label('group_id'))

                        .subquery())

            # No base CTE, using join to the dictionaries.

            else:

                condition_list = (

                    self.dictionary_condition_list(
                        self.args.dictionary_category,
                        False,
                        self.args.dictionary_published))

                joint_query = (

                    DBSession

                        .query(
                            ls.c.client_id,
                            ls.c.object_id)

                        .outerjoin(
                            dbDictionary,

                            and_(
                                dbDictionary.parent_client_id == ls.c.client_id,
                                dbDictionary.parent_object_id == ls.c.object_id,
                                *condition_list))

                        .add_columns(
                            dbDictionary.client_id.label('dictionary_client_id'),
                            dbDictionary.object_id.label('dictionary_object_id'))

                        .outerjoin(
                            participant_query,

                            and_(
                                dbDictionary.client_id == participant_query.client_id,
                                dbDictionary.object_id == participant_query.object_id))

                        .add_columns(

                            sqlalchemy

                                .literal_column('''
                                    (case when dictionary.client_id is null then null else
                                        coalesce(participant.id :: text, '') end)
                                    ''')

                                .label('group_id'))

                        .subquery())

            base_count_query = (

                DBSession

                    .query(
                        joint_query.c.client_id,
                        joint_query.c.object_id,
                        joint_query.c.group_id,

                        func.count()
                            .filter(joint_query.c.group_id != None)
                            .label('base_count'))

                    .group_by(
                        joint_query.c.client_id,
                        joint_query.c.object_id,
                        joint_query.c.group_id)

                    .subquery())

            aggregate_count_query = (

                DBSession

                    .query(
                        base_count_query.c.client_id,
                        base_count_query.c.object_id,

                        func
                            .jsonb_object_agg(
                                base_count_query.c.group_id,
                                base_count_query.c.base_count)

                            .filter(
                                base_count_query.c.group_id != None)

                            .label('aggregate_count'))

                    .group_by(
                        base_count_query.c.client_id,
                        base_count_query.c.object_id)

                    .subquery())

            ls.query = (

                ls.query

                    .join(
                        aggregate_count_query,

                        and_(
                            aggregate_count_query.c.client_id == ls.c.client_id,
                            aggregate_count_query.c.object_id == ls.c.object_id))

                    .add_columns(
                        aggregate_count_query.c.aggregate_count))

        # If we require languages in the language tree order, we establish preliminary ordering.

        if self.args.in_tree_order:

            ls.query = (

                ls.query

                    .order_by(
                        ls.c.additional_metadata['younger_siblings'],
                        ls.c.client_id.desc(),
                        ls.c.object_id.desc()))

        # Getting language data.

        result_list = ls.query.all()

        if self.debug_flag:

            log.debug(
                f'\n language_query ({len(result_list)} languages):\n ' +
                render_statement(ls.query.statement))

        # Generating language tree data and dictionary counts, if required.

        self.arbitrary_root_set = (

            self.args.in_tree_order and
            (self.args.id_list or self.args.only_in_toc))

        if (self.args.in_tree_order or
            ls.recursive_count_flag or
            self.grant_or_organization):

            if not self.arbitrary_root_set:

                self.from_to_dict = collections.defaultdict(list)

            for result in result_list:

                if ls.object_flag:

                    language = (
                        result[0] if ls.join_flag else result)

                    id = language.id
                    parent_id = language.parent_id

                else:

                    id = (
                        result.client_id, result.object_id)

                    parent_id = (
                        result.parent_client_id, result.parent_object_id)

                # Processing language tree data, unless we don't have full paths to the language hierarchy
                # root in our language set and we'll have to get fully traceable language set later and
                # build language tree data from it.

                if not self.arbitrary_root_set:

                    self.from_to_dict[parent_id].append(id)

                for name, count_dict in dictionary_count_dict.values():

                    count_dict[id] = (
                        getattr(result, name))

                if self.grant_or_organization:

                    self.aggregate_count_dict[id] = (
                        result.aggregate_count or empty_count_dict)

        if self.debug_flag:

            for name, count_dict in dictionary_count_dict.values():

                log.debug(

                    f'\n count_dict({name}):\n' +

                    pprint.pformat(
                        count_dict, width = 144))

            if self.grant_or_organization:

                log.debug(

                    f'\n aggregate_count_dict:\n' +

                    pprint.pformat(
                        self.aggregate_count_dict, width = 144))

        gql_language_list = []

        gql_language_dict_flag = (

            self.args.in_tree_order or
            ls.dictionaries)

        if gql_language_dict_flag:

            gql_language_dict = {}

        self.filtered_out_id_set = set()

        if ls.in_toc_flag:

            ls.field_set.discard('in_toc')
            ls.field_set.discard('additional_metadata')

        if ls.object_flag:

            # We are getting full ORM dbLanguage objects.

            attribute_set = ls.field_set.copy()

            attribute_set.discard('translation')
            attribute_set.discard('translations')

            for result in result_list:

                language = (
                    result[0] if ls.join_flag else result)

                language_id = language.id

                # Filtering based on a dictionary count if required. 

                if (dictionary_filter_f and
                    dictionary_filter_f(language_id) <= 0):

                    self.filtered_out_id_set.add(language_id)
                    continue

                gql_language = (
                    Language(id = language_id))

                gql_language.dbObject = language

                # Computed attributes.

                if ls.in_toc_flag:

                    metadata = (
                        result.additional_metadata)

                    gql_language.in_toc = (

                        metadata is not None and
                        metadata.get('toc_mark', False))

                    gql_language.additional_metadata = (
                        AdditionalMetadata.from_object(metadata))

                if ls.translation_flag:

                    translation = (
                        result.translation)

                    gql_language.translation = (
                        translation if translation is not None else gql_none_value)

                if ls.translations_flag:

                    translations = (
                        result.translations)

                    gql_language.translations = (
                        translations if translations is not None else gql_none_value)

                if dictionary_count_f:

                    gql_language.dictionary_count = (
                        dictionary_count_f(language_id))

                # Standard attributes.

                for attribute in attribute_set:

                    value = (
                        getattr(language, attribute))

                    if attribute == 'additional_metadata':

                        value = AdditionalMetadata.from_object(value)

                    elif attribute == 'created_at':

                        value = CreatedAt.from_timestamp(value)

                    setattr(
                        gql_language,
                        attribute,
                        value)

                if not self.args.in_tree_order:

                    gql_language_list.append(gql_language)

                if gql_language_dict_flag:

                    gql_language_dict[language_id] = gql_language

        else:

            # We are getting attribute values as they are.

            for result in result_list:

                language_id = (
                    result.client_id, result.object_id)

                # Filtering based on a dictionary count if required. 

                if (dictionary_filter_f and
                    dictionary_filter_f(language_id) <= 0):

                    self.filtered_out_id_set.add(language_id)
                    continue

                gql_language = (
                    Language(id = language_id))

                if ls.in_toc_flag:

                    metadata = (
                        result.additional_metadata)

                    gql_language.in_toc = (

                        metadata is not None and
                        metadata.get('toc_mark', False))

                    gql_language.additional_metadata = (
                        AdditionalMetadata.from_object(metadata))

                if dictionary_count_f:

                    gql_language.dictionary_count = (
                        dictionary_count_f(language_id))

                for field_str in ls.field_set:

                    if field_str == 'id':

                        gql_language.id = language_id

                        continue

                    elif field_str == 'parent_id':

                        parent_client_id = (
                            result.parent_client_id)

                        gql_language.parent_id = (

                            gql_none_value

                            if parent_client_id is None else

                            (parent_client_id,
                                result.parent_object_id))

                        continue

                    elif field_str == 'translation_gist_id':

                        gql_language.translation_gist_id = (

                            result.translation_gist_client_id,
                            result.translation_gist_object_id)

                        continue

                    value = getattr(result, field_str)

                    if field_str == 'additional_metadata':

                        value = AdditionalMetadata.from_object(value)

                    elif field_str == 'created_at':

                        value = CreatedAt.from_timestamp(value)

                    setattr(
                        gql_language,
                        field_str,
                        value if value is not None else gql_none_value)

                if not self.args.in_tree_order:

                    gql_language_list.append(gql_language)

                if gql_language_dict_flag:

                    gql_language_dict[language_id] = gql_language

        # If we need to return languages in the standard language tree order, we order languages by
        # recursively traversing the tree we build earlier, the order is guaranteed by the preliminary
        # ordering we received languages from the DB in.

        if self.args.in_tree_order:

            def f(id):

                gql_language = (
                    gql_language_dict.get(id))

                if gql_language:

                    gql_language_list.append(
                        gql_language)

                for to_id in self.from_to_dict[id]:

                    f(to_id)

            # Filtering languages explicitly or based on ToC status, an arbitrary number of tree roots, and
            # we'll have to find them and traverse them in the right order, so we'll have to compile full
            # language ordering info.

            if (self.args.id_list or
                self.args.only_in_toc):

                base_cte = (

                    DBSession

                        .query(
                            dbLanguage.client_id,
                            dbLanguage.object_id,
                            dbLanguage.parent_client_id,
                            dbLanguage.parent_object_id,
                            dbLanguage.additional_metadata)

                        .filter(
                            dbLanguage.client_id == language_table.c.client_id,
                            dbLanguage.object_id == language_table.c.object_id)

                        .cte(recursive = True))

                recursive_query = (

                    DBSession

                        .query(
                            dbLanguage.client_id,
                            dbLanguage.object_id,
                            dbLanguage.parent_client_id,
                            dbLanguage.parent_object_id,
                            dbLanguage.additional_metadata)

                        .filter(
                            dbLanguage.client_id == base_cte.c.parent_client_id,
                            dbLanguage.object_id == base_cte.c.parent_object_id))

                language_cte = (
                    base_cte.union(recursive_query))

                language_id_id_list = (

                    DBSession

                        .query(
                            language_cte.c.client_id,
                            language_cte.c.object_id,
                            language_cte.c.parent_client_id,
                            language_cte.c.parent_object_id)

                        .order_by(
                            language_cte.c.additional_metadata['younger_siblings'],
                            language_cte.c.client_id.desc(),
                            language_cte.c.object_id.desc())

                        .all())

                self.from_to_dict = collections.defaultdict(list)

                for language_id_id in language_id_id_list:

                    id = (
                        language_id_id[0], language_id_id[1])

                    parent_id = (
                        language_id_id[2], language_id_id[3])

                    self.from_to_dict[parent_id].append(id)

            # Traversing language tree we have in the standard order, compiling final list of languages.

            root_id = (

                tuple(self.args.language_id) if self.args.language_id else
                (None, None))

            f(root_id)

            # Checking compatibility with recursive_sort(), if required.

            if self.debug_flag:

                id_list = [

                    gql_language.id
                    for gql_language in gql_language_list]

                id_set = set(id_list)

                reference_list = [

                    (client_id, object_id)
                    for _, client_id, object_id, _ in

                        recursive_sort(

                            DBSession

                                .query(dbLanguage)

                                .filter_by(
                                    marked_for_deletion = False)

                                .order_by(
                                    dbLanguage.parent_client_id,
                                    dbLanguage.parent_object_id,
                                    dbLanguage.additional_metadata['younger_siblings'],
                                    dbLanguage.client_id.desc(),
                                    dbLanguage.object_id.desc())

                                .all())

                    if (client_id, object_id) in id_set]

                if id_list != reference_list:

                    log.warning(
                        f'\nid_list:\n{pprint.pformat(id_list, width = 192)}'
                        f'\nreference_list:\n{pprint.pformat(reference_list, width = 192)}')

                    raise NotImplementedError

        if self.debug_flag:

            log.debug(
                f'\nlen(gql_language_list): {len(gql_language_list)}')

        # Getting dictionaries, if required.

        if (d := ls.dictionaries):

            condition_list = (

                self.dictionary_condition_list(
                    d.category,
                    d.deleted,
                    d.published))

            if self.dictionary_id_c is None:

                condition_list.extend((
                    dbDictionary.parent_client_id == language_table.c.client_id,
                    dbDictionary.parent_object_id == language_table.c.object_id))

            if self.filtered_out_id_set:

                condition_list.append(

                    tuple_(
                        dbDictionary.parent_client_id,
                        dbDictionary.parent_object_id)

                        .notin_(

                            ids_to_id_query(
                                self.filtered_out_id_set)))

            ds = self.dictionary_selection

            if ds.object_flag:

                ds.column_list = [dbDictionary]

            ds.query = (

                DBSession

                    .query(
                        *ds.column_list)

                    .filter(
                        *condition_list))

            ds.c = dbDictionary

            # If we are going to get perspectives, we save dictionary info in a temporary table.

            if ds.perspectives:

                dictionary_table_name = (

                    'dictionary_' +
                     str(uuid.uuid4()).replace('-', '_'))

                dictionary_table = (

                    sqlalchemy.Table(
                        dictionary_table_name,
                        models.Base.metadata,
                        sqlalchemy.Column('client_id', SLBigInteger),
                        sqlalchemy.Column('object_id', SLBigInteger),
                        prefixes = ['temporary'],
                        postgresql_on_commit = 'drop'))

                dictionary_table.create(
                    DBSession.connection())

                DBSession.execute(

                    dictionary_table

                        .insert()

                        .from_select(
                            (ds.c.client_id, ds.c.object_id),
                            ds.query.with_entities(
                                ds.c.client_id, ds.c.object_id)))

                ds.query = (

                    DBSession

                        .query(
                            *ds.column_list)

                        .filter(

                            tuple_(
                                dbDictionary.client_id,
                                dbDictionary.object_id)

                                .in_(
                                    DBSession.query(dictionary_table))))

                ds.c = dbDictionary

            # Checking for joins.

            join_count = 0

            if ds.translations_flag:
                join_count += 1

            if ds.status_flag:
                join_count += 1

            if ds.status_translations_flag:
                join_count += 1

            ds.cte_flag = (
                join_count > 1)

            ds.join_flag = (
                join_count >= 1)

            ds.cte = None

            if ds.cte_flag:

                ds.cte = ds.query.cte()
                ds.c = ds.cte.c

                if ds.object_flag:

                    ds.cte = (

                        aliased(
                            dbDictionary,
                            ds.cte,
                            adapt_on_names = True))

                    ds.c = ds.cte

                ds.query = (
                    DBSession.query(ds.cte))

            if ds.translations_flag:

                self.translations_join(
                    ds,
                    'translation_gist_client_id',
                    'translation_gist_object_id',
                    'translations')

            if ds.status_flag:

                self.translation_join(
                    ds,
                    ds.status.locale_id or self.info.context.locale_id,
                    'state_translation_gist_client_id',
                    'state_translation_gist_object_id',
                    'status')

            if ds.status_translations_flag:

                self.translations_join(
                    ds,
                    'state_translation_gist_client_id',
                    'state_translation_gist_object_id',
                    'status_translations')

            # Dictionaries go in standard order, from newest to oldest.

            ds.query = (

                ds.query

                    .order_by(
                        ds.c.created_at.desc(),
                        ds.c.client_id.desc(),
                        ds.c.object_id.desc()))

            # Getting and processing dictionary data.

            result_list = ds.query.all()

            if self.debug_flag:

                log.debug(
                    '\n dictionary_query:\n ' +
                    render_statement(ds.query.statement))

            for gql_language in gql_language_dict.values():

                gql_language.dictionaries = []

            gql_dictionary_dict_flag = (

                ds.perspectives)

            if gql_dictionary_dict_flag:

                gql_dictionary_dict = {}

            if ds.object_flag:

                # We are getting full ORM dbDictionary objects.

                attribute_set = ds.field_set.copy()

                attribute_set.discard('status')
                attribute_set.discard('status_translations')
                attribute_set.discard('translations')

                for result in result_list:

                    dictionary = (
                        result[0] if ds.join_flag else result)

                    dictionary_id = dictionary.id

                    gql_dictionary = (
                        Dictionary(id = dictionary_id))

                    gql_dictionary.dbObject = dictionary

                    # Computed attributes.

                    if ds.status_flag:

                        translation = (
                            result.status)

                        gql_dictionary.status = (
                            translation if translation is not None else gql_none_value)

                    if ds.status_translations_flag:

                        translations = (
                            result.status_translations)

                        gql_dictionary.translations = (
                            translations if translations is not None else gql_none_value)

                    if ds.translations_flag:

                        translations = (
                            result.translations)

                        gql_dictionary.translations = (
                            translations if translations is not None else gql_none_value)

                    # Standard attributes.

                    for attribute in attribute_set:

                        value = (
                            getattr(dictionary, attribute))

                        if attribute == 'additional_metadata':

                            value = AdditionalMetadata.from_object(value)

                        elif attribute == 'created_at':

                            value = CreatedAt.from_timestamp(value)

                        setattr(
                            gql_dictionary,
                            attribute,
                            value)

                    (gql_language_dict[
                        dictionary.parent_id]

                        .dictionaries
                        .append(gql_dictionary))

                    if gql_dictionary_dict_flag:

                        gql_dictionary_dict[dictionary_id] = gql_dictionary

            else:

                # We are getting attribute values as they are.

                for result in result_list:

                    dictionary_id = (
                        result.client_id, result.object_id)

                    dictionary_parent_id = (
                        result.parent_client_id, result.parent_object_id)

                    gql_dictionary = (
                        Dictionary(id = dictionary_id))

                    for field_str in ds.field_set:

                        if field_str == 'id':

                            gql_dictionary.id = dictionary_id

                            continue

                        elif field_str == 'parent_id':

                            gql_dictionary.parent_id = dictionary_parent_id

                            continue

                        elif field_str == 'state_translation_gist_id':

                            gql_dictionary.state_translation_gist_id = (

                                result.state_translation_gist_client_id,
                                result.state_translation_gist_object_id)

                            continue

                        elif field_str == 'translation_gist_id':

                            gql_dictionary.translation_gist_id = (

                                result.translation_gist_client_id,
                                result.translation_gist_object_id)

                            continue

                        value = getattr(result, field_str)

                        if field_str == 'additional_metadata':

                            value = AdditionalMetadata.from_object(value)

                        elif field_str == 'created_at':

                            value = CreatedAt.from_timestamp(value)

                        setattr(
                            gql_dictionary,
                            field_str,
                            value if value is not None else gql_none_value)

                    (gql_language_dict[
                        dictionary_parent_id]

                        .dictionaries
                        .append(gql_dictionary))

                    if gql_dictionary_dict_flag:

                        gql_dictionary_dict[dictionary_id] = gql_dictionary

        # Getting perspectives, if required.

        if (ps := self.perspective_selection):

            p = ds.perspectives

            parent_id_tuple = (

                tuple_(
                    dbPerspective.parent_client_id,
                    dbPerspective.parent_object_id))

            condition_list = [

                parent_id_tuple.in_(

                    DBSession.query(
                        dictionary_table.c.client_id,
                        dictionary_table.c.object_id)),

                dbPerspective.marked_for_deletion == False]

            if p.with_verb_data is not None:

                with_accepted_cte = (

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
                            dbValencySourceData.perspective_object_id)

                        .cte())

                id_tuple = (

                    tuple_(
                        dbPerspective.client_id,
                        dbPerspective.object_id))

                condition_list.append(

                    (id_tuple.in_ if p.with_verb_data else
                        id_tuple.notin_)(

                        DBSession.query(
                            with_accepted_cte)))

            if ps.object_flag:

                ps.column_list = [dbPerspective]

            ps.query = (

                DBSession

                    .query(
                        *ps.column_list)

                    .filter(
                        *condition_list))

            ps.c = dbPerspective

            # If we are going to get columns, we save perspective info in a temporary table.

            if ps.columns:

                self.perspective_table_name = (

                    'perspective_' +
                     str(uuid.uuid4()).replace('-', '_'))

                perspective_table = (

                    sqlalchemy.Table(
                        self.perspective_table_name,
                        models.Base.metadata,
                        sqlalchemy.Column('client_id', SLBigInteger),
                        sqlalchemy.Column('object_id', SLBigInteger),
                        prefixes = ['temporary'],
                        postgresql_on_commit = 'drop'))

                perspective_table.create(
                    DBSession.connection())

                DBSession.execute(

                    perspective_table

                        .insert()

                        .from_select(
                            (ps.c.client_id, ps.c.object_id),
                            ps.query.with_entities(
                                ps.c.client_id, ps.c.object_id)))

                ps.query = (

                    DBSession

                        .query(
                            *ps.column_list)

                        .filter(

                            tuple_(
                                dbPerspective.client_id,
                                dbPerspective.object_id)

                                .in_(
                                    DBSession.query(perspective_table))))

                ps.c = dbPerspective

            # Checking for joins.

            join_count = 0

            if ps.translations_flag:
                join_count += 1

            if ps.status_flag:
                join_count += 1

            if ps.status_translations_flag:
                join_count += 1

            ps.cte_flag = (
                join_count > 1)

            ps.join_flag = (
                join_count >= 1)

            ps.cte = None

            if ps.cte_flag:

                ps.cte = ps.query.cte()
                ps.c = ps.cte.c

                if ps.object_flag:

                    ps.cte = (

                        aliased(
                            dbPerspective,
                            ps.cte,
                            adapt_on_names = True))

                    ps.c = ps.cte

                ps.query = (
                    DBSession.query(ps.cte))

            if ps.translations_flag:

                self.translations_join(
                    ps,
                    'translation_gist_client_id',
                    'translation_gist_object_id',
                    'translations')

            if ps.status_flag:

                self.translation_join(
                    ps,
                    ps.status.locale_id or self.info.context.locale_id,
                    'state_translation_gist_client_id',
                    'state_translation_gist_object_id',
                    'status')

            if ps.status_translations_flag:

                self.translations_join(
                    ps,
                    'state_translation_gist_client_id',
                    'state_translation_gist_object_id',
                    'status_translations')

            # Perspectives go from older to newer.

            ps.query = (

                ps.query

                    .order_by(
                        ps.c.created_at,
                        ps.c.client_id,
                        ps.c.object_id))

            # Getting and processing perspective data.

            result_list = ps.query.all()

            if self.debug_flag:

                log.debug(
                    '\n perspective_query:\n ' +
                    render_statement(ps.query.statement))

            for gql_dictionary in gql_dictionary_dict.values():

                gql_dictionary.perspectives = []

            gql_perspective_dict_flag = (

                ps.columns)

            if gql_perspective_dict_flag:

                gql_perspective_dict = {}

            if ps.object_flag:

                # We are getting full ORM dbPerspective objects.

                attribute_set = ps.field_set.copy()

                attribute_set.discard('status')
                attribute_set.discard('status_translations')
                attribute_set.discard('translations')

                for result in result_list:

                    perspective = (
                        result[0] if ps.join_flag else result)

                    gql_perspective = (
                        Perspective(id = perspective.id))

                    gql_perspective.dbObject = perspective

                    # Computed attributes.

                    if ps.status_flag:

                        translation = (
                            result.status)

                        gql_perspective.status = (
                            translation if translation is not None else gql_none_value)

                    if ps.status_translations_flag:

                        translations = (
                            result.status_translations)

                        gql_perspective.translations = (
                            translations if translations is not None else gql_none_value)

                    if ps.translations_flag:

                        translations = (
                            result.translations)

                        gql_perspective.translations = (
                            translations if translations is not None else gql_none_value)

                    # Standard attributes.

                    for attribute in attribute_set:

                        value = (
                            getattr(perspective, attribute))

                        if attribute == 'additional_metadata':

                            value = AdditionalMetadata.from_object(value)

                        elif attribute == 'created_at':

                            value = CreatedAt.from_timestamp(value)

                        setattr(
                            gql_perspective,
                            attribute,
                            value)

                    (gql_dictionary_dict[
                        perspective.parent_id]

                        .perspectives
                        .append(gql_perspective))

                    if gql_perspective_dict_flag:

                        gql_perspective_dict[perspective.id] = gql_perspective

            else:

                # We are getting attribute values as they are.

                for result in result_list:

                    perspective_id = (
                        result.client_id, result.object_id)

                    perspective_parent_id = (
                        result.parent_client_id, result.parent_object_id)

                    gql_perspective = (
                        Perspective(id = perspective_id))

                    for field_str in ps.field_set:

                        if field_str == 'id':

                            gql_perspective.id = perspective_id

                            continue

                        elif field_str == 'parent_id':

                            gql_perspective.parent_id = perspective_parent_id

                            continue

                        elif field_str == 'state_translation_gist_id':

                            gql_perspective.state_translation_gist_id = (

                                result.state_translation_gist_client_id,
                                result.state_translation_gist_object_id)

                            continue

                        elif field_str == 'translation_gist_id':

                            gql_perspective.translation_gist_id = (

                                result.translation_gist_client_id,
                                result.translation_gist_object_id)

                            continue

                        value = getattr(result, field_str)

                        if field_str == 'additional_metadata':

                            value = AdditionalMetadata.from_object(value)

                        elif field_str == 'created_at':

                            value = CreatedAt.from_timestamp(value)

                        setattr(
                            gql_perspective,
                            field_str,
                            value if value is not None else gql_none_value)

                    (gql_dictionary_dict[
                        perspective_parent_id]

                        .perspectives
                        .append(gql_perspective))

                    if gql_perspective_dict_flag:

                        gql_perspective_dict[perspective_id] = gql_perspective

        # Getting columns, if required.

        if (cs := self.column_selection):

            parent_id_tuple = (

                tuple_(
                    dbColumn.parent_client_id,
                    dbColumn.parent_object_id))

            if cs.object_flag:

                cs.column_list = [dbColumn]

            cs.query = (

                DBSession

                    .query(
                        *cs.column_list)

                    .filter(

                        parent_id_tuple.in_(

                            DBSession.query(
                                perspective_table.c.client_id,
                                perspective_table.c.object_id))))

            cs.c = dbColumn

            # Getting and processing column data.

            result_list = cs.query.all()

            if self.debug_flag:

                log.debug(
                    '\n column_query:\n ' +
                    render_statement(cs.query.statement))

            for gql_perspective in gql_perspective_dict.values():

                gql_perspective.columns = []

            if cs.object_flag:

                # We are getting full ORM dbColumn objects.

                for result in result_list:

                    column = result

                    gql_column = (
                        Column(id = column.id))

                    gql_column.dbObject = column

                    # Standard attributes.

                    for attribute in cs.field_set:

                        value = (
                            getattr(column, attribute))

                        if attribute == 'created_at':

                            value = CreatedAt.from_timestamp(value)

                        setattr(
                            gql_column,
                            attribute,
                            value)

                    (gql_perspective_dict[
                        column.parent_id]

                        .columns
                        .append(gql_column))

            else:

                # We are getting attribute values as they are.

                for result in result_list:

                    column_id = (
                        result.client_id, result.object_id)

                    column_parent_id = (
                        result.parent_client_id, result.parent_object_id)

                    gql_column = (
                        Column(id = column_id))

                    for field_str in cs.field_set:

                        if field_str == 'field_id':

                            gql_column.field_id = (

                                result.field_client_id,
                                result.field_object_id)

                            continue

                        elif field_str == 'id':

                            gql_column.id = column_id

                            continue

                        elif field_str == 'link_id':

                            link_client_id = (
                                result.link_client_id)

                            gql_column.link_id = (

                                gql_none_value

                                if link_client_id is None else

                                (link_client_id,
                                    result.link_object_id))

                            continue

                        elif field_str == 'parent_id':

                            gql_column.parent_id = column_parent_id

                            continue

                        elif field_str == 'self_id':

                            self_client_id = (
                                result.self_client_id)

                            gql_column.self_id = (

                                gql_none_value

                                if self_client_id is None else

                                (self_client_id,
                                    result.self_object_id))

                            continue

                        value = getattr(result, field_str)

                        if field_str == 'created_at':

                            value = CreatedAt.from_timestamp(value)

                        setattr(
                            gql_column,
                            field_str,
                            value if value is not None else gql_none_value)

                    (gql_perspective_dict[
                        column_parent_id]

                        .columns
                        .append(gql_column))

        return gql_language_list

