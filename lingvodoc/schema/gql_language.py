import graphene
from lingvodoc.models import (
    Language as dbLanguage,
    Dictionary as dbDictionary,
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
from .gql_dictionary import Dictionary
from lingvodoc.utils.creation import (
    create_dblanguage,
    create_gists_with_atoms,
    add_user_to_group)
# from lingvodoc.schema.gql_dictionary import Dictionary
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import (
    func,
    or_,
    and_,
    tuple_,
    not_
)


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
    dictionaries = graphene.List(Dictionary)

    dataType = graphene.String()

    class Meta:
        interfaces = (CommonFieldsComposite, TranslationHolder)

    @fetch_object()
    def resolve_dictionaries(self, info):
        result = list()
        for dictionary in DBSession.query(dbDictionary).filter(
                and_(dbDictionary.parent_object_id == self.dbObject.object_id,
                     dbDictionary.parent_client_id == self.dbObject.client_id)):
            result.append(Dictionary(id=[dictionary.client_id, dictionary.object_id]))
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
        locale_exist = graphene.Boolean()
        translation_atoms = graphene.List(ObjectVal)

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

        translation_gist_id = args.get("translation_gist_id")
        translation_atoms = args.get("translation_atoms")
        translation_gist_id = create_gists_with_atoms(
                              translation_atoms,
                              translation_gist_id,
                              [client_id,object_id]
                              )
        dblanguage = create_dblanguage(id=id,
                                                      parent_id=parent_id,
                                                      translation_gist_id=translation_gist_id)
        language = Language(id=[dblanguage.client_id, dblanguage.object_id])
        language.dbObject = dblanguage
        return CreateLanguage(language=language, triumph=True)


def move_language(language, parent_id, previous_sibling):
    previous = None
    if previous_sibling:
        previous = DBSession.query(dbLanguage).filter(dbLanguage.client_id == previous_sibling[0],
                                           dbLanguage.object_id == previous_sibling[1]).first()
        if not previous:
            raise ResponseError(message='no such previous sibling')
        if [previous.parent_client_id, previous.parent_object_id] != parent_id:
            raise ResponseError(message='no such pair of this parent/previous_sibling')
    ids = [language.client_id, language.object_id]
    ids = str(ids)
    older_siblings = DBSession.query(dbLanguage).filter(dbLanguage.parent_client_id == language.parent_client_id,
                                       dbLanguage.parent_object_id == language.parent_object_id,
                                       dbLanguage.additional_metadata['younger_siblings'].contains(
                                           [ids])).all()
    for lang in older_siblings:
        lang.additional_metadata['younger_siblings'].remove([dbLanguage.client_id, dbLanguage.object_id])
        flag_modified(lang, 'additional_metadata')
    language.parent_client_id = parent_id[0]
    language.parent_object_id = parent_id[1]
    older_siblings = DBSession.query(dbLanguage).filter(dbLanguage.parent_client_id == language.parent_client_id,
                                                        dbLanguage.parent_object_id == language.parent_object_id,
                                                        or_(dbLanguage.client_id != language.client_id, dbLanguage.object_id != language.object_id))
    if previous:
        ids = str(previous_sibling)
        older_siblings = older_siblings.filter(dbLanguage.additional_metadata['younger_siblings'].contains(
                                               [ids]))
    older_siblings = older_siblings.all()
    flag_modified(language, 'additional_metadata')
    if previous:
        new_meta = list(previous.additional_metadata['younger_siblings'])
    else:
        new_meta = []
    for lang in older_siblings:
        siblings = lang.additional_metadata['younger_siblings']
        index = siblings.index(previous_sibling)
        lang.additional_metadata['younger_siblings'].insert(index, [dbLanguage.client_id, dbLanguage.object_id])
        flag_modified(lang, 'additional_metadata')





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

        if parent_id or previous_sibling:
            move_language(dblanguage, parent_id, previous_sibling)
            # dblanguage.parent_client_id = parent_id[0]
            # dblanguage.parent_object_id = parent_id[1]

        translation_gist_id = args.get('translation_gist_id')
        if translation_gist_id:
            dblanguage.translation_gist_client_id = translation_gist_id[0]
            dblanguage.translation_gist_object_id = translation_gist_id[1]

        language = Language(id=[dblanguage.client_id, dblanguage.object_id])
        language.dbObject = dblanguage
        return UpdateLanguage(language=language, triumph=True)


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
            # dbentryobj = dbentityobj.parent - ?
        del_object(dblanguageobj)
        language = Language(id=id)
        language.dbObject = dblanguageobj
        return DeleteLanguage(language=language, triumph=True)



# from .gql_dictionary import Dictionary
