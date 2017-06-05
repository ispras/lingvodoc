from lingvodoc.scripts.restore_entities_fields.models import DBSession
from lingvodoc.scripts.restore_entities_fields.old_models import DBSession as old_DBSession
from sqlalchemy import func
import json
# from lingvodoc.scripts.restore_entities_fields.models import (
#     Locale,
#     User,
#     Client,
#     UserBlobs,
#     BaseGroup,
#     Group,
#     Language,
#     Dictionary,
#     DictionaryPerspective,
#     TranslationGist,
#     TranslationAtom,
#     Email,
#     Passhash,
#     Field,
#     DictionaryPerspectiveToField,
#     LexicalEntry,
#     Entity,
#     PublishingEntity
# )
from lingvodoc.scripts.restore_entities_fields.old_models import (
    Locale as old_Locale,
    User as old_User,
    Client as old_Client,
    UserBlobs as old_UserBlobs,
    BaseGroup as old_BaseGroup,
    Group as old_Group,
    Language as old_Language,
    Dictionary as old_Dictionary,
    DictionaryPerspective as old_DictionaryPerspective,
    Email as old_Email,
    Passhash as old_Passhash,
    LexicalEntry as old_LexicalEntry,
    Entity as old_Entity
)


if __name__ == "__main__":
    entities = list()
    for entity in old_DBSession.query(old_Entity).join(old_LexicalEntry).filter(old_LexicalEntry.parent_client_id == 671,
                                                                                old_LexicalEntry.parent_object_id == 10419,
                                                                                old_Entity.field_client_id == 671,
                                                                                old_Entity.field_object_id == 16073).all():
        entity_tuple = (entity.client_id, entity.object_id)
        entities.append(entity_tuple)
    print(entities)

    entities = list()
    for entity in old_DBSession.query(old_Entity).join(old_LexicalEntry).filter(old_LexicalEntry.parent_client_id == 671,
                                                                                old_LexicalEntry.parent_object_id == 12797,
                                                                                old_Entity.field_client_id == 671,
                                                                                old_Entity.field_object_id == 16073).all():
        entity_tuple = (entity.client_id, entity.object_id)
        entities.append(entity_tuple)
    print(entities)

    entities = list()
    for entity in old_DBSession.query(old_Entity).join(old_LexicalEntry).filter(old_LexicalEntry.parent_client_id == 748,
                                                                                old_LexicalEntry.parent_object_id == 1802,
                                                                                old_Entity.field_client_id == 671,
                                                                                old_Entity.field_object_id == 16067).all():
        entity_tuple = (entity.client_id, entity.object_id)
        entities.append(entity_tuple)
    print(entities)