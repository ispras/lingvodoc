import base64
import errno
import hashlib
import os
import os.path
from pathvalidate import sanitize_filename
import shutil
import urllib

import graphene
from lingvodoc.cache.caching import TaskStatus, CACHE
from sqlalchemy import and_, create_engine
from sqlalchemy.orm import aliased

from lingvodoc.queue.celery import celery
from lingvodoc.utils.creation import create_entity, create_lexicalentry
from lingvodoc.utils.verification import check_lingvodoc_id

from lingvodoc.models import (
    DBSession,
    Entity as dbEntity,
    LexicalEntry as dbLexicalEntry,
    Field as dbField,
    DictionaryPerspective as dbDictionaryPerspective,
    Client,
)
from lingvodoc.schema.gql_holders import LingvodocID, ResponseError

def create_n_entries_in_persp(n, pid, client):
    lexentries_list = list()
    client = client
    for i in range(0, n):
        id = [client.id, None]
        perspective_id = pid
        dblexentry = create_lexicalentry(id, perspective_id, True)
        lexentries_list.append(dblexentry)
    # DBSession.bulk_save_objects(lexentries_list)
    CACHE.set(objects = lexentries_list, DBSession=DBSession)
    # DBSession.flush()
    result = list()
    for lexentry in lexentries_list:
        result.append(lexentry)
    return result

def object_file_path(obj, base_path, folder_name, filename, create_dir=False):
    filename = sanitize_filename(filename)
    storage_dir = os.path.join(base_path, obj.__tablename__, folder_name, str(obj.client_id), str(obj.object_id))
    if create_dir:
        os.makedirs(storage_dir, exist_ok=True)
    storage_path = os.path.join(storage_dir, filename)
    return storage_path, filename

def create_object(content, obj, data_type, filename, folder_name, storage):

    storage_path, filename = object_file_path(obj, storage["path"], folder_name, filename, True)
    directory = os.path.dirname(storage_path)  # TODO: find out, why object_file_path were not creating dir
    try:
        os.makedirs(directory)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise
    with open(storage_path, 'wb+') as f:
        f.write(content)

    real_location = storage_path

    url = "".join((storage["prefix"],
                  storage["static_route"],
                  obj.__tablename__,
                  '/',
                  folder_name,
                  '/',
                  str(obj.client_id), '/',
                  str(obj.object_id), '/',
                  filename))
    return real_location, url

def corpus_create_entity(
    le_client_id,
    le_object_id,
    field_client_id,
    field_object_id,
    data_type,
    client_id,
    content = None,
    filename = None,
    self_client_id = None,
    self_object_id = None,
    link_client_id = None,
    link_object_id = None,
    folder_name = None,
    storage = None):

    entity = dbEntity(client_id=client_id,
                    field_client_id=field_client_id,
                    field_object_id=field_object_id,
                    parent_client_id=le_client_id,
                    parent_object_id=le_object_id)

    if self_client_id and self_object_id:
        entity.self_client_id = self_client_id
        entity.self_object_id = self_object_id

    hash = None
    real_location = None
    url = None
    if data_type == 'image' or data_type == 'sound' or 'markup' in data_type:
        ##entity.data_type = data_type
        real_location, url = create_object(content, entity, data_type, filename, folder_name, storage)
        entity.content = url
        old_meta = entity.additional_metadata
        need_hash = True
        if old_meta:
            new_meta = old_meta #json.loads(old_meta)
            if new_meta.get('hash'):
                need_hash = False
        if need_hash:
            hash = hashlib.sha224(content).hexdigest()

            hash_dict = {'hash': hash}
            if old_meta:
                new_meta = old_meta #json.loads(old_meta)
                new_meta.update(hash_dict)
            else:
                new_meta = hash_dict
            entity.additional_metadata = new_meta #json.dumps(new_meta)
        old_meta = entity.additional_metadata
        if data_type == "markup":
            data_type_dict = {"data_type": "praat markup"}
            if old_meta:
                new_meta = old_meta #json.loads(old_meta)
                new_meta.update(data_type_dict)
            else:
                new_meta = data_type_dict
            entity.additional_metadata = new_meta #json.dumps(new_meta)
        if data_type == "sound":
            data_type_dict = {"data_type": "sound"}
            if old_meta:
                new_meta = old_meta #json.loads(old_meta)
                new_meta.update(data_type_dict)
            else:
                new_meta = data_type_dict
            entity.additional_metadata = new_meta #json.dumps(new_meta)
    elif data_type == 'link':
        try:
            entity.link_client_id = link_client_id
            entity.link_object_id = link_object_id
        except (KeyError, TypeError):
            return {'Error': "The field is of link type. You should provide client_id and object id in the content"}
    else:
        entity.content = content
    entity.publishingentity.accepted = True

    # DBSession.add(entity)
    CACHE.set(objects = [entity, ], DBSession=DBSession)

    # means that the function was called from CopyField and so need to be sure that sound has been copied before copying markups
    if byte_content:
        DBSession.flush()
    return (entity.client_id, entity.object_id)

def copy_sound_or_markup_entity(
    entity,
    dest_fid,
    ftype,
    client,
    self_client_id=None,
    self_object_id=None,
    parent_client_id=None,
    parent_object_id=None):

    storage = info.context.request.registry.settings["storage"]

    # filename = "copy_" + sound.content[sound.content.rfind('/')+1:]
    filename = entity.content[entity.content.rfind('/') + 1:]

    ascii_part = entity.content[:entity.content.rfind('/') + 1]
    unicode_part = entity.content[entity.content.rfind('/') + 1:entity.content.rfind('.')]
    extension = entity.content[entity.content.rfind('.'):]
    url = ascii_part + urllib.request.quote(unicode_part) + extension

    response = urllib.request.urlopen(url)
    content = response.read()

    created_entity_ids = (

        corpus_create_entity(
            parent_client_id,
            parent_object_id,
            dest_fid[0],
            dest_fid[1],
            ftype,
            client.id,
            content=content,
            filename=filename,
            folder_name="graphql_files",
            storage=storage,
            self_client_id=self_client_id,
            self_object_id=self_object_id))

    return created_entity_ids


@celery.task
def async_copy_single_field(one_pid, ftype, client, info,
                            pid1, pid2, fid1, fid2,
                            task_key, cache_kwargs, sqlalchemy_url):

    from lingvodoc.cache.caching import initialize_cache
    engine = create_engine(sqlalchemy_url)
    DBSession.configure(bind=engine)
    initialize_cache(cache_kwargs)
    global CACHE
    from lingvodoc.cache.caching import CACHE
    task_status = TaskStatus.get_from_cache(task_key)

    ftype = ftype.lower()

    try:

        e = aliased(dbEntity)
        le = aliased(dbLexicalEntry)
        query_result = DBSession.query(e).join(le, and_(
            e.parent_client_id == le.client_id, e.parent_object_id == le.object_id,
            e.field_client_id == fid1[0], e.field_object_id == fid1[1],
            le.parent_client_id == pid1[0], le.parent_object_id == pid1[1],
            e.marked_for_deletion == False, le.marked_for_deletion == False,
            le.moved_to == None)).all()

        task_status.set(2, 5, "Made a query to database")

        dbentities_list = list()

        # lex_entries_to is a list of newly created lex entries in pid1 of length of lex_entries_from

        if not one_pid:
            # for each element of this list a new lex entry should be created
            lex_entries_from = list()
            last_parent_ids = [0, 0]
            for entity in query_result:
                if entity.parent_client_id != last_parent_ids[0] or \
                        entity.parent_object_id != last_parent_ids[1]:
                    lex_entries_from.append(list())
                lex_entries_from[-1].append(entity)
                last_parent_ids = [entity.parent_client_id, entity.parent_object_id]

            # get list of lex entries of pid2
            lex_entries_to = create_n_entries_in_persp(len(lex_entries_from), pid2, client)
            task_status.set(3, 15, "Made sufficient number of lexical entries in new perspective")

            i = -1
            for lex_entry_from in lex_entries_from:
                i += 1
                for entity in lex_entry_from:
                    # create one db entry and add to list of all entries to be added
                    if ftype != "text":
                        copy_sound_or_markup_entity(entity, fid2, ftype, client,
                                                    parent_client_id=lex_entries_to[i].client_id,
                                                    parent_object_id=lex_entries_to[i].object_id)
                        task_status.set(4, 15+round((1 / len(query_result)) * 85), "Copied an entity")
                    else:
                        dbentity = create_entity(id=[entity.field_client_id, None],
                                                 parent_id=[lex_entries_to[i].client_id, lex_entries_to[i].object_id],
                                                 locale_id=entity.locale_id, content=entity.content,
                                                 request=info.context.request,
                                                 save_object=True)
                        dbentities_list.append(dbentity)
                        task_status.set(4, 15+round((1 / len(query_result)) * 85), "Copied an entity")

        else:

            for entity in query_result:
                if ftype != "text":
                    copy_sound_or_markup_entity(entity, fid2, ftype, client,
                                                parent_client_id=entity.parent_client_id,
                                                parent_object_id=entity.parent_object_id)
                    task_status.set(4, 15 + round((1 / len(query_result)) * 85), "Copied an entity")
                else:
                    dbentity = create_entity(id=[entity.field_client_id, None],
                                             parent_id=[entity.parent_client_id, entity.parent_object_id],
                                             additional_metadata=entity.additional_metadata, field_id=fid2,
                                             locale_id=entity.locale_id, content=entity.content,
                                             request=info.context.request,
                                             save_object=True)
                    dbentities_list.append(dbentity)
                    task_status.set(4, 15+round((1 / len(query_result)) * 85), "Copied an entity")

        if len(dbentities_list) > 0:
            # DBSession.bulk_save_objects(dbentities_list)
            CACHE.set(objects = dbentities_list, DBSession = DBSession)
    except Exception as err:
        task_status.set(None, -1, "Copying failed: %s" % str(err))
        raise

    # DBSession.flush()
    task_status.set(5, 100, "Copying field finished")


@celery.task
def async_copy_sound_markup_field(one_pid, client, info,
                            pid1, pid2, sfid1, sfid2, mfid1, mfid2,
                            task_key, cache_kwargs, sqlalchemy_url):

    from lingvodoc.cache.caching import initialize_cache
    engine = create_engine(sqlalchemy_url)
    DBSession.configure(bind=engine)
    initialize_cache(cache_kwargs)
    task_status = TaskStatus.get_from_cache(task_key)

    try:

        e1 = aliased(dbEntity)
        e2 = aliased(dbEntity)
        le = aliased(dbLexicalEntry)
        query_result = DBSession.query(le, e1, e2).join(e1, and_(
            e1.parent_client_id == le.client_id, e1.parent_object_id == le.object_id,
            e1.field_client_id == sfid1[0], e1.field_object_id == sfid1[1],
            le.parent_client_id == pid1[0], le.parent_object_id == pid1[1],
            e1.marked_for_deletion == False, le.marked_for_deletion == False,
            le.moved_to == None)).outerjoin(e2, and_(e2.self_client_id == e1.client_id,
                                                     e2.self_object_id == e1.object_id, e2.field_client_id == mfid1[0],
                                                     e2.field_object_id == mfid1[1],
                                                     e2.marked_for_deletion == False)).all()

        task_status.set(2, 5, "Made a query to database")

        # [0] is lex entry, [1] is sound, [2] is markup

        if not one_pid:
            # for each element of this list a new lex entry should be created
            lex_entries_from = list()
            last_lex_entry_ids = [0, 0]
            last_sound_ids = [0, 0]
            for row in query_result:
                lex_entry = row[0]
                sound = row[1]

                has_markups = False
                if row[2]:
                    markup = row[2]
                    has_markups = True

                if lex_entry.client_id != last_lex_entry_ids[0] or \
                        lex_entry.object_id != last_lex_entry_ids[1]:
                    lex_entries_from.append(list())
                if sound.client_id != last_sound_ids[0] or \
                        sound.object_id != last_sound_ids[1]:
                    lex_entries_from[-1].append(dict())
                    lex_entries_from[-1][-1]['sound'] = sound
                    lex_entries_from[-1][-1]['markups'] = list()
                if has_markups:
                    lex_entries_from[-1][-1]['markups'].append(markup)
                last_lex_entry_ids = [lex_entry.client_id, lex_entry.object_id]
                last_sound_ids = [sound.client_id, sound.object_id]

            # get list of lex entries of pid2
            lex_entries_to = create_n_entries_in_persp(len(lex_entries_from), pid2, client)
            task_status.set(3, 15, "Made sufficient number of lexical entries in new perspective")

            i = -1
            for lex_entry_from in lex_entries_from:
                i += 1
                for element in lex_entry_from:
                    sound = element['sound']
                    markups = element['markups']

                    sound_entity_ids = copy_sound_or_markup_entity(sound, sfid2, client,
                                                                   parent_client_id=lex_entries_to[i].client_id,
                                                                   parent_object_id=lex_entries_to[i].object_id)


                    for markup in markups:
                        sound_entity_ids = copy_sound_or_markup_entity(markup, mfid2, client,
                                                                       parent_client_id=lex_entries_to[i].client_id,
                                                                       parent_object_id=lex_entries_to[i].object_id,
                                                                       self_client_id=sound_entity_ids[0],
                                                                       self_object_id=sound_entity_ids[1])

                    task_status.set(4, 15 + round(((1 + len(markups))/ len(query_result)) * 85), "Copied a sound entity with markup entities")

        else:

            last_sound_ids = [0, 0]
            sounds = list()
            for row in query_result:
                sound = row[1]
                has_markups = False
                if row[2]:
                    markup = row[2]
                    has_markups = True

                if sound.client_id != last_sound_ids[0] or \
                        sound.object_id != last_sound_ids[1]:
                    sounds.append(dict())
                    sounds[-1]['sound'] = sound
                    sounds[-1]['markups'] = list()
                if has_markups:
                    sounds[-1]['markups'].append(markup)
                last_sound_ids = [sound.client_id, sound.object_id]

            for element in sounds:

                sound = element['sound']
                markups = element['markups']

                sound_entity_ids = copy_sound_or_markup_entity(sound, sfid2, client,
                                                               parent_client_id=sound.parent_client_id,
                                                               parent_object_id=sound.parent_object_id)

                for markup in markups:
                    copy_sound_or_markup_entity(markup, mfid2, client,
                                                parent_client_id=markup.parent_client_id,
                                                parent_object_id=markup.parent_object_id,
                                                self_client_id=sound_entity_ids[0],
                                                self_object_id=sound_entity_ids[1])

                task_status.set(4, 15 + round(((1 + len(markups))/ len(query_result)) * 85), "Copied a sound entity with markup entities")

    except Exception as err:
        task_status.set(None, -1, "Copying failed: %s" % str(err))
        raise

    task_status.set(5, 100, "Copying field finished")

class CopySingleField(graphene.Mutation):
    class Arguments:
        # fidX ~ field_id_X, pid ~ perspective_id
        fid1 = LingvodocID(required=True)
        fid2 = LingvodocID(required=True)
        pid1 = LingvodocID(required=True)
        pid2 = LingvodocID(required=True)

    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):

        request = info.context.request

        one_pid = False

        cur_args = dict()

        # check if client
        cur_args['client'] = client = DBSession.query(Client).filter_by(id=info.context["client_id"]).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           info.context["client_id"])
        else:
            user_id = Client.get_user_by_client_id(client.id).id

        # check if perspective and fields present
        # check fields type

        pid1 = cur_args['pid1'] = args.get('pid1')
        pid2 = cur_args['pid2'] = args.get('pid2')
        fid1 = cur_args['fid1'] = args.get('fid1')
        fid2 = cur_args['fid2'] = args.get('fid2')

        if not check_lingvodoc_id(fid1):
            raise ResponseError('no valid field 1 id provided')
        if not check_lingvodoc_id(fid2):
            raise ResponseError('no valid field 2 id provided')

        if not check_lingvodoc_id(pid1):
            raise ResponseError('no perspective_1 id provided')
        if pid1 == pid2:
            if fid1 == fid2:
                raise ResponseError('cannot copy a field into itself')
            one_pid = True
        elif not check_lingvodoc_id(pid2):
            raise ResponseError('no perspective_2 id provided')

        info.context.acl_check('create', 'lexical_entries_and_entities',
                               (pid2[0], pid2[1]))

        dbfield1 = DBSession.query(dbField).filter_by(client_id=fid1[0], object_id=fid1[1]).first()

        cur_args['ftype'] = ftype = dbfield1.data_type
        if ftype != "Text" and ftype != "Sound" and ftype != "Markup":
            raise ResponseError('field 1 is not Text or Sound or Markup type')

        dbfield2 = DBSession.query(dbField).filter_by(client_id=fid2[0], object_id=fid2[1]).first()
        if dbfield2.data_type != ftype:
            raise ResponseError('field 2 has not the same type as field 1')

        task = TaskStatus(user_id, "Copying single field", "", 5)

        cur_args['one_pid'] = one_pid
        cur_args['info'] = info
        cur_args["task_key"] = task.key
        cur_args["cache_kwargs"] = request.registry.settings["cache_kwargs"]
        cur_args["sqlalchemy_url"] = request.registry.settings["sqlalchemy.url"]

        res = async_copy_single_field.delay(**cur_args)

        return CopySingleField(triumph=True)

class CopySoundMarkupFields(graphene.Mutation):
    class Arguments:
        # sfidX ~ sound field_id_X, mfidX ~ markup field_id_X, pid ~ perspective_id
        sfid1 = LingvodocID(required=True)
        mfid1 = LingvodocID(required=True)
        sfid2 = LingvodocID(required=True)
        mfid2 = LingvodocID(required=True)
        pid1 = LingvodocID(required=True)
        pid2 = LingvodocID(required=True)

    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):

        request = info.context.request

        cur_args = dict()

        one_pid = False

        # check if client
        cur_args['client'] = client = DBSession.query(Client).filter_by(id=info.context["client_id"]).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           info.context["client_id"])
        else:
            user_id = Client.get_user_by_client_id(client.id).id

        # check if perspective and fields present
        # check fields type

        cur_args['pid1'] = pid1 = args.get('pid1')
        cur_args['pid2'] = pid2 = args.get('pid2')
        cur_args['sfid1'] = sfid1 = args.get('sfid1')
        cur_args['mfid1'] = mfid1 = args.get('mfid1')
        cur_args['sfid2'] = sfid2 = args.get('sfid2')
        cur_args['mfid2'] = mfid2 = args.get('mfid2')

        if not check_lingvodoc_id(sfid1):
            raise ResponseError('no valid sound field 1 id provided')
        if not check_lingvodoc_id(sfid2):
            raise ResponseError('no valid sound field 2 id provided')
        if not check_lingvodoc_id(mfid1):
            raise ResponseError('no valid markup field 1 id provided')
        if not check_lingvodoc_id(mfid2):
            raise ResponseError('no valid markup field 2 id provided')

        if not check_lingvodoc_id(pid1):
            raise ResponseError('no perspective_1 id provided')
        if pid1 == pid2:
            if sfid1 == sfid2 or mfid1 == mfid2:
                raise ResponseError('cannot copy a field into itself')
            one_pid = True
        elif not check_lingvodoc_id(pid2):
            raise ResponseError('no perspective_2 id provided')

        info.context.acl_check('create', 'lexical_entries_and_entities',
                               (pid2[0], pid2[1]))

        dbsfield1 = DBSession.query(dbField).filter_by(client_id=sfid1[0], object_id=sfid1[1]).first()
        if dbsfield1.data_type != "Sound":
            raise ResponseError('sfield 1 is not Sound type')

        dbmfield1 = DBSession.query(dbField).filter_by(client_id=mfid1[0], object_id=mfid1[1]).first()
        if dbmfield1.data_type != "Markup":
            raise ResponseError('mfield 1 is not Markup type')

        dbsfield2 = DBSession.query(dbField).filter_by(client_id=sfid2[0], object_id=sfid2[1]).first()
        if dbsfield2.data_type != "Sound":
            raise ResponseError('sfield 2 is not Sound type')

        dbmfield2 = DBSession.query(dbField).filter_by(client_id=mfid2[0], object_id=mfid2[1]).first()
        if dbmfield2.data_type != "Markup":
            raise ResponseError('mfield 2 is not Markup type')

        task = TaskStatus(user_id, "Copying sound and markup fields", "", 5)

        cur_args['one_pid'] = one_pid
        cur_args['info'] = info
        cur_args["task_key"] = task.key
        cur_args["cache_kwargs"] = request.registry.settings["cache_kwargs"]
        cur_args["sqlalchemy_url"] = request.registry.settings["sqlalchemy.url"]

        res = async_copy_sound_markup_field.delay(**cur_args)

        return CopySoundMarkupFields(triumph=True)
