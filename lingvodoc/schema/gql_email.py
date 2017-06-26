import graphene
from lingvodoc.models import (
    Email as dbEmail,

)
from lingvodoc.schema.gql_holders import (
    IdHolder,
    CreatedAt,
    UserId,
)
class Email(graphene.ObjectType):
    """
     #created_at | timestamp without time zone | NOT NULL
     #id         | bigint                      | NOT NULL DEFAULT nextval('email_id_seq'::regclass)
     #user_id    | bigint                      | NOT NULL
     #email      | text                        |
    """
    dbType = dbEmail
    dbObject = None

    email = graphene.String()

    class Meta:
        interfaces = (CreatedAt,
                      IdHolder,
                      UserId
                    )
    pass