import graphene
from lingvodoc.schema.gql_holders import (
    IdHolder,
    Name,
    fetch_object
)
from lingvodoc.models import (
    Entity as dbBaseGroup,
)
from lingvodoc.schema.gql_holders import (
    CreatedAt,
)
class BaseGroup(graphene.ObjectType):  # tested
    """
     #created_at          | timestamp without time zone | NOT NULL
     #id                  | bigint                      | NOT NULL
     #dictionary_default  | boolean                     | NOT NULL
     #perspective_default | boolean                     | NOT NULL
     #name                | text                        | NOT NULL
     #subject             | text                        | NOT NULL
     #action              | text                        | NOT NULL

    query myQuery {
      all_basegroups {
        id
        created_at
        action
        name
        subject
        dictionary_default
        perspective_default
      }
    }

    """
    dbType = dbBaseGroup
    dbObject = None

    perspective_default = graphene.Boolean()
    dictionary_default = graphene.Boolean()
    subject = graphene.String()
    action = graphene.String()
    class Meta:
        interfaces = (IdHolder, CreatedAt, Name)

    @fetch_object("perspective_default")
    def resolve_perspective_default(self, info):
        return self.dbObject.perspective_default


    @fetch_object("dictionary_default")
    def resolve_dictionary_default(self, info):
        return self.dbObject.dictionary_default


    @fetch_object("subject")
    def resolve_subject(self, info):
        return self.dbObject.subject


    @fetch_object("action")
    def resolve_action(self, info):
        return self.dbObject.action
