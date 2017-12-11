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

from lingvodoc.models import (
    Entity as dbEntity,
    Field as dbField,
    PublishingEntity as dbPublishingEntity,
    LexicalEntry as dbLexicalEntry,
    Client,
    DBSession,
    DictionaryPerspective as dbDictionaryPerspective,
    Group as dbGroup,
    LexicalEntry as dbLexicalEntry,
    User as dbUser,
    ObjectTOC as dbObjectTOC
)
from lingvodoc.schema.gql_entity import Entity
from lingvodoc.utils.verification import check_client_id
from lingvodoc.views.v2.delete import real_delete_lexical_entry

from lingvodoc.utils.creation import create_lexicalentry



def have_tag(lex, tags, field_client_id, field_object_id):
    return bool([x for x in lex['contains'] if x['field_client_id'] == field_client_id and x['field_object_id'] == field_object_id and x['content'] in tags and x['published'] and x['accepted']])


def find_lexical_entries_by_tags(tags, field_client_id, field_object_id, accepted):
    result = DBSession.query(LexicalEntry) \
        .join(LexicalEntry.entity) \
        .join(Entity.publishingentity) \
        .join(Entity.field) \
        .filter(dbEntity.content.in_(tags),
                dbEntity.marked_for_deletion == False,
                dbField.client_id == field_client_id,
                dbField.object_id == field_object_id)
    if accepted:
        result = result.filter(dbPublishingEntity.accepted == True)
    result = result.all()
    return result


def find_all_tags(lexical_entry, field_client_id, field_object_id, accepted):
    tag = None
    for entity in lexical_entry.entity:
        if not entity.marked_for_deletion and entity.field_client_id == field_client_id and entity.field_object_id == field_object_id:
            if accepted:
                if not entity.publishingentity.accepted:
                    continue
            tag = entity.content
            break
    if not tag:
        return set()
    else:
        tags = {tag}
        new_tags =  {tag}
        while new_tags:
            lexical_entries = find_lexical_entries_by_tags(new_tags, field_client_id, field_object_id, accepted)
            new_tags = set()
            for lex in lexical_entries:
                entities = DBSession.query(Entity) \
                    .join(Entity.field) \
                    .join(Entity.publishingentity) \
                    .filter(Entity.parent == lex,
                            dbField.client_id == field_client_id,
                            dbField.object_id == field_object_id,
                            Entity.marked_for_deletion==False)
                if accepted:
                    entities = entities.filter(dbPublishingEntity.accepted == True)

                entities = entities.all()
                for entity in entities:
                    if entity.content not in tags:
                        tags.add(entity.content)
                        new_tags.add(entity.content)
        return tags

class LexicalEntry(LingvodocObjectType):
    """
     #created_at          | timestamp without time zone | NOT NULL
     #object_id           | bigint                      | NOT NULL
     #client_id           | bigint                      | NOT NULL
     #parent_object_id    | bigint                      |
     #parent_client_id    | bigint                      |
     #marked_for_deletion | boolean                     | NOT NULL
     #moved_to            | text                        |
     #additional_metadata | jsonb                       |
    """
    entities = graphene.List(Entity)

    dbType = dbLexicalEntry

    class Meta:
        interfaces = (CompositeIdHolder, AdditionalMetadata, CreatedAt, MarkedForDeletion, Relationship, MovedTo)
    @fetch_object('entities')
    @acl_check_by_id('view', 'lexical_entries_and_entities')
    def resolve_entities(self, info):
        result = list()
        for db_entity in self.dbObject.entity:
            gr_entity_object = Entity(id=[db_entity.client_id, db_entity.object_id])
            gr_entity_object.dbObject = db_entity
            result.append(gr_entity_object)
        return result


    @fetch_object('connected_words')
    def resoleve_connected_words(self, info):
        response = list()
        client_id = info.get('client_id')
        object_id = info.get('object_id')
        accepted = info.get('accepted', False)
        if type(accepted) == str and 'false' in accepted.lower():
            accepted = False
        if accepted:
            accepted = True
        published = info.get('published', False)
        if type(published) == str and 'false' in published.lower():
            published = False
        if published:
            published = True
        field_client_id = int(info.get('field_client_id'))
        field_object_id = int(info.get('field_object_id'))
        lexical_entry = DBSession.query(LexicalEntry).filter_by(client_id=client_id, object_id=object_id).first()
        if not lexical_entry or lexical_entry.marked_for_deletion:
            raise ResponseError(message="No such lexical entry in the system")
        tags = find_all_tags(lexical_entry, field_client_id, field_object_id, accepted)
        lexes = find_lexical_entries_by_tags(tags, field_client_id, field_object_id, accepted)
        lexes_composite_list = [(lex.created_at,
                                 lex.client_id, lex.object_id, lex.parent_client_id, lex.parent_object_id,
                                 lex.marked_for_deletion, lex.additional_metadata,
                                 lex.additional_metadata.get('came_from')
                                 if lex.additional_metadata and 'came_from' in lex.additional_metadata else None)
                                for lex in lexes]

        result = LexicalEntry.track_multiple(lexes_composite_list, int(info.context["locale_id"] or 2),
                                             publish=published, accept=accepted)
        if published:
            result = [lex for lex in result if have_tag(lex, tags, field_client_id, field_object_id)]

        response = list(result)
        result = list()
        for le in response:
            le_obj = LexicalEntry(id=[le.client_id, le.object_id])
            le_obj.dbObject = le
            result.append(le_obj)

        return result




class CreateLexicalEntry(graphene.Mutation):
    """
    example:
    mutation {
        create_lexicalentry(id: [949,21], perspective_id: [71,5]) {
            field {
                id
            }
            triumph
        }
    }

    (this example works)
    returns:

    {
      "create_lexicalentry": {
        "field": {
          "id": [
            949,
            21
          ]
        },
        "triumph": true
      }
    }
    """

    class Arguments:
        id = LingvodocID()
        perspective_id = LingvodocID(required=True)

    lexicalentry = graphene.Field(LexicalEntry)
    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):
        perspective_id = args.get('perspective_id')
        id = args.get('id')
        client_id = id[0] if id else info.context["client_id"]
        object_id = id[1] if id else None
        id = [client_id, object_id]
        dblexentry = create_lexicalentry(id, perspective_id, True)
        """
        perspective_client_id = perspective_id[0]
        perspective_object_id = perspective_id[1]

        object_id = None
        client_id_from_args = None
        if len(id) == 1:
            client_id_from_args = id[0]
        elif len(id) == 2:
            client_id_from_args = id[0]
            object_id = id[1]

        client_id = info.context["client_id"]
        client = DBSession.query(Client).filter_by(id=client_id).first()

        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        if not user:
            raise ResponseError(message="This client id is orphaned. Try to logout and then login once more.")

        perspective = DBSession.query(dbDictionaryPerspective). \
            filter_by(client_id=perspective_client_id, object_id=perspective_object_id).first()
        if not perspective:
            raise ResponseError(message="No such perspective in the system")

        if client_id_from_args:
            if check_client_id(authenticated=client.id, client_id=client_id_from_args):
                client_id = client_id_from_args
            else:
                raise ResponseError(message="Error: client_id from another user")

        dblexentry = dbLexicalEntry(object_id=object_id, client_id=client_id,
                               parent_object_id=perspective_object_id, parent=perspective)
        DBSession.add(dblexentry)
        DBSession.flush()
        """
        lexicalentry = LexicalEntry(id=[dblexentry.client_id, dblexentry.object_id])
        lexicalentry.dbObject = dblexentry
        return CreateLexicalEntry(lexicalentry=lexicalentry, triumph=True)

class DeleteLexicalEntry(graphene.Mutation):
    """
    example:
    mutation {
        delete_lexicalentry(id: [949,21]) {
            lexicalentry {
                id
            }
            triumph
        }
    }
    now returns:
      {
      "delete_lexicalentry": {
        "lexicalentry": {
          "id": [
            949,
            21
          ]
        },
        "triumph": true
      }
    }
    """

    class Arguments:
        id = LingvodocID(required=True)

    lexicalentry = graphene.Field(LexicalEntry)
    triumph = graphene.Boolean()

    @staticmethod
    @acl_check_by_id('delete', 'lexical_entries_and_entities', id_key= "parent_id")
    def mutate(root, info, **args):
        id = args.get('id')
        client_id, object_id = id
        dblexicalentry = DBSession.query(dbLexicalEntry).filter_by(client_id=client_id, object_id=object_id).first()
        if dblexicalentry and not dblexicalentry.marked_for_deletion:
            del_object(dblexicalentry)
            objecttoc = DBSession.query(dbObjectTOC).filter_by(client_id=dblexicalentry.client_id,
                                                             object_id=dblexicalentry.object_id).one()
            del_object(objecttoc)
            lexicalentry = LexicalEntry(id=[dblexicalentry.client_id, dblexicalentry.object_id])
            lexicalentry.dbObject = dblexicalentry
            return DeleteLexicalEntry(lexicalentry=lexicalentry, triumph=True)
        raise ResponseError(message="No such entity in the system")

class BulkCreateLexicalEntry(graphene.Mutation):
    class Arguments:
        lexicalentries = graphene.List(ObjectVal)

    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):
        lexicalentries = args.get('lexicalentries')
        lexentries_list = list()
        client = DBSession.query(Client).filter_by(id=info.context["client_id"]).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           info.context["client_id"])
        for lexentry in lexicalentries:
            id = lexentry["id"]

            perspective_id = lexentry["perspective_id"]

            dblexentry = create_lexicalentry(id, perspective_id, False)
            lexentries_list.append(dblexentry)


        DBSession.bulk_save_objects(lexentries_list)
        DBSession.flush()
        return BulkCreateLexicalEntry(triumph=True)