import urllib

import graphene
from sqlalchemy import and_
from sqlalchemy.orm import aliased

from lingvodoc.schema.gql_dictionaryperspective import DictionaryPerspective
from lingvodoc.schema.gql_field import Field
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

from lingvodoc.utils.corpus_converter import create_entity as corpus_create_entity

def create_n_entries_in_persp(n, pid, client):
    lexentries_list = list()
    client = client
    for i in range(0, n):
        id = [client.id, None]
        perspective_id = pid
        dblexentry = create_lexicalentry(id, perspective_id, True)
        lexentries_list.append(dblexentry)
    DBSession.bulk_save_objects(lexentries_list)
    DBSession.flush()
    result = list()
    for lexentry in lexentries_list:
        result.append(lexentry)
    return result

def copy_sound_or_markup_entity(entity, dest_fid, client, self_client_id=None, self_object_id=None, parent_client_id=None, parent_object_id=None):

    storage = dict()
    storage['path'] = "/home/andriy/Desktop/objects/"
    storage['prefix'] = "http://localhost:6543/"
    storage['static_route'] = "objects/"

    # filename = "copy_" + sound.content[sound.content.rfind('/')+1:]
    filename = entity.content[entity.content.rfind('/') + 1:]

    ascii_part = entity.content[:entity.content.rfind('/') + 1]
    unicode_part = entity.content[entity.content.rfind('/') + 1:entity.content.rfind('.')]
    extension = entity.content[entity.content.rfind('.'):]
    url = ascii_part + urllib.request.quote(unicode_part) + extension

    response = urllib.request.urlopen(url)
    content = response.read()
    outfile = open("out.wav", "wb")
    outfile.write(content)

    created_entity_ids = corpus_create_entity(parent_client_id, parent_object_id, dest_fid[0], dest_fid[1],
                                            entity.additional_metadata, client,
                                            content=content, filename=filename,
                                            folder_name="graphql_files", locale_id=entity.locale_id,
                                            storage=storage, byte_content=True,
                                            self_client_id=self_client_id, self_object_id=self_object_id)

    return created_entity_ids

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

        one_pid = False

        # check if client
        client = DBSession.query(Client).filter_by(id=info.context["client_id"]).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           info.context["client_id"])

        # check if perspective and fields present
        # check fields type

        pid1 = args.get('pid1')
        pid2 = args.get('pid2')
        fid1 = args.get('fid1')
        fid2 = args.get('fid2')

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

        ftype = dbfield1.data_type
        if ftype != "Text" and ftype != "Sound" and ftype != "Markup":
            raise ResponseError('field 1 is not Text or Sound or Markup type')

        dbfield2 = DBSession.query(dbField).filter_by(client_id=fid2[0], object_id=fid2[1]).first()
        if dbfield2.data_type != ftype:
            raise ResponseError('field 2 has not the same type as field 1')

        e = aliased(dbEntity)
        le = aliased(dbLexicalEntry)
        query_result = DBSession.query(e).join(le, and_(
            e.parent_client_id == le.client_id, e.parent_object_id == le.object_id,
            e.field_client_id == fid1[0], e.field_object_id == fid1[1],
            le.parent_client_id == pid1[0], le.parent_object_id == pid1[1],
            e.marked_for_deletion == False, le.marked_for_deletion == False,
            le.moved_to == None)).all()

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

            i = -1
            for lex_entry_from in lex_entries_from:
                i += 1
                for entity in lex_entry_from:
                    # create one db entry and add to list of all entries to be added
                    if ftype != "Text":
                        copy_sound_or_markup_entity(entity, fid2, client, parent_client_id=lex_entries_to[i].client_id,
                                                    parent_object_id=lex_entries_to[i].object_id)
                    else:
                        dbentity = create_entity(id=[entity.field_client_id, None],
                                                 parent_id=[lex_entries_to[i].client_id, lex_entries_to[i].object_id],
                                                 locale_id=entity.locale_id, content=entity.content, request=info.context.request,
                                                 save_object=True)
                        dbentities_list.append(dbentity)

        else:

            for entity in query_result:
                if ftype != "Text":
                    copy_sound_or_markup_entity(entity, fid2, client, parent_client_id=entity.parent_client_id,
                                                parent_object_id=entity.parent_object_id)
                else:
                    dbentity = create_entity(id=[entity.field_client_id, None],
                                         parent_id=[entity.parent_client_id, entity.parent_object_id],
                                         additional_metadata=entity.additional_metadata, field_id=fid2,
                                         locale_id=entity.locale_id, content=entity.content,
                                         request=info.context.request,
                                         save_object=True)
                    dbentities_list.append(dbentity)

        if len(dbentities_list) > 0:
            DBSession.bulk_save_objects(dbentities_list)
            DBSession.flush()

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

        one_pid = False

        # check if client
        client = DBSession.query(Client).filter_by(id=info.context["client_id"]).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           info.context["client_id"])

        # check if perspective and fields present
        # check fields type

        pid1 = args.get('pid1')
        pid2 = args.get('pid2')
        sfid1 = args.get('sfid1')
        mfid1 = args.get('mfid1')
        sfid2 = args.get('sfid2')
        mfid2 = args.get('mfid2')

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
            e2.field_object_id == mfid1[1], e2.marked_for_deletion == False)).all()

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

        return CopySoundMarkupFields(triumph=True)