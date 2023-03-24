import graphene

from lingvodoc.schema.gql_holders import (
    LingvodocObjectType,
    CompositeIdHolder,
    AdditionalMetadata,
    CreatedAt,
    MarkedForDeletion,
    Relationship,
    MovedTo,
    fetch_object,
    client_id_check,
    del_object,
    acl_check_by_id,
    ResponseError,
    LingvodocID,
    ObjectVal
)
from lingvodoc.cache.caching import TaskStatus


class Task(LingvodocObjectType):
    """
     #created_at          | timestamp without time zone | NOT NULL
     #id                  | bigint                      | NOT NULL DEFAULT nextval('organization_id_seq'::regclass)
     #marked_for_deletion | boolean                     | NOT NULL
     #name                | text                        |
     #about               | text                        |
     #additional_metadata | jsonb                       |
    """
    dbType = None
    id = graphene.String()
    key = graphene.String()
    progress = graphene.Int()
    result_link_list = graphene.List(graphene.String)
    status = graphene.String()
    task_details = graphene.String()
    task_family = graphene.String()
    total_stages = graphene.Int()
    current_stage = graphene.Int()
    user_id = graphene.String()

    def resolve_user_id(self, info):
        return int(self.user_id)


class DeleteTask(graphene.Mutation):
    """
    example:
    mutation {
        create_user( login: "new", email: "n@mail.ru", name: "Новое имя", birthday: [1, 1, 1970], password: "secret") {
             field {
                login
                id
            }
            triumph
        }
    }

    (this example works)
    returns:

    {
      "create_user": {
        "field": {
          "login": "new",
          "id": 70
        },
        "triumph": true
      }
    }
    """
    class Arguments:
        task_id = graphene.String(required=True)

    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):
        task_id = args.get('task_id')
        task_key = "task:" + task_id
        task = TaskStatus.get_from_cache(task_key)
        if task:
            task.delete()
            return DeleteTask(triumph=True)
