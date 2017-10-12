from lingvodoc.models import (
    Client,
    DBSession,
    Dictionary,
    TranslationAtom,
    TranslationGist,
    User,
    Group,
    BaseGroup,
    DictionaryPerspective,
    Language,
    DictionaryPerspectiveToField,
    LexicalEntry,
    Entity,
    Field
)

from lingvodoc.views.v2.utils import add_user_to_group
from lingvodoc.schema.gql_holders import ResponseError
from lingvodoc.views.v2.translations import translationgist_contents

from sqlalchemy import (
    and_,
)

from lingvodoc.views.v2.utils import (
     create_object
)

import base64
import hashlib



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

def create_perspective(id = (None, None),
                       parent_id=None,
                       translation_gist_id=(None, None),
                       latitude=None,
                       longitude=None,
                       additional_metadata=None,
                       import_source=None,
                       import_hash=None
                       ):
    client_id, object_id = id
    parent_client_id, parent_object_id = parent_id
    translation_gist_client_id, translation_gist_object_id = translation_gist_id

    parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    if not parent:
        raise ResponseError(message="No such dictionary in the system")
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


def create_dbdictionary(id=None,
                        parent_id=None,
                        translation_gist_id=None,
                        additional_metadata=None):
    client_id, object_id = id
    parent_client_id, parent_object_id = parent_id
    translation_gist_client_id, translation_gist_object_id = translation_gist_id

    duplicate_check = DBSession.query(Dictionary).filter_by(client_id=client_id, object_id=object_id).all()
    if duplicate_check:
        raise ResponseError(message="Dictionary with such ID already exists in the system")
    parent = DBSession.query(Language).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    resp = translation_service_search("WiP")
    state_translation_gist_object_id, state_translation_gist_client_id = resp['object_id'], resp['client_id']
    dbdictionary_obj = Dictionary(client_id=client_id,
                                    object_id=object_id,
                                    state_translation_gist_object_id=state_translation_gist_object_id,
                                    state_translation_gist_client_id=state_translation_gist_client_id,
                                    parent=parent,
                                    translation_gist_client_id=translation_gist_client_id,
                                    translation_gist_object_id=translation_gist_object_id,
                                    additional_metadata=additional_metadata
                                    )

    client = DBSession.query(Client).filter_by(id=client_id).first()
    user = client.user
    for base in DBSession.query(BaseGroup).filter_by(dictionary_default=True):
        new_group = Group(parent=base,
                          subject_object_id=dbdictionary_obj.object_id,
                          subject_client_id=dbdictionary_obj.client_id)
        if user not in new_group.users:
            new_group.users.append(user)
        DBSession.add(new_group)
        DBSession.flush()
    return dbdictionary_obj

def create_dictionary_persp_to_field(id=None,
                                     parent_id=None,
                                     field_id=None,
                                     self_id=None,
                                     link_id=None,
                                     upper_level=None,
                                     position=1):

    client_id, object_id = id if id else (None,None)
    parent_client_id, parent_object_id = parent_id if parent_id else (None,None)
    field_client_id, field_object_id = field_id if field_id else  (None,None)
    self_client_id, self_object_id = self_id if self_id else (None,None)
    link_client_id, link_object_id = link_id if link_id else (None,None)

    if DBSession.query(DictionaryPerspectiveToField).filter_by(client_id=client_id,
                                                                 object_id=object_id).first():
        raise ResponseError(message="This field already exists")
    if upper_level:
            field_object = DictionaryPerspectiveToField(client_id=client_id,
                                                  object_id=object_id,
                                                  parent_client_id=parent_client_id,
                                                  parent_object_id=parent_object_id,
                                                  field_client_id=field_client_id,
                                                  field_object_id=field_object_id,
                                                  self_client_id=self_client_id,
                                                  self_object_id=self_object_id,
                                                  link_client_id=link_client_id,
                                                  link_object_id=link_object_id,
                                                  position=position
                                                  )
    else:
        field_object = DictionaryPerspectiveToField(client_id=client_id,
                                                      object_id=object_id,
                                                      parent_client_id=parent_client_id,
                                                      parent_object_id=parent_object_id,
                                                      field_client_id=field_client_id,
                                                      field_object_id=field_object_id,
                                                      self_client_id=self_client_id,
                                                      self_object_id=self_object_id,
                                                      link_client_id=link_client_id,
                                                      link_object_id=link_object_id,
                                                      position=position
                                                      )
    DBSession.add(field_object)
    DBSession.flush()
    return field_object

def create_entity(id=None,
        parent_id=None,
        additional_metadata=None,
        field_id=None,
        self_id=None,
        link_id=None,
        locale_id=2,
        filename=None,
        content=None,
        registry=None,
        request=None,
        save_object=False):

    parent_client_id, parent_object_id = parent_id
    parent = DBSession.query(LexicalEntry).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    if not parent:
        raise ResponseError(message="No such lexical entry in the system")

    upper_level = None

    field_client_id, field_object_id = field_id
    tr_atom = DBSession.query(TranslationAtom).join(TranslationGist, and_(
        TranslationAtom.locale_id == 2,
        TranslationAtom.parent_client_id == TranslationGist.client_id,
        TranslationAtom.parent_object_id == TranslationGist.object_id)).join(Field, and_(
        TranslationGist.client_id == Field.data_type_translation_gist_client_id,
        TranslationGist.object_id == Field.data_type_translation_gist_object_id)).filter(
        Field.client_id == field_client_id, Field.object_id == field_object_id).first()
    if not tr_atom:
        raise ResponseError(message="No such field in the system")
    data_type = tr_atom.content.lower()

    if self_id:
        self_client_id, self_object_id = self_id
        upper_level = DBSession.query(Entity).filter_by(client_id=self_client_id,
                                                          object_id=self_object_id).first()
        if not upper_level:
            raise ResponseError(message="No such upper level in the system")

    client_id, object_id = id
    dbentity = Entity(client_id=client_id,
                        object_id=object_id,
                        field_client_id=field_client_id,
                        field_object_id=field_object_id,
                        locale_id=locale_id,
                        additional_metadata=additional_metadata,
                        parent=parent)
    group = DBSession.query(Group).join(BaseGroup).filter(BaseGroup.subject == 'lexical_entries_and_entities',
                                                              Group.subject_client_id == dbentity.parent.parent.client_id,
                                                              Group.subject_object_id == dbentity.parent.parent.object_id,
                                                              BaseGroup.action == 'create').one()

    override_group = DBSession.query(Group).join(BaseGroup).filter(
        BaseGroup.subject == 'lexical_entries_and_entities',
        Group.subject_override == True,
        BaseGroup.action == 'create').one()
    # if user in group.users or user in override_group.users:
    #    dbentity.publishingentity.accepted = True
    if upper_level:
        dbentity.upper_level = upper_level
    dbentity.publishingentity.accepted = True
    real_location = None
    url = None

    if data_type == 'image' or data_type == 'sound' or 'markup' in data_type:
        blob = request.POST.pop("blob")
        filename = blob.filename
        content = blob.file.read()
        # filename=
        real_location, url = create_object(base64.urlsafe_b64encode(content).decode(), dbentity, data_type, filename,
                                           "graphql_files", request.registry.settings["storage"])
        dbentity.content = url
        old_meta = dbentity.additional_metadata
        need_hash = True
        if old_meta:
            if old_meta.get('hash'):
                need_hash = False
        if need_hash:
            hash = hashlib.sha224(base64.urlsafe_b64decode(base64.urlsafe_b64encode(content).decode())).hexdigest()
            hash_dict = {'hash': hash}
            if old_meta:
                old_meta.update(hash_dict)
            else:
                old_meta = hash_dict
            dbentity.additional_metadata = old_meta
        if 'markup' in data_type:
            name = filename.split('.')
            ext = name[len(name) - 1]
            if ext.lower() == 'textgrid':
                data_type = 'praat markup'
            elif ext.lower() == 'eaf':
                data_type = 'elan markup'
        dbentity.additional_metadata['data_type'] = data_type
    elif data_type == 'link':
        if link_id:
            link_client_id, link_object_id = link_id
            dbentity.link_client_id = link_client_id
            dbentity.link_object_id = link_object_id
        else:
            raise ResponseError(
                message="The field is of link type. You should provide client_id and object id in the content")
    else:
        dbentity.content = content

    if save_object:
        DBSession.add(dbentity)
        DBSession.flush()
    return dbentity

def create_lexicalentry(id, perspective_id, save_object=False):
    client_id, object_id = id
    perspective_client_id, perspective_object_id = perspective_id

    perspective = DBSession.query(DictionaryPerspective). \
        filter_by(client_id=perspective_client_id, object_id=perspective_object_id).first()
    if not perspective:
        raise ResponseError(message="No such perspective in the system")

    dblexentry = LexicalEntry(object_id=object_id, client_id=client_id,
                                parent_object_id=perspective_object_id, parent=perspective)
    if save_object:
        DBSession.add(dblexentry)
        DBSession.flush()
    return dblexentry
