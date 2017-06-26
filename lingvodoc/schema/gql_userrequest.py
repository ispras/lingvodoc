import graphene

from lingvodoc.schema.gql_holders import (
    IdHolder,
    AdditionalMetadata,
    CreatedAt,
    TypeHolder,
    JSONString
)

from lingvodoc.models import (
    UserRequest as dbUserRequest,
)


class UserRequest(graphene.ObjectType): # show only
    """
     #id                  | bigint                      | NOT NULL DEFAULT nextval('userrequest_id_seq'::regclass)
     #sender_id           | bigint                      | NOT NULL
     #recipient_id        | bigint                      | NOT NULL
     #created_at          | timestamp without time zone | NOT NULL
     #broadcast_uuid      | character varying(36)       | NOT NULL
     #type                | character varying(1000)     | NOT NULL
     #message             | character varying(1000)     |
     #subject             | jsonb                       |
     #additional_metadata | jsonb                       |
    """
    dbType = dbUserRequest
    dbObject = None
    sender_id = graphene.Int()
    recipient_id = graphene.Int()
    broadcast_uuid = graphene.String()
    message = graphene.String()
    subject = JSONString()
    class Meta:
        interfaces = (IdHolder, AdditionalMetadata, CreatedAt, TypeHolder)
    pass

    # def data_type(self):
    #     return DBSession.query(TranslationAtom.content).filter_by(
    #     parent_client_id=self.data_type_translation_gist_client_id,
    #     parent_object_id=self.data_type_translation_gist_object_id,
    #     locale_id=2).scalar()