import graphene

from lingvodoc.schema.gql_holders import (
    LingvodocObjectType,
    CompositeIdHolder,
    CreatedAt,
    MarkedForDeletion,
    TypeHolder,
    client_id_check,
    acl_check_by_id,
    ResponseError,
    fetch_object,
    LingvodocID,
    TranslationHolder,
    del_object
)

from lingvodoc.models import (
    TranslationAtom as dbTranslationAtom,
    TranslationGist as dbTranslationGist,
    Client,
    User as dbUser,
    BaseGroup as dbBaseGroup,
    Group as dbGroup,
    DBSession,
)
from lingvodoc.utils.creation import add_user_to_group
from lingvodoc.utils.verification import check_client_id
from lingvodoc.schema.gql_translationatom import TranslationAtom

class TranslationGist(LingvodocObjectType):
    """
     #created_at          | timestamp without time zone | NOT NULL
     #object_id           | bigint                      | NOT NULL
     #client_id           | bigint                      | NOT NULL
     #marked_for_deletion | boolean                     | NOT NULL
     #type                | text                        |

     {"variables": {}, "query": "query QUERYNAME { translationgist(id:[578, 6]){id created_at}}"   }

    """
    dbType = dbTranslationGist

    translationatoms = (
        graphene.List(TranslationAtom, deleted = graphene.Boolean()))

    class Meta:
        interfaces = (CompositeIdHolder,
                      CreatedAt,
                      MarkedForDeletion,
                      TypeHolder,
                        TranslationHolder
                      )

    @fetch_object("translationatoms")
    def resolve_translationatoms(self, info, deleted = None):

        query = (

            DBSession

                .query(dbTranslationAtom)

                .filter_by(
                    parent_client_id = self.dbObject.client_id,
                    parent_object_id = self.dbObject.object_id))

        if deleted is not None:

            query = (

                query.filter(
                    dbTranslationAtom.marked_for_deletion == deleted))

        result = list()

        for dbatom in query.all():

            atom = TranslationAtom(id=[dbatom.client_id, dbatom.object_id])
            atom.dbObject = dbatom

            result.append(atom)

        return result


class CreateTranslationGist(graphene.Mutation):
    """
    example:
    mutation {
        create_translationgist(id: [949,22], type: "some type") {
            translationgist {
                id
                type
            }
            triumph
        }
    }
    (this example works)
    returns:
    {
        "data": {
            "create_translationgist": {
                "translationgist": {
                    "id": [
                        1197,
                        206
                    ],
                    "type": "some type"
                },
                "triumph": true
            }
        }
    }
    """

    class Arguments:
        id = LingvodocID()
        type = graphene.String(required=True)

    translationgist = graphene.Field(TranslationGist)
    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):
        type = args.get('type')
        id = args.get('id')
        client_id = id[0] if id else info.context["client_id"]
        object_id = id[1] if id else None
        client = DBSession.query(Client).filter_by(id=client_id).first()
        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        dbtranslationgist = dbTranslationGist(client_id=client_id, object_id=object_id, type=type)
        DBSession.add(dbtranslationgist)
        DBSession.flush()
        basegroups = list()
        basegroups.append(DBSession.query(dbBaseGroup).filter_by(name="Can delete translationgist").first())
        if not object_id:
            groups = []
            for base in basegroups:
                group = dbGroup(subject_client_id=dbtranslationgist.client_id, subject_object_id=dbtranslationgist.object_id,
                              parent=base)
                groups += [group]
            for group in groups:
                add_user_to_group(user, group)

        translationgist = TranslationGist(id=[dbtranslationgist.client_id, dbtranslationgist.object_id])
        translationgist.dbObject = dbtranslationgist
        return CreateTranslationGist(translationgist=translationgist, triumph=True)


class DeleteTranslationGist(graphene.Mutation):
    """
    example:
    mutation {
        delete_translationgist(id: [949,22]) {
            translationgist {
                id
            }
            triumph
        }
    }

    now returns:
    {
      "delete_translationgist": {
        "translationgist": {
          "id": [
            949,
            22
          ]
        },
        "triumph": true
      }
    }
    """

    class Arguments:
        id = LingvodocID(required=True)

    translationgist = graphene.Field(TranslationGist)
    triumph = graphene.Boolean()

    @staticmethod
    @acl_check_by_id('delete', 'translations')
    def mutate(root, info, **args):
        id = args.get('id')
        client_id, object_id= id
        dbtranslationgist = DBSession.query(dbTranslationGist).filter_by(client_id=client_id, object_id=object_id).first()
        if not dbtranslationgist or dbtranslationgist.marked_for_deletion:
            raise ResponseError(message="No such translationgist in the system")
        del_object(dbtranslationgist, "delete_translationgist", info.context.get('client_id'))
        translationgist = TranslationGist(id=[dbtranslationgist.client_id, dbtranslationgist.object_id])
        translationgist.dbObject = dbtranslationgist
        return DeleteTranslationGist(translationgist=translationgist, triumph=True)


class TranslationGistInterface(graphene.Interface):
    """
    Interface for querying translation gist with all its translations.

    Why not in gql_holders? Because TranslationGist itself uses interfaces from there, can't have cyclic
    dependency.
    """

    translation_gist = graphene.Field(TranslationGist)

    @fetch_object("translation_gist")
    def resolve_translation_gist(self, info):

        db_translation_gist = DBSession.query(dbTranslationGist).filter_by(
            client_id = self.dbObject.translation_gist_client_id,
            object_id = self.dbObject.translation_gist_object_id).first()

        translation_gist = TranslationGist(id =
            [db_translation_gist.client_id, db_translation_gist.object_id])

        translation_gist.dbObject = db_translation_gist

        return translation_gist

