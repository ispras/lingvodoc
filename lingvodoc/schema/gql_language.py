import logging

import graphene

from lingvodoc.cache.caching import CACHE
from lingvodoc.models import (
    Language as dbLanguage,
    Dictionary as dbDictionary,
    DictionaryPerspective as dbPerspective,
    TranslationAtom as dbTranslationAtom,
    Client as dbClient,
    User as dbUser,
    DBSession,
    TranslationGist as dbTranslationGist,
    BaseGroup as dbBaseGroup,
    Group as dbGroup
)

from lingvodoc.schema.gql_holders import (
    LingvodocObjectType,
    CommonFieldsComposite,
    TranslationHolder,
    fetch_object,
    del_object,
    client_id_check,
    ResponseError,
    acl_check_by_id,
    ObjectVal,
    LingvodocID
)
from lingvodoc.schema.gql_translationgist import TranslationGistInterface
from .gql_dictionary import Dictionary

from lingvodoc.utils.creation import (
    create_dblanguage,
    create_gists_with_atoms,
    add_user_to_group, update_metadata)

from lingvodoc.utils.deletion import real_delete_language
from lingvodoc.utils.search import translation_gist_search

# from lingvodoc.schema.gql_dictionary import Dictionary
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import (
    func,
    or_,
    and_,
    tuple_,
    not_
)


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
        published=graphene.Boolean())

    languages = graphene.List('lingvodoc.schema.gql_language.Language',
        deleted=graphene.Boolean())

    locale_exist = graphene.Boolean()
    dataType = graphene.String()

    tree = graphene.List('lingvodoc.schema.gql_language.Language')

    class Meta:
        interfaces = (CommonFieldsComposite, TranslationHolder, TranslationGistInterface)

    @fetch_object()
    def resolve_locale_exists(self):
        return self.dbObject.locale

    @fetch_object()
    def resolve_dictionaries(self, info, deleted = None, published = None):

        # Dictionaries of the language, in standard order, from newest to oldest.

        dictionary_query = (DBSession
                
            .query(dbDictionary)
            
            .filter(
                and_(dbDictionary.parent_object_id == self.dbObject.object_id,
                     dbDictionary.parent_client_id == self.dbObject.client_id))
                
            .order_by(dbDictionary.created_at.desc()))

        if deleted is not None:

            dictionary_query = dictionary_query.filter(
                dbDictionary.marked_for_deletion == deleted)

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

                .query(dbPerspective)

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

    @fetch_object()
    def resolve_languages(self, info, deleted = None):

        query = DBSession.query(dbLanguage).filter(
            and_(dbLanguage.parent_object_id == self.dbObject.object_id,
                 dbLanguage.parent_client_id == self.dbObject.client_id))

        if deleted is not None:
            query = query.filter(dbLanguage.marked_for_deletion == deleted)

        result = list()

        for language in query:
            gql_language = Language(id=[language.client_id, language.object_id])
            gql_language.dbObject = language
            result.append(gql_language)

        return result

    @fetch_object()
    def resolve_tree(self, info):
        result = list()
        iteritem = self.dbObject
        while iteritem:
            id = [iteritem.client_id, iteritem.object_id]
            result.append(Language(id=id))
            iteritem = iteritem.parent

        return result


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
        id = LingvodocID()
        translation_gist_id = LingvodocID()
        parent_id = LingvodocID()
        translation_atoms = graphene.List(ObjectVal)
        additional_metadata = ObjectVal()

    language = graphene.Field(Language)
    triumph = graphene.Boolean()



    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):
        id = args.get('id')
        client_id = id[0] if id else info.context["client_id"]
        object_id = id[1] if id else None
        id = [client_id, object_id]
        parent_id = args.get('parent_id')
        additional_metadata = args.get("additional_metadata")
        translation_gist_id = args.get("translation_gist_id")
        translation_atoms = args.get("translation_atoms")
        translation_gist_id = create_gists_with_atoms(
                              translation_atoms,
                              translation_gist_id,
                              [client_id,object_id],
                              gist_type="Language"
                              )

        dblanguage = create_dblanguage(id=id,
                                                      parent_id=parent_id,
                                                      translation_gist_id=translation_gist_id)

        language = Language(id=[dblanguage.client_id, dblanguage.object_id])
        language.dbObject = dblanguage
        return CreateLanguage(language=language, triumph=True)


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
        additional_metadata = args.get("additional_metadata")
        if additional_metadata:
            update_metadata(dblanguage, additional_metadata)
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
    #@client_id_check()
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
                                                parent_client_id=dblanguage.translation_gist_client_id,
                                                parent_object_id=dblanguage.translation_gist_object_id,
                                                locale_id=locale_id,
                                                content=content)
            DBSession.add(dbtranslationatom)
            DBSession.flush()

        language = Language(id=[dblanguage.client_id, dblanguage.object_id])
        language.dbObject = dbLanguage
        return UpdateLanguageAtom(language=language, triumph=True)

# class MoveLanguage(graphene.Mutation):
#     """
#     example:
#        mutation  {
#         update_language(id: [949,18], translation_gist_id: [660, 4]) {
#             language {
#                 id
#                 translation_gist_id
#             }
#         }
#     }
#
#     (this example works)
#     returns:
#    {
#       "update_language": {
#         "language": {
#           "id": [
#             949,
#             18
#           ],
#           "translation_gist_id": [
#             660,
#             4
#           ]
#         }
#       }
#     }
#     """
#     class Arguments:
#         id = LingvodocID(required=True)
#         parent_id = LingvodocID()
#
#     language = graphene.Field(Language)
#     triumph = graphene.Boolean()
#
#     @staticmethod
#     @acl_check_by_id('edit', 'language')
#     def mutate(root, info, **args):
#         id = args.get('id')
#         client_id = id[0]
#         object_id = id[1]
#         dblanguage = DBSession.query(dbLanguage).filter_by(client_id=client_id, object_id=object_id).first()
#
#         if not dblanguage or dblanguage.marked_for_deletion:
#             raise ResponseError(message="Error: No such language in the system")
#         parent_id = args.get('parent_id')
#         if parent_id:
#             dblanguage.parent_client_id = parent_id[0]
#             dblanguage.parent_object_id = parent_id[1]
#
#         translation_gist_id = args.get('translation_gist_id')
#         if translation_gist_id:
#             dblanguage.translation_gist_client_id = translation_gist_id[0]
#             dblanguage.translation_gist_object_id = translation_gist_id[1]
#
#         language = Language(id=[dblanguage.client_id, dblanguage.object_id])
#         language.dbObject = dblanguage
#         return UpdateLanguage(language=language, triumph=True)

def get_child_languages(parent_languages):
    """
    Returns child_langs set
    (Uralic) -> set([UralicObject])
    |       \
    |        \
    (lang_1, lang_2)  -> set([lang_1, lang_2])
    """
    child_langs = set()
    for parent_language in parent_languages:
        for lng_obj in DBSession.query(dbLanguage).filter_by(parent=parent_language, marked_for_deletion=False).all():
            child_langs.add(lng_obj)
    return child_langs

def get_child_lang_list(parent_lang):
    all_languages = set()
    next_childs = set([parent_lang])

    while next_childs:
        next_childs = get_child_languages(next_childs)
        all_languages.update(next_childs)
    return all_languages


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



# from .gql_dictionary import Dictionary
