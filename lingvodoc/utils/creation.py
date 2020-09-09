import base64
import hashlib
import os
import shutil
import tempfile
import time
import random
import string
import urllib

import transaction
from pathvalidate import sanitize_filename
from sqlalchemy import (
    and_, create_engine,
)
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import or_

from lingvodoc.cache.caching import TaskStatus
from lingvodoc.queue.celery import celery
from lingvodoc.utils.elan_functions import eaf_wordlist
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
    Field,
    PublishingEntity,
    Organization as dbOrganization, Parser, ParserResult,
    get_client_counter
)
from lingvodoc.schema.gql_holders import ResponseError
from lingvodoc.utils.search import translation_gist_search


import logging
log = logging.getLogger(__name__)

import lingvodoc.utils.parser as ParseMethods

def add_user_to_group(user, group):
    if user not in group.users:
        group.users.append(user)


def create_perspective(id = (None, None),
                       parent_id=None,
                       translation_gist_id=(None, None),
                       latitude=None,
                       longitude=None,
                       additional_metadata=None,
                       import_source=None,
                       import_hash=None,
                       is_template=False,
                       add_group=False
                       ):
    client_id, object_id = id

    if not parent_id:
        raise ResponseError(message="Bad parent ids")
    parent_client_id, parent_object_id = parent_id
    translation_gist_client_id, translation_gist_object_id = translation_gist_id if translation_gist_id else (None, None)

    parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    if not parent:
        raise ResponseError(message="No such dictionary in the system")
    resp = translation_gist_search("WiP")
    state_translation_gist_object_id, state_translation_gist_client_id = resp.object_id, resp.client_id

    dbperspective = DictionaryPerspective(client_id=client_id,
                                  object_id=object_id,
                                  state_translation_gist_object_id=state_translation_gist_object_id,
                                  state_translation_gist_client_id=state_translation_gist_client_id,
                                  parent=parent,
                                  import_source=import_source,
                                  import_hash=import_hash,
                                  additional_metadata=additional_metadata,
                                  translation_gist_client_id=translation_gist_client_id,
                                  translation_gist_object_id=translation_gist_object_id,
                                  is_template=False
                                  )
    DBSession.add(dbperspective)
    DBSession.flush()
    owner_client = DBSession.query(Client).filter_by(id=parent.client_id).first()
    owner = owner_client.user
    if not object_id or add_group:
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
                        additional_metadata=None,
                        domain=0,
                        category=0,
                        add_group=False):
    client_id, object_id = id

    if not parent_id:
        raise ResponseError(message="Bad parent ids")
    parent_client_id, parent_object_id = parent_id
    translation_gist_client_id, translation_gist_object_id = translation_gist_id if translation_gist_id else (None, None)

    duplicate_check = DBSession.query(Dictionary).filter_by(client_id=client_id, object_id=object_id).all()
    if duplicate_check:
        raise ResponseError(message="Dictionary with such ID already exists in the system")
    parent = DBSession.query(Language).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    if not parent:
        raise ResponseError(message="No such language in the system")

    resp = translation_gist_search("WiP")
    state_translation_gist_object_id, state_translation_gist_client_id = resp.object_id, resp.client_id
    dbdictionary_obj = Dictionary(client_id=client_id,
                                    object_id=object_id,
                                    state_translation_gist_object_id=state_translation_gist_object_id,
                                    state_translation_gist_client_id=state_translation_gist_client_id,
                                    parent=parent,
                                    translation_gist_client_id=translation_gist_client_id,
                                    translation_gist_object_id=translation_gist_object_id,
                                    additional_metadata=additional_metadata,
                                    domain=domain,
                                    category=category
                                    )

    client = DBSession.query(Client).filter_by(id=client_id).first()
    user = client.user
    if not object_id or add_group:
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
    client_id, object_id = id
    if not parent_id:
        raise ResponseError(message="Bad parent ids")
    parent_client_id, parent_object_id = parent_id
    parent = DBSession.query(DictionaryPerspective).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    if not parent:
        raise ResponseError(message="No such perspective in the system")

    field_client_id, field_object_id = field_id if field_id else (None, None)
    self_client_id, self_object_id = self_id if self_id else (None, None)
    link_client_id, link_object_id = link_id if link_id else (None, None)


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
                                                  upper_level=upper_level,
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

def create_dblanguage(id=None,
                      parent_id=None,
                      translation_gist_id=None,
                      additional_metadata=None):
    parent = None
    parent_client_id, parent_object_id = parent_id if parent_id else (None, None)
    client_id, object_id = id
    translation_gist_client_id, translation_gist_object_id = translation_gist_id if translation_gist_id else (None, None)

    if parent_client_id and parent_object_id:
        parent = DBSession.query(Language).\
            filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
        if not parent:
            raise ResponseError(message="No such language in the system")

    dblanguage = Language(
        client_id=client_id,
        object_id=object_id,
        translation_gist_client_id=translation_gist_client_id,
        translation_gist_object_id=translation_gist_object_id,
        additional_metadata=additional_metadata
    )
    DBSession.add(dblanguage)

    if parent:
        dblanguage.parent = parent

    prev_sibling = DBSession.query(Language).filter(Language.parent_client_id == parent_client_id,
                                                        Language.parent_object_id == parent_object_id,
                                                        Language.marked_for_deletion == False,
                                                    or_(Language.client_id != dblanguage.client_id,
                                                        Language.object_id != dblanguage.object_id)).order_by(Language.parent_client_id,
                                                                                        Language.parent_object_id,
                                                                                        Language.additional_metadata[
                                                                                            'younger_siblings'].desc()).first()
    dblanguage.additional_metadata = dict()
    dblanguage.additional_metadata['younger_siblings'] = list()
    if prev_sibling and prev_sibling.additional_metadata:
        dblanguage.additional_metadata['younger_siblings'] = prev_sibling.additional_metadata.get('younger_siblings')
        dblanguage.additional_metadata['younger_siblings'].append([prev_sibling.client_id, prev_sibling.object_id])

    # if not object_id:
    #     for base in DBSession.query(BaseGroup).filter_by(dictionary_default=True):
    #         new_group = Group(parent=base,
    #                           subject_object_id=dblanguage.object_id,
    #                           subject_client_id=dblanguage.client_id)
    #         if user not in new_group.users:
    #             new_group.users.append(user)
    #         DBSession.add(new_group)
    #         DBSession.flush()
    client = DBSession.query(Client).filter_by(id=client_id).first()
    user = client.user
    basegroups = []
    basegroups += [DBSession.query(BaseGroup).filter_by(name="Can edit languages").first()]
    basegroups += [DBSession.query(BaseGroup).filter_by(name="Can delete languages").first()]
    if not object_id:
        groups = []
        for base in basegroups:
            group = Group(subject_client_id=dblanguage.client_id, subject_object_id=dblanguage.object_id, parent=base)
            groups += [group]
        for group in groups:
            add_user_to_group(user, group)

    DBSession.flush()
    return dblanguage

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

    if not parent_id:
        raise ResponseError(message="Bad parent ids")
    parent_client_id, parent_object_id = parent_id
    parent = DBSession.query(LexicalEntry).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    if not parent:
        raise ResponseError(message="No such lexical entry in the system")

    upper_level = None

    field_client_id, field_object_id = field_id if field_id else (None, None)
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
    # TODO: check permissions if object_id != None
    # group = DBSession.query(Group).join(BaseGroup).filter(BaseGroup.subject == 'lexical_entries_and_entities',
    #                                                           Group.subject_client_id == dbentity.parent.parent.client_id,
    #                                                           Group.subject_object_id == dbentity.parent.parent.object_id,
    #                                                           BaseGroup.action == 'create').one()
    #
    # override_group = DBSession.query(Group).join(BaseGroup).filter(
    #     BaseGroup.subject == 'lexical_entries_and_entities',
    #     Group.subject_override == True,
    #     BaseGroup.action == 'create').one()
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

        if 'elan' in data_type:
            bag_of_words = list(eaf_wordlist(dbentity))
            dbentity.additional_metadata['bag_of_words'] = bag_of_words

        dbentity.additional_metadata['data_type'] = data_type
    elif data_type in ('link', "directed link"):
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

    if not perspective_id:
        raise ResponseError(message="Bad perspective ids")
    perspective_client_id, perspective_object_id = perspective_id

    perspective = DBSession.query(DictionaryPerspective). \
        filter_by(client_id=perspective_client_id, object_id=perspective_object_id).first()
    if not perspective:
        raise ResponseError(message="No such perspective in the system")

    dblexentry = LexicalEntry(object_id=object_id, client_id=client_id, parent_client_id=perspective_client_id,
                                parent_object_id=perspective_object_id, parent=perspective)
    if save_object:
        DBSession.add(dblexentry)
        DBSession.flush()
    return dblexentry

@celery.task
def async_create_parser_result(id, parser_id, entity_id,
                               task_key, cache_kwargs, sqlalchemy_url,
                               arguments, save_object):
    async_create_parser_result_method(id=id, parser_id=parser_id, entity_id=entity_id,
                                      task_key=task_key, cache_kwargs=cache_kwargs,
                                      sqlalchemy_url=sqlalchemy_url,
                                      arguments=arguments, save_object=save_object)

def async_create_parser_result_method(id, parser_id, entity_id,
                               task_key, cache_kwargs, sqlalchemy_url,
                               arguments, save_object):

    from lingvodoc.cache.caching import initialize_cache
    engine = create_engine(sqlalchemy_url)
    DBSession.configure(bind=engine)
    initialize_cache(cache_kwargs)
    task_status = TaskStatus.get_from_cache(task_key)
    entity = DBSession.query(Entity).filter_by(client_id=entity_id[0], object_id=entity_id[1]).first()
    content_filename = entity.content.split('/')[-1]
    task_status.set(1, 5, "Parsing of file " + content_filename + " started")

    try:

        create_parser_result(id=id, parser_id=parser_id, entity_id=entity_id,
                             arguments=arguments, save_object=save_object)

    except Exception as err:
        task_status.set(None, -1, "Parsing of file " + content_filename + " failed: %s" % str(err))
        raise

    task_status.set(2, 100, "Parsing of file " + content_filename + " finished")

def create_parser_result(id, parser_id, entity_id, arguments=None, save_object=True):

    client_id, object_id = id
    parser_client_id, parser_object_id = parser_id
    entity_client_id, entity_object_id = entity_id
    entity = DBSession.query(Entity). \
        filter_by(client_id=entity_client_id, object_id=entity_object_id).first()

    parser = DBSession.query(Parser). \
        filter_by(client_id=parser_client_id, object_id=parser_object_id).first()
    if not parser:
        raise ResponseError(message="No such parser in the system")

    if not arguments:
        arguments = dict()

    parse_method = getattr(ParseMethods, parser.name)

    # print(entity.content)
    ascii_part = entity.content[:entity.content.rfind('/') + 1]
    unicode_part = entity.content[entity.content.rfind('/') + 1:entity.content.rfind('.')]
    extension = entity.content[entity.content.rfind('.'):]
    url = ascii_part + urllib.request.quote(unicode_part) + extension
    response = urllib.request.urlopen(url)

    tmp_file_id, tmp_filename = tempfile.mkstemp()
    tmp_file = open(tmp_filename, 'wb')
    tmp_file.write(response.read())

    result = parse_method(tmp_filename, **arguments)
    # result = ParseMethods.dedoc_extract(tmp_filename)

    dbparserresult = ParserResult(client_id=client_id, object_id=object_id,
                                  parser_object_id=parser_object_id, parser_client_id=parser_client_id,
                                  entity_client_id=entity_client_id, entity_object_id=entity_object_id,
                                  arguments=arguments, content=result)
    if not dbparserresult.object_id:
        dbparserresult.object_id = get_client_counter(client_id)
    if save_object:
        DBSession.add(dbparserresult)
        DBSession.flush()

    transaction.commit()

    return dbparserresult

def create_parser(id, name, parameters=None):

    client_id, object_id = id

    dbparser = Parser(client_id=client_id, object_id=object_id,
                      name=name, parameters=parameters)
    DBSession.add(dbparser)
    DBSession.flush()
    return dbparser

# Json_input point to the method of file getting: if it's embedded in json, we need to decode it. If
# it's uploaded via multipart form, it's just saved as-is.
def create_object(request, content, obj, data_type, filename, json_input=True):
    import errno
    # here will be object storage write as an option. Fallback (default) is filesystem write
    settings = request.registry.settings
    storage = settings['storage']
    if storage['type'] == 'openstack':
        if json_input:
            content = base64.urlsafe_b64decode(content)
        # TODO: openstack objects correct naming
        filename = str(obj.data_type) + '/' + str(obj.client_id) + '_' + str(obj.object_id)
        real_location = openstack_upload(settings, content, filename, obj.data_type, 'test')
    else:
        filename = filename or 'noname.noext'
        storage_path, filename = object_file_path(obj, settings, data_type, filename, True)
        directory = os.path.dirname(storage_path)  # TODO: find out, why object_file_path were not creating dir
        try:
            os.makedirs(directory)
        except OSError as exception:
            if exception.errno != errno.EEXIST:
                raise
        with open(storage_path, 'wb+') as f:
            # set_trace()
            if json_input:
                f.write(base64.urlsafe_b64decode(content))
            else:
                shutil.copyfileobj(content, f)

        real_location = storage_path

    url = "".join((settings['storage']['prefix'],
                  settings['storage']['static_route'],
                  obj.__tablename__,
                  '/',
                  data_type,
                  '/',
                  str(obj.client_id), '/',
                  str(obj.object_id), '/',
                  filename))
    return real_location, url

def create_gists_with_atoms(translation_atoms, translation_gist_id, ids, gist_type=None):
        if translation_atoms is None:  # TODO: look at this
            if not translation_gist_id:
                raise ResponseError(message="translation_gist_id arg not found")
        else:
            client_id, object_id = ids
            client = DBSession.query(Client).filter_by(id=client_id).first()

            user = DBSession.query(User).filter_by(id=client.user_id).first()
            if not translation_gist_id:
                dbtranslationgist = TranslationGist(client_id=client_id, object_id=object_id, type=gist_type)
                DBSession.add(dbtranslationgist)
                DBSession.flush()
                translation_gist_client_id = dbtranslationgist.client_id
                translation_gist_object_id = dbtranslationgist.object_id
                translation_gist_id = [translation_gist_client_id, translation_gist_object_id]
            else:
                translation_gist_client_id, translation_gist_object_id = translation_gist_id
            basegroups = list()
            basegroups.append(DBSession.query(BaseGroup).filter_by(name="Can delete translationgist").first())
            if not object_id:
                groups = []
                for base in basegroups:
                    group = Group(subject_client_id=translation_gist_client_id,
                                  subject_object_id=translation_gist_object_id,
                                  parent=base)
                    groups += [group]
                for group in groups:
                    add_user_to_group(user, group)

            for atom_dict in translation_atoms:
                if "locale_id" in atom_dict and "content" in atom_dict:
                    locale_id = atom_dict["locale_id"]
                    content = atom_dict["content"]
                    dbtranslationatom = TranslationAtom(client_id=client_id,
                                                          object_id=object_id,
                                                          parent_client_id=translation_gist_client_id,
                                                          parent_object_id=translation_gist_object_id,
                                                          locale_id=locale_id,
                                                          content=content)
                    DBSession.add(dbtranslationatom)
                    DBSession.flush()
                    if not object_id:
                        basegroups = []
                        basegroups += [DBSession.query(BaseGroup).filter_by(name="Can edit translationatom").first()]
                        if not object_id:
                            groups = []
                            for base in basegroups:
                                group = Group(subject_client_id=dbtranslationatom.client_id,
                                                subject_object_id=dbtranslationatom.object_id,
                                                parent=base)
                                groups += [group]
                            for group in groups:
                                add_user_to_group(user, group)
                else:
                    raise ResponseError(message="locale_id and content args not found")
        return translation_gist_id





def object_file_path(obj, settings, data_type, filename, create_dir=False):
    filename = sanitize_filename(filename)
    base_path = settings['storage']['path']
    storage_dir = os.path.join(base_path, obj.__tablename__, data_type, str(obj.client_id), str(obj.object_id))
    if create_dir:
        # pdb.set_trace()
        storage_dir = os.path.normpath(storage_dir)
        os.makedirs(storage_dir, exist_ok=True)
    storage_path = os.path.join(storage_dir, filename)

    return storage_path, filename


def openstack_upload(settings, file, file_name, content_type,  container_name):
    storage = settings['storage']
    authurl = storage['authurl']
    user = storage['user']
    key = storage['key']
    auth_version = storage['auth_version']
    tenant_name = storage['tenant_name']
    conn = swiftclient.Connection(authurl=authurl, user=user, key=key,  auth_version=auth_version,
                                  tenant_name=tenant_name)
    #storageurl = conn.get_auth()[0]
    conn.put_container(container_name)
    obje = conn.put_object(container_name, file_name,
                    contents = file,
                    content_type = content_type)
    #obje = conn.get_object(container_name, file_name)
    return str(obje)


def update_metadata(dbobject, new_metadata=None):
    if new_metadata:
        old_meta = dbobject.additional_metadata
        if old_meta is None:
            dbobject.additional_metadata = new_metadata
        else:
            old_meta.update(new_metadata)
            dbobject.additional_metadata = old_meta
        flag_modified(dbobject, 'additional_metadata')


def translationgist_contents(translationgist):
    result = dict()
    result['client_id'] = translationgist.client_id
    result['object_id'] = translationgist.object_id
    result['type'] = translationgist.type
    result['created_at'] = translationgist.created_at
    contains = []
    for translationatom in translationgist.translationatom:
        contains.append(translationatom_contents(translationatom))
    result['contains'] = contains
    return result


def translationatom_contents(translationatom):
    result = dict()
    result['content'] = translationatom.content
    result['locale_id'] = translationatom.locale_id
    result['client_id'] = translationatom.client_id
    result['object_id'] = translationatom.object_id
    result['parent_client_id'] = translationatom.parent_client_id
    result['parent_object_id'] = translationatom.parent_object_id
    result['created_at'] = translationatom.created_at
    return result


def edit_role(dict_or_persp, user_id, role_id, client_id, organization=False, dictionary_default=False, perspective_default=False, action="add"):
    # TODO: refactor
    if role_id:
        user = DBSession.query(User).filter_by(id=user_id).first()
        org = DBSession.query(dbOrganization).filter_by(id=user_id).first()
        base = DBSession.query(BaseGroup).filter_by(id=role_id,
                                                    dictionary_default=dictionary_default,
                                                    perspective_default=perspective_default
                                          ).first()
        if not base:
            raise ResponseError(message="No such role in the system")
        group = DBSession.query(Group).filter_by(base_group_id=base.id,
                                                 subject_object_id=dict_or_persp.object_id,
                                                 subject_client_id=dict_or_persp.client_id
                                          ).first()
        if not group:
            raise ResponseError(message="No such group in the system")

        client = DBSession.query(Client).filter_by(id=client_id).first()
        userlogged = DBSession.query(User).filter_by(id=client.user_id).first()

        # Administrator can do everything.

        permitted = userlogged and userlogged.id == 1

        if userlogged in group.users:
            permitted = True
        if not permitted:
            for org in userlogged.organizations:
                if org in group.organizations:
                    permitted = True
                    break
        if not permitted:
            override_group = DBSession.query(Group).filter_by(base_group_id=base.id,
                                                              subject_override=True).first()
            if not override_group:
                raise ResponseError(message="No such group in the system")

            if userlogged in override_group.users:
                permitted = True  #TODO: refactor

        if not permitted:
            raise ResponseError(message="Not enough permission")
        ###


        if user:
            if organization:
                if org:
                    if action == "delete":
                            if org in group.organizations:
                                group.organizations.remove(org)
                    else:
                            if org not in group.organizations:
                                group.organizations.append(org)
            else:
                if action == "delete":
                    if user.id == userlogged.id:
                        raise ResponseError(message="Cannot delete roles from self")
                    if user in group.users:
                        group.users.remove(user)
                else:
                    if user not in group.organizations:
                        group.users.append(user)


def find_lexical_entries_by_tags(tags, field_client_id, field_object_id):
    return DBSession.query(LexicalEntry) \
        .join(LexicalEntry.entity) \
        .join(Entity.publishingentity) \
        .join(Entity.field) \
        .filter(Entity.content.in_(tags),
                PublishingEntity.accepted == True,
                Field.client_id == field_client_id,
                Field.object_id == field_object_id).all()

def find_all_tags(lexical_entry, field_client_id, field_object_id):
    tag = None
    for entity in lexical_entry.entity:
        if entity.field.data_type == 'Grouping Tag':
            tag = entity.content
            break
    if not tag:
        return []
    else:
        tags = [tag]
        new_tags = [tag]
        while new_tags:
            lexical_entries = find_lexical_entries_by_tags(new_tags, field_client_id, field_object_id)
            new_tags = list()
            for lex in lexical_entries:
                entities = DBSession.query(Entity) \
                    .join(Entity.field) \
                    .join(Entity.publishingentity) \
                    .filter(Entity.parent == lex,
                            PublishingEntity.accepted == True,
                            Field.client_id == field_client_id,
                            Field.object_id == field_object_id).all()
                for entity in entities:
                    if entity.content not in tags:
                        tags.append(entity.content)
                        new_tags.append(entity.content)
        return tags


def create_group_entity(request, client, user, obj_id):  # tested
        response = dict()
        req = request
        tags = list()
        if 'tag' in req:
            tags.append(req['tag'])
        field_client_id=req['field_client_id']
        field_object_id=req['field_object_id']
        # field = DBSession.query(Field).\
        #     filter_by(client_id=field_client_id, object_id=field_object_id).first()
        #
        # if not field:
        #     return {'error': str("No such field in the system")}

        for par in req['connections']:
            parent = DBSession.query(LexicalEntry).\
                filter_by(client_id=par['client_id'], object_id=par['object_id']).first()
            if not parent:
                return {'error': str("No such lexical entry in the system")}
            par_tags = find_all_tags(parent, field_client_id, field_object_id)
            for tag in par_tags:
                if tag not in tags:
                    tags.append(tag)
        if not tags:
            n = 10  # better read from settings
            tag = (
                time.asctime(time.gmtime()) + ''.join(
                    random.SystemRandom().choice(string.ascii_uppercase + string.digits) for c in range(n)))
            tags.append(tag)
        lexical_entries = find_lexical_entries_by_tags(tags, field_client_id, field_object_id)
        for par in req['connections']:
            parent = DBSession.query(LexicalEntry).\
                filter_by(client_id=par['client_id'], object_id=par['object_id']).first()
            if parent not in lexical_entries:
                lexical_entries.append(parent)

        for lex in lexical_entries:
            for tag in tags:
                tag_entity = DBSession.query(Entity) \
                    .join(Entity.field) \
                    .filter(Entity.parent == lex,
                            Field.client_id == field_client_id,
                            Field.object_id == field_object_id,
                            Entity.content == tag).first()
                if not tag_entity:
                    tag_entity = Entity(client_id=client.id, object_id=obj_id.next,
                                        field_client_id=field_client_id, field_object_id=field_object_id, content=tag, parent=lex)

                    # group = DBSession.query(Group).join(BaseGroup).filter(
                    #     BaseGroup.subject == 'lexical_entries_and_entities',
                    #     Group.subject_client_id == tag_entity.parent.parent.client_id,
                    #     Group.subject_object_id == tag_entity.parent.parent.object_id,
                    #     BaseGroup.action == 'create').one()
                    # if user in group.users:
                    tag_entity.publishingentity.accepted = True
                    DBSession.add(tag_entity)
