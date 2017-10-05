from lingvodoc.models import (
    Client,
    DBSession,
    Dictionary,

    TranslationAtom,
    TranslationGist,
    User,
    Group,
    BaseGroup,
    DictionaryPerspective
)

from lingvodoc.views.v2.utils import add_user_to_group
from lingvodoc.schema.gql_holders import ResponseError
from lingvodoc.views.v2.translations import translationgist_contents

def translation_service_search(searchstring):
    translationatom = DBSession.query(TranslationAtom)\
        .join(TranslationGist).\
        filter(TranslationAtom.content == searchstring,
               TranslationAtom.locale_id == 2,
               TranslationGist.type == 'Service')\
        .order_by(TranslationAtom.client_id)\
        .first()
    response = translationgist_contents(translationatom.parent)
    return response

def create_perspective(client_id=None,
                       object_id=None,
                       parent_client_id=None,
                       parent_object_id=None,
                       translation_gist_client_id=None,
                       translation_gist_object_id=None,
                       latitude=None,
                       longitude=None,
                       additional_metadata=None,
                       import_source=None,
                       import_hash=None
                       ):
    parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    if not parent:
        raise ResponseError(message="No such dictionary in the system")
    coord = {}

    if latitude:
        coord['latitude'] = latitude
    if longitude:
        coord['longitude'] = longitude

    if additional_metadata:
        additional_metadata.update(coord)
    else:
        additional_metadata = coord

    resp = translation_service_search("WiP")
    state_translation_gist_object_id, state_translation_gist_client_id = resp['object_id'], resp['client_id']

    dbperspective = DictionaryPerspective(client_id=client_id,
                                  object_id=object_id,
                                  state_translation_gist_object_id=state_translation_gist_object_id,
                                  state_translation_gist_client_id=state_translation_gist_client_id,
                                  parent=parent,
                                  import_source=import_source,
                                  import_hash=import_hash,
                                  additional_metadata=additional_metadata,
                                  translation_gist_client_id=translation_gist_client_id,
                                  translation_gist_object_id=translation_gist_object_id
                                  )
    DBSession.add(dbperspective)
    DBSession.flush()
    owner_client = DBSession.query(Client).filter_by(id=parent.client_id).first()
    owner = owner_client.user
    if not object_id:
        for base in DBSession.query(BaseGroup).filter_by(perspective_default=True):
            client = DBSession.query(Client).filter_by(id=client_id).first()
            user = DBSession.query(User).filter_by(id=client.user_id).first()
            new_group = Group(parent=base,
                                subject_object_id=dbperspective.object_id,
                                subject_client_id=dbperspective.client_id)
            add_user_to_group(user, new_group)
            add_user_to_group(owner, new_group)
            DBSession.add(new_group)
            DBSession.flush()
    return dbperspective