import graphene
from lingvodoc.schema.gql_holders import (
    IdHolder,
    Name,
)
from lingvodoc.models import (
    Entity as dbBaseGroup,
)
from lingvodoc.schema.gql_holders import (
    CreatedAt,
)
class BaseGroup(graphene.ObjectType):
    """
     #created_at          | timestamp without time zone | NOT NULL
     #id                  | bigint                      | NOT NULL
     #dictionary_default  | boolean                     | NOT NULL
     #perspective_default | boolean                     | NOT NULL
     #name                | text                        | NOT NULL
     #subject             | text                        | NOT NULL
     #action              | text                        | NOT NULL
    """
    dbType = dbBaseGroup
    dbObject = None

    perspective_default = graphene.Boolean()
    dictionary_default = graphene.Boolean()
    subject = graphene.String()
    action = graphene.String()
    class Meta:
        interfaces = (IdHolder, CreatedAt, Name)
    pass
