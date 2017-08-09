import graphene

from lingvodoc.models import (
    Dictionary as dbDictionary,
    TranslationAtom as dbTranslationAtom,
    TranslationGist as dbTranslationGist,
    DBSession,
    Client as dbClient,
    Language as dbLanguage,
    User as dbUser
)
from lingvodoc.schema.gql_user import User

"""
from lingvodoc.views.v2.views import (
    translation_service_search
)
"""

from lingvodoc.views.v2.translations import translationgist_contents

# from lingvodoc.schema.gql_language import Language


def translation_service_search(searchstring):
    translationatom = DBSession.query(dbTranslationAtom)\
        .join(dbTranslationGist).\
        filter(dbTranslationAtom.content == searchstring,
               dbTranslationAtom.locale_id == 2,
               dbTranslationGist.type == 'Service')\
        .order_by(dbTranslationAtom.client_id)\
        .first()
    response = translationgist_contents(translationatom.parent)
    return response

from lingvodoc.schema.gql_holders import (
    CommonFieldsComposite,
    StateHolder,
    fetch_object,
    del_object
)

from lingvodoc.views.v2.delete import real_delete_dictionary
from lingvodoc.views.v2.utils import (
    check_client_id
)


class Dictionary(graphene.ObjectType):
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
    """
    dbType = dbDictionary
    dbObject = None
    category = graphene.Int()
    domain = graphene.Int()
    # parent_object_id
    # translation_gist_client_id
    # state_translation_gist_client_id
    status = graphene.String()

    translation = graphene.String()
    dataType = graphene.String()

    class Meta:
        interfaces = (CommonFieldsComposite, StateHolder)

    def resolve_dataType(self, args, context, info):
        return 'dictionary'

    @fetch_object('translation')
    def resolve_translation(self, args, context, info):
        # return dbdict.get_translation(2)
        return self.dbObject.get_translation(context.get('locale_id'))

    @fetch_object('status')
    def resolve_status(self, args, context, info):
        atom = DBSession.query(dbTranslationAtom).filter_by(
            parent_client_id=self.dbObject.state_translation_gist_client_id,
            parent_object_id=self.dbObject.state_translation_gist_object_id,
            locale_id=int(context.get('locale_id'))).first()
        if atom:
            return atom.content
        else:
            return None

    @fetch_object()
    def resolve_created_at(self, args, context, info):
        return self.dbObject.created_at


class CreateDictionary(graphene.Mutation):


    """
    example:
    mutation  {
        create_dictionary(id: [ 742, 5494], translation_gist_id: [662, 2], parent_id: [1, 47], additional_metadata: "some data") {
            status
        }
    }
    """


    class Input:
        id = graphene.List(graphene.Int)
        translation_gist_id = graphene.List(graphene.Int)
        client_id = graphene.Int()
        parent_id = graphene.List(graphene.Int)
        additional_metadata = graphene.String()


    field = graphene.Field(lambda: Language)
    status = graphene.Boolean()


    @staticmethod
    def mutate(root, args, context, info):
        parent_id = args.get('parent_id')
        parent_client_id = parent_id[0]
        parent_object_id = parent_id[1]

        translation_gist_id = args.get('translation_gist_id')
        translation_gist_client_id = translation_gist_id[0]
        translation_gist_object_id = translation_gist_id[1]

        id = args.get('id')
        client_id = id[0]
        # client_id = context["client_id"]

        object_id = id[1]
        # object_id = context["object_id"]
        # object_id = args.get('object_id')
        if not object_id:
            object_id = None

        client = DBSession.query(dbClient).filter_by(id=client_id).first()
        if not client:
            return ResponseError(
                message="Error: Invalid client id (not registered on server). Try to logout and then login.")

        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        if not user:
            return ResponseError(message="Error: This client id is orphaned. Try to logout and then login once more.")

        client_id_from_args = args.get('client_id')
        if client_id_from_args:
            if check_client_id(authenticated=client.id, client_id=client_id_from_args):
                client_id = client_id_from_args
            else:
                return ResponseError(message="Error: client_id from another user")

        parent = DBSession.query(dbLanguage).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()

        additional_metadata = args.get('additional_metadata')
        if not additional_metadata:
            additional_metadata = None

        """
    
    
        subreq = Request.blank('/translation_service_search')
        subreq.method = 'POST'
        subreq.headers = request.headers
        subreq.json = {"searchstring": "WiP"}
        headers = {'Cookie': request.headers['Cookie']}
        subreq.headers = headers
    
        resp = request.invoke_subrequest(subreq)
        # set_trace()
        if 'error' not in resp.json:
            state_translation_gist_object_id, state_translation_gist_client_id = resp.json['object_id'], resp.json['client_id']
        else:
            raise KeyError("Something wrong with the base", resp.json['error'])
        """

        dbentityobj = dbDictionary(client_id=client_id,
                                   object_id=object_id,
                                   state_translation_gist_object_id=None,
                                   state_translation_gist_client_id=None,
                                   parent=parent,
                                   translation_gist_client_id=translation_gist_client_id,
                                   translation_gist_object_id=translation_gist_object_id)

        dictionary = Dictionary(id=[dbentityobj.client_id, dbentityobj.object_id])
        dictionary.dbObject = dbentityobj
        #context = {}
        #context.locale_id = 2
        searchstring = {"searchstring": "WiP"}
        response = translation_service_search(searchstring)
        # response = dictionary.resolve_status(dictionary, args, context, info)
        dbentityobj.state_translation_gist_client_id = response.state_translation_gist_client
        dbentityobj.state_translation_gist_object_id = response.state_translation_gist_object

        DBSession.flush()
        return CreateDictionary(field=dictionary, status=True)


class UpdateDictionary(graphene.Mutation):
    class Input:
        translation_gist_id = graphene.List(graphene.Int)
        parent_id = graphene.List(graphene.Int)
        additional_metadata = graphene.String()

    field = graphene.Field(User)
    status = graphene.Boolean()

    @staticmethod
    def mutate(root, args, context, info):
        client_id = context["client_id"]
        object_id = context["object_id"]

        client = DBSession.query(dbClient).filter_by(id=request.authenticated_userid).first()
        if not client:
            return ResponseError(
                message="Error: Invalid client id (not registered on server). Try to logout and then login.")

            dbentityobj = DBSession.query(dbDictionary).filter_by(client_id=client_id, object_id=object_id).first()
        if dbentityobj:
            if not dbentityobj.marked_for_deletion:

                parent_id = args.get('parent_id')
                parent_client_id = parent_id[0]
                parent_object_id = parent_id[1]
                if parent_client_id:
                    dbentityobj.parent_client_id = parent_client_id
                if parent_object_id:
                    dbentityobj.parent_object_id = parent_object_id

                translation_gist_id = args.get('translation_gist_id')
                translation_gist_client_id = translation_gist_id[0]
                translation_gist_object_id = translation_gist_id[1]
                if translation_gist_client_id:
                    dbentityobj.translation_gist_client_id = translation_gist_client_id
                if translation_gist_object_id:
                    dbentityobj.translation_gist_object_id = translation_gist_object_id

                additional_metadata = args.get('additional_metadata')
                if additional_metadata:
                    old_meta = dbentityobj.additional_metadata
                    old_meta.update(additional_metadata)
                    dbentityobj.additional_metadata = old_meta

                dictionary = Dictionary(id=[dbentityobj.client_id, dbentityobj.object_id])
                dictionary.dbObject = dbentityobj
                return UpdateDictionary(field=dictionary, status=True)
        return ResponseError(message="Error: No such dictionary in the system")


class DeleteDictionary(graphene.Mutation):
    class Input:
        id = graphene.List(graphene.Int)

    field = graphene.Field(lambda: Language)
    status = graphene.Boolean()

    @staticmethod
    def mutate(root, args, context, info):
        id = args.get('id')

        client_id = id[0]
        object_id = id[1]
        dbentityobj = DBSession.query(dbDictionary).filter_by(client_id=client_id, object_id=object_id).first()

        if dbentityobj and not dbentityobj.marked_for_deletion:
            dbentityobj = dbentityobj.parent

            del_object(dbentityobj)
            dictionary = Dictionary(id=id)
            dictionary.dbObject = dbentityobj
            return DeleteDictionary(field=dbentityobj, status=True)
        return ResponseError(message="No such entity in the system")


from .gql_language import Language