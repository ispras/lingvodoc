import graphene
from sqlalchemy import and_
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
from lingvodoc.views.v2.utils import  add_user_to_group
# from lingvodoc.schema.gql_dictionary import Dictionary


class Language(graphene.ObjectType):
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
    dbObject = None
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
    def create_dblanguage(id=None,
                          parent_id=None,
                          translation_gist_id=None):
        parent = None
        parent_client_id, parent_object_id = parent_id
        client_id, object_id = id
        translation_gist_client_id, translation_gist_object_id = translation_gist_id

        if parent_client_id and parent_object_id:
            parent = DBSession.query(dbLanguage).\
                filter_by(client_id=parent_client_id, object_id=parent_object_id).first()

        dblanguage = dbLanguage(
            client_id=client_id,
            object_id=object_id,
            translation_gist_client_id=translation_gist_client_id,
            translation_gist_object_id=translation_gist_object_id
        )
        DBSession.add(dblanguage)

        if parent:
            dblanguage.parent = parent

        DBSession.flush()
        return dblanguage

    @staticmethod
    @client_id_check()
    #@acl_check_by_id('create', 'language', id_key="parent_id")
    def mutate(root, info, **args):
        id = args.get('id')
        client_id = id[0] if id else info.context["client_id"]
        object_id = id[1] if id else None
        id = [client_id, object_id]
        parent_id = args.get('parent_id')

        tr_atoms = args.get("translation_atoms")
        if type(tr_atoms) is not list:  # TODO: look at this
            translation_gist_id = args.get('translation_gist_id')
            if not translation_gist_id:
                raise ResponseError(message="translation_gist_id arg not found")
            translation_gist_client_id = translation_gist_id[0]
            translation_gist_object_id = translation_gist_id[1]
        else:
            client = DBSession.query(dbClient).filter_by(id=client_id).first()

            user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
            dbtranslationgist = dbTranslationGist(client_id=client_id, object_id=object_id, type="Language")
            translation_gist_client_id = dbtranslationgist.client_id
            translation_gist_object_id = dbtranslationgist.object_id
            DBSession.add(dbtranslationgist)
            DBSession.flush()
            basegroups = list()
            basegroups.append(DBSession.query(dbBaseGroup).filter_by(name="Can delete translationgist").first())
            if not object_id:
                groups = []
                for base in basegroups:
                    group = dbGroup(subject_client_id=translation_gist_client_id, subject_object_id=translation_gist_object_id,
                                  parent=base)
                    groups += [group]
                for group in groups:
                    add_user_to_group(user, group)
            for atom_dict in tr_atoms:
                if "locale_id" in atom_dict and "content" in atom_dict:
                    locale_id = atom_dict["locale_id"]
                    content = atom_dict["content"]
                    dbtranslationatom = dbTranslationAtom(client_id=client_id,
                                                          object_id=object_id,
                                                          parent=dbtranslationgist,
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
                else:
                    raise ResponseError(message="locale_id and content args not found")

        translation_gist_id = [translation_gist_client_id, translation_gist_object_id]
        dblanguage = CreateLanguage.create_dblanguage(id=id,
                                                      parent_id=parent_id,
                                                      translation_gist_id=translation_gist_id)
        language = Language(id=[dblanguage.client_id, dblanguage.object_id])
        language.dbObject = dblanguage
        return CreateLanguage(language=language, triumph=True)


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

    language = graphene.Field(Language)
    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    #@acl_check_by_id('edit', 'language')
    def mutate(root, info, **args):
        id = args.get('id')
        client_id = id[0]
        object_id = id[1]
        dblanguage = DBSession.query(dbLanguage).filter_by(client_id=client_id, object_id=object_id).first()

        if not dblanguage or dblanguage.marked_for_deletion:
            raise ResponseError(message="Error: No such language in the system")
        parent_id = args.get('parent_id')
        if parent_id:
            dblanguage.parent_client_id = parent_id[0]
            dblanguage.parent_object_id = parent_id[1]

        translation_gist_id = args.get('translation_gist_id')
        if translation_gist_id:
            dblanguage.translation_gist_client_id = translation_gist_id[0]
            dblanguage.translation_gist_object_id = translation_gist_id[1]

        language = Language(id=[dblanguage.client_id, dblanguage.object_id])
        language.dbObject = dblanguage
        return UpdateLanguage(language=language, triumph=True)


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
