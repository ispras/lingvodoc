import time
import random
import string
import collections
import transaction
import datetime
from collections import defaultdict
from itertools import chain
import logging
import traceback
import pprint
import csv
import urllib
import io

import graphene
from sqlalchemy import create_engine

from lingvodoc.cache.caching import TaskStatus
from lingvodoc.models import (
    Dictionary as dbDictionary,
    Entity as dbEntity,
    TranslationAtom as dbTranslationAtom,
    TranslationGist as dbTranslationGist,
    DBSession,
    Client as dbClient,
    Language as dbLanguage,
    User as dbUser,
    Field as dbField,
    DictionaryPerspective as dbDictionaryPerspective,
    BaseGroup as dbBaseGroup,
    Group as dbGroup,
    Organization as dbOrganization,
    UserBlobs as dbUserBlobs,
    LexicalEntry as dbLexicalEntry
)
from lingvodoc.utils.creation import create_gists_with_atoms, update_metadata, add_user_to_group
from lingvodoc.schema.gql_holders import (
    LingvodocObjectType,
    CommonFieldsComposite,
    StateHolder,
    TranslationHolder,
    fetch_object,
    del_object,
    client_id_check,
    ResponseError,
    ObjectVal,
    acl_check_by_id,
    LingvodocID,
    UserAndOrganizationsRoles
)

from lingvodoc.utils import statistics
from lingvodoc.utils.creation import (create_perspective,
                                      create_dbdictionary,
                                      create_dictionary_persp_to_field,
                                      edit_role,
                                      create_group_entity)
from lingvodoc.utils.search import translation_gist_search, get_id_to_field_dict

from lingvodoc.scripts.convert_five_tiers import convert_all
from lingvodoc.queue.celery import celery

from lingvodoc.cache.caching import CACHE

# Setting up logging.
log = logging.getLogger(__name__)


#from lingvodoc.utils.creation import create_entity, create_lexicalentry



"""
    column_dict = dict() #collections.OrderedDict()
    columns = lines[0]
    #lines.pop()
    j = 0
    for line in lines:
        i = 0
        if not j:
            j=1
            continue
        for column in columns:
            if not column in column_dict:
                column_dict[column] = []
            column_dict[column].append(line[i])
            i += 1
    return column_dict
"""


def csv_to_columns(path, url):

    # First trying as if it is a special Starling CSV-like format.

    try:

        try:
            csv_file = (

                open(path, 'rb')
                    .read()
                    .decode('utf-8-sig', 'ignore'))

        except FileNotFoundError:

            csv_file = (

                urllib.request.urlopen(
                    urllib.parse.quote(url, safe = '/:'))
                    .read()
                    .decode('utf-8-sig', 'ignore'))

        lines = list()
        for x in csv_file.split("\n"):
            if not x:
                continue
            lines.append(x.rstrip().split('#####'))
            #n = len(x.rstrip().split('|'))
        #lines = [x.rstrip().split('|') for x in csv_file.split("\n") if x.rstrip().split('|')]
        column_dict = dict()
        columns = lines[0]

        for line in lines[1:]:
            if len(line) != len(columns):
                continue
            col_num = 0
            for column in columns:
                if not column in column_dict:
                    column_dict[column] = []
                column_dict[column].append(line[col_num])
                col_num += 1
        # hack #1

        column_dict["NUMBER"] = [int(x) for x in column_dict["NUMBER"]] #list(range(1, len(column_dict["NUMBER"]) + 1))

        return column_dict, True

    # If failed, we try as if it is an Excel-generated CSV file.

    except:

        try:

            csv_file = (

                open(path,
                    encoding = 'utf-8-sig',
                    errors = 'ignore',
                    newline = ''))

        except FileNotFoundError:

            csv_str = (

                urllib.request.urlopen(
                    urllib.parse.quote(url, safe = '/:'))
                    .read()
                    .decode('utf-8-sig', 'ignore'))

            csv_file = (
                io.StringIO(csv_str))

        dialect = (
            csv.Sniffer().sniff(csv_file.read(4096)))

        csv_file.seek(0)

        csv_reader = (
            csv.reader(csv_file, dialect))

        row_list = [row for row in csv_reader]

        # Assuming first row contains field headers.

        header_list = row_list[0]

        while header_list and not header_list[-1].strip():
            header_list.pop()

        # Stripping whitespace for compatibility with gql_userblobs.py:179.

        header_list = [
            header.strip() for header in header_list]

        column_dict = {
            header: [] for header in header_list}

        column_dict['NUMBER'] = []

        # BAD HACK, just mocking up a 'NUMBER' column based on row indices.

        for index, row in enumerate(row_list[1:]):

            for column, value in zip(header_list, row):
                column_dict[column].append(value)

            column_dict['NUMBER'].append(index)

        csv_file.close()

        return column_dict, False


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
    # parent = DBSession.query(dbLexicalEntry).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    # if not parent:
    #     raise ResponseError(message="No such lexical entry in the system")

    upper_level = None

    field_client_id, field_object_id = field_id if field_id else (None, None)


    if self_id:
        # self_client_id, self_object_id = self_id
        # upper_level = DBSession.query(dbEntity).filter_by(client_id=self_client_id,
        #                                                   object_id=self_object_id).first()
        upper_level = CACHE.get(objects =
            {
                dbEntity : (self_id, )
            },
        DBSession=DBSession)

        if not upper_level:
            raise ResponseError(message="No such upper level in the system")

    client_id, object_id = id

    # TODO: check permissions if object_id != None


    real_location = None
    url = None

    if link_id:
        link_client_id, link_object_id = link_id
        dbentity = dbEntity(client_id=client_id,
                            object_id=object_id,
                            field_client_id=field_client_id,
                            field_object_id=field_object_id,
                            locale_id=locale_id,
                            additional_metadata=additional_metadata,
                            parent_client_id=parent_client_id,
                            parent_object_id=parent_object_id,
                            link_client_id = link_client_id,
                            link_object_id = link_object_id
                            )
        # else:
        #     raise ResponseError(
        #         message="The field is of link type. You should provide client_id and object id in the content")
    else:
        dbentity = dbEntity(client_id=client_id,
                            object_id=object_id,
                            field_client_id=field_client_id,
                            field_object_id=field_object_id,
                            locale_id=locale_id,
                            additional_metadata=additional_metadata,
                            parent_client_id=parent_client_id,
                            parent_object_id=parent_object_id,
                            content = content,
                            )
    if upper_level:
        dbentity.upper_level = upper_level
    dbentity.publishingentity.accepted = True
    if save_object:
        CACHE.set(objects = [dbentity, ], DBSession=DBSession)
        # DBSession.add(dbentity)
        # DBSession.flush()
    return dbentity

def graphene_to_dicts(starling_dictionaries):
    result = []
    for dictionary in starling_dictionaries:
        dictionary = dict(dictionary)
        fmap = [dict(x) for x in dictionary.get("field_map")]
        dictionary["field_map"] = fmap
        result.append(dictionary)

    return result

def convert(
    info,
    starling_dictionaries,
    cache_kwargs,
    sqlalchemy_url,
    task_key,
    synchronous = False):

    ids = [info.context["client_id"], None]
    locale_id = info.context.get('locale_id')

    convert_f = (
        convert_start_sync if synchronous else
        convert_start_async.delay)

    convert_f(
        ids,
        graphene_to_dicts(starling_dictionaries),
        cache_kwargs,
        sqlalchemy_url,
        task_key)

    return True


class StarlingField(graphene.InputObjectType):
    starling_name = graphene.String(required=True)
    starling_type = graphene.Int(required=True)
    field_id = LingvodocID(required=True)
    fake_id = graphene.String()
    link_fake_id = LingvodocID() #graphene.String()

class StarlingDictionary(graphene.InputObjectType):
    blob_id = LingvodocID()
    parent_id = LingvodocID(required=True)
    perspective_gist_id = LingvodocID()
    perspective_atoms = graphene.List(ObjectVal)
    translation_gist_id = LingvodocID()
    translation_atoms = graphene.List(ObjectVal)
    field_map = graphene.List(StarlingField, required=True)
    add_etymology = graphene.Boolean(required=True)
    license = graphene.String()


class GqlStarling(graphene.Mutation):
    triumph = graphene.Boolean()
    #convert_starling

    class Arguments:
        starling_dictionaries=graphene.List(StarlingDictionary)
        synchronous=graphene.Boolean()

    def mutate(root, info, **args):
        starling_dictionaries = args.get("starling_dictionaries")
        if not starling_dictionaries:
            raise ResponseError(message="The starling_dictionaries variable is not set")
        cache_kwargs = info.context["request"].registry.settings["cache_kwargs"]
        sqlalchemy_url = info.context["request"].registry.settings["sqlalchemy.url"]
        task_names = []
        for st_dict in starling_dictionaries:
            # TODO: fix
            task_names.append(st_dict.get("translation_atoms")[0].get("content"))
        name = ",".join(task_names)
        user_id = dbClient.get_user_by_client_id(info.context["client_id"]).id
        task = TaskStatus(user_id, "Starling dictionary conversion", name, 10)

        convert(
            info,
            starling_dictionaries,
            cache_kwargs,
            sqlalchemy_url,
            task.key,
            synchronous = args.get('synchronous', False))

        return GqlStarling(triumph=True)







import cProfile
from io import StringIO
import pstats
import contextlib

class ObjectId:

    object_id_counter = 0

    @property
    def next(self):
        self.object_id_counter += 1
        return self.object_id_counter


    def id_pair(self, client_id):
        return [client_id, self.next]





#@contextlib.contextmanager
def convert_start(ids, starling_dictionaries, cache_kwargs, sqlalchemy_url, task_key):
    """
        mutation myQuery($starling_dictionaries: [StarlingDictionary]) {
      convert_starling(starling_dictionaries: $starling_dictionaries){
            triumph
        }
    }
    """
    # pr = cProfile.Profile()
    # pr.enable()
    from lingvodoc.cache.caching import initialize_cache
    initialize_cache(cache_kwargs)
    global CACHE
    from lingvodoc.cache.caching import CACHE
    try:
        with transaction.manager:
            n = 10
            timestamp = (
                time.asctime(time.gmtime()) + ''.join(
                    random.SystemRandom().choice(string.ascii_uppercase + string.digits) for c in range(n)))


            task_status = TaskStatus.get_from_cache(task_key)
            task_status.set(1, 1, "Preparing")
            engine = create_engine(sqlalchemy_url)
            #DBSession.remove()
            DBSession.configure(bind=engine, autoflush=False)
            obj_id = ObjectId()

            old_client_id = ids[0]
            old_client = DBSession.query(dbClient).filter_by(id=old_client_id).first()
            #user_id = old_client.user_id
            user = DBSession.query(dbUser).filter_by(id=old_client.user_id).first()
            client = dbClient(user_id=user.id)
            user.clients.append(client)
            DBSession.add(client)
            DBSession.flush()
            client_id = client.id
            id_to_field_dict = get_id_to_field_dict()
            etymology_field_id = id_to_field_dict.get("Etymology")
            relation_field_id = id_to_field_dict.get("Relation")


            link_col_to_blob = collections.defaultdict(dict)

            dictionary_id_links = collections.defaultdict(list)
            task_status.set(2, 5, "Checking links")
            fake_link_to_field= {}#collections.defaultdict(list)
            for starling_dictionary in starling_dictionaries:
                fields = starling_dictionary.get("field_map")
                blob_id_as_fake_id = starling_dictionary.get("blob_id")
                for field in fields:
                    link_fake_id = field.get("link_fake_id")
                    if not link_fake_id:
                        continue
                    # dictionary_id_links[tuple(blob_id_as_fake_id)].append(tuple(link_fake_id))

                    fake_link_to_field[tuple(link_fake_id)] = [x for x in fields if x["starling_type"] == 2]
                    link_col_to_blob[tuple(blob_id_as_fake_id)][field.get("starling_name")] = tuple(link_fake_id)
            # crutch
            for starling_dictionary in starling_dictionaries:
                fields = starling_dictionary.get("field_map")
                blob_id = tuple(starling_dictionary.get("blob_id"))
                if blob_id in fake_link_to_field:
                    old_fields = fake_link_to_field[blob_id]
                    for old_field in old_fields:
                        fake_field = old_field.copy()
                        fake_field["starling_type"] = 4
                        if fake_field["field_id"] in [x.get("field_id") for x in fields]:
                            continue
                        fields.append(fake_field)
                        starling_dictionary["field_map"] = fields
            #

            task_status.set(4, 50, "uploading...")
            blob_to_perspective = dict()
            perspective_column_dict = {}

            persp_to_lexentry = collections.defaultdict(dict)
            copy_field_dict = collections.defaultdict(dict)
            keep_field_dict = collections.defaultdict(dict)
            link_field_dict = collections.defaultdict(dict)
            task_status_counter = 0
            etymology_set = set()
            etymology_blobs = set()
            for starling_dictionary in starling_dictionaries:
                task_status_counter += 1
                blob_id = tuple(starling_dictionary.get("blob_id"))
                blob = DBSession.query(dbUserBlobs).filter_by(client_id=blob_id[0], object_id=blob_id[1]).first()

                column_dict, starling_flag = csv_to_columns(blob.real_storage_path, blob.content)
                perspective_column_dict[blob_id] = column_dict, starling_flag

                atoms_to_create = starling_dictionary.get("translation_atoms")
                if atoms_to_create:
                    content = atoms_to_create[0].get("content")
                    task_status.set(4, 60, "%s (%s/%s)" % (content, task_status_counter, len(starling_dictionaries)))
                dictionary_translation_gist_id = create_gists_with_atoms(atoms_to_create,
                                                                         None,
                                                                         (old_client_id, None),
                                                                         gist_type="Dictionary")
                parent_id = starling_dictionary.get("parent_id")

                dbdictionary_obj = (

                    create_dbdictionary(
                        id = obj_id.id_pair(client_id),
                        parent_id = parent_id,
                        translation_gist_id = dictionary_translation_gist_id,
                        add_group = True,
                        additional_metadata = {
                            'license': starling_dictionary.get('license') or 'proprietary'}))

                atoms_to_create = [{"locale_id": 2, "content": "starling_source"}]
                persp_translation_gist_id = create_gists_with_atoms(atoms_to_create,
                                                                    None,
                                                                    (old_client_id, None),
                                                                    gist_type="Perspective")
                dictionary_id = [dbdictionary_obj.client_id, dbdictionary_obj.object_id]
                new_persp = create_perspective(id=obj_id.id_pair(client_id),
                                        parent_id=dictionary_id,  # TODO: use all object attrs
                                        translation_gist_id=persp_translation_gist_id,
                                        add_group=True
                                        )

                blob_to_perspective[blob_id] = new_persp
                perspective_id = [new_persp.client_id, new_persp.object_id]
                fields = starling_dictionary.get("field_map")
                starlingname_to_column = collections.OrderedDict()

                position_counter = 1

                # perspective:field_id

                fields_fix = list()
                for field in fields:
                    starling_type = field.get("starling_type")
                    field_id = tuple(field.get("field_id"))
                    starling_name = field.get("starling_name")
                    if starling_type == 1:
                        if field_id in fields_fix:
                            starlingname_to_column[starling_name] = field_id
                            keep_field_dict[blob_id][field_id] = starling_name
                            continue
                        else:
                            fields_fix.append(field_id)
                        persp_to_field = create_dictionary_persp_to_field(id=obj_id.id_pair(client_id),
                                         parent_id=perspective_id,
                                         field_id=field_id,
                                         upper_level=None,
                                         link_id=None,
                                         position=position_counter
                                         )
                        position_counter += 1
                        starlingname_to_column[starling_name] = field_id
                        keep_field_dict[blob_id][field_id] = starling_name
                    elif starling_type == 2:
                        if field_id in fields_fix:
                            starlingname_to_column[starling_name] = field_id
                            keep_field_dict[blob_id][field_id] = starling_name
                            continue
                        else:
                            fields_fix.append(field_id)
                        # copy
                        persp_to_field = create_dictionary_persp_to_field(id=obj_id.id_pair(client_id),
                                         parent_id=perspective_id,
                                         field_id=field_id,
                                         upper_level=None,
                                         link_id=None,
                                         position=position_counter
                                         )
                        position_counter += 1
                        starlingname_to_column[starling_name] = field_id
                        copy_field_dict[blob_id][field_id] = starling_name
                    elif starling_type == 4:
                        persp_to_field = create_dictionary_persp_to_field(id=obj_id.id_pair(client_id),
                                         parent_id=perspective_id,
                                         field_id=field_id,
                                         upper_level=None,
                                         link_id=None,
                                         position=position_counter
                                         )
                        position_counter += 1


                add_etymology = starling_dictionary.get("add_etymology")
                if add_etymology:
                    persp_to_field = create_dictionary_persp_to_field(id=obj_id.id_pair(client_id),
                                     parent_id=perspective_id,
                                     field_id=etymology_field_id,
                                     upper_level=None,
                                     link_id=None,
                                     position=position_counter
                                     )
                    position_counter += 1
                    etymology_blobs.add(blob_id)

                if starling_flag:

                    persp_to_field = create_dictionary_persp_to_field(id=obj_id.id_pair(client_id),
                             parent_id=perspective_id,
                             field_id=relation_field_id,
                             upper_level=None,
                             link_id=None,
                             position=position_counter
                             )

                fields_marked_as_links = [x.get("starling_name") for x in fields if x.get("starling_type") == 3]
                link_field_dict[blob_id] = fields_marked_as_links

                # blob_link -> perspective_link
                csv_data = column_dict
                collist = list(starlingname_to_column)
                le_list = []

                for number in csv_data["NUMBER"]:  # range()
                    le_client_id, le_object_id = client_id, obj_id.next
                    lexentr = dbLexicalEntry(object_id=le_object_id,
                                             client_id=le_client_id,
                                             parent_client_id=perspective_id[0],
                                             parent_object_id=perspective_id[1])
                    DBSession.add(lexentr)
                    le_list.append((le_client_id, le_object_id))
                    persp_to_lexentry[blob_id][number] = (le_client_id, le_object_id)
                    #number += 1
                #DBSession.bulk_save_objects(le_list)

                i = 0
                for lexentr_tuple in le_list:
                    for starling_column_name in starlingname_to_column:
                        field_id = starlingname_to_column[starling_column_name]
                        col_data = csv_data[starling_column_name][i]
                        if col_data:
                            new_ent = create_entity(id=obj_id.id_pair(client_id),
                                parent_id=lexentr_tuple,
                                additional_metadata=None,
                                field_id=field_id,
                                self_id=None,
                                link_id=None, #
                                locale_id=2,
                                filename=None,
                                content=col_data,
                                registry=None,
                                request=None,
                                save_object=False)
                            CACHE.set(objects = [new_ent, ], DBSession=DBSession)
                            # DBSession.add(new_ent)
                    i+=1
            task_status.set(5, 70, "link, spread" )
            tag_list = list()
            d = dict()
            for starling_dictionary in starling_dictionaries:
                blob_id = tuple(starling_dictionary.get("blob_id"))
                # if blob_id not in dictionary_id_links:
                #     continue
                if blob_id not in link_col_to_blob:
                    continue
                #persp = blob_to_perspective[blob_id]
                copy_field_to_starlig = copy_field_dict[blob_id]
                column_dict, starling_flag = perspective_column_dict[blob_id]

                le_links = defaultdict(dict)
                for num_col in link_field_dict[blob_id]:
                    if num_col in link_col_to_blob[blob_id].keys():
                        new_blob_link = link_col_to_blob[blob_id][num_col]
                        link_numbers = list(zip(
                                           [int(x) for x in column_dict["NUMBER"]],
                                           [int(x) for x in column_dict[num_col]])
                        )
                        for link_pair in link_numbers:
                            # TODO: fix
                            le_numb = link_pair[1]
                            if not le_numb:
                                continue
                            if not le_numb in persp_to_lexentry[new_blob_link]:
                                #raise ResponseError(message="%s line not found (blob_id = %s)" % (le_numb, str(new_blob_link)))
                                continue
                            link_lexical_entry = persp_to_lexentry[new_blob_link][le_numb]
                            lexical_entry_ids = persp_to_lexentry[blob_id][link_pair[0]]
                            perspective = blob_to_perspective[new_blob_link]
                            new_ent = create_entity(id=obj_id.id_pair(client_id),
                                                    parent_id=lexical_entry_ids,
                                                    additional_metadata={"link_perspective_id":[perspective.client_id, perspective.object_id]},
                                                    field_id=relation_field_id,
                                                    self_id=None,
                                                    link_id=link_lexical_entry, #
                                                    locale_id=2,
                                                    filename=None,
                                                    content=None,
                                                    registry=None,
                                                    request=None,
                                                    save_object=True)
                            # DBSession.add(new_ent)
                            le_links[lexical_entry_ids][new_blob_link] = link_lexical_entry
                            # etymology tag
                            #"""
                            if starling_dictionary.get("add_etymology"):
                                if not new_blob_link in etymology_blobs:
                                    continue
                                tag = "%s_%s_%s_%s" % (num_col, str(new_blob_link), str(link_lexical_entry), timestamp)
                                if not tag in etymology_set:
                                    etymology_set.add(tag)
                                    tag_entity = dbEntity(client_id=client.id, object_id=obj_id.next,
                                        field_client_id=etymology_field_id[0], field_object_id=etymology_field_id[1], parent_client_id=link_lexical_entry[0], parent_object_id=link_lexical_entry[1], content=tag)
                                    # additional_metadata num_col
                                    tag_entity.publishingentity.accepted = True
                                    # DBSession.add(tag_entity)
                                    CACHE.set(objects = [tag_entity, ], DBSession=DBSession)
                                tag_entity = dbEntity(client_id=client.id, object_id=obj_id.next,
                                    field_client_id=etymology_field_id[0], field_object_id=etymology_field_id[1], parent_client_id=lexical_entry_ids[0], parent_object_id=lexical_entry_ids[1], content=tag)
                                tag_entity.publishingentity.accepted = True
                                # DBSession.add(tag_entity)
                                CACHE.set(objects = [tag_entity, ], DBSession=DBSession)



                for field_id in copy_field_to_starlig:
                    starling_field = copy_field_to_starlig[field_id]
                    word_list = column_dict[starling_field]
                    numb_list = iter(column_dict["NUMBER"])
                    i = 0
                    for word in word_list:
                        i = next(numb_list)
                        #word = word_list[i]
                        lexical_entry_ids = persp_to_lexentry[blob_id][i]
                        if lexical_entry_ids in le_links:
                            for other_blob in le_links[lexical_entry_ids]:
                                link_lexical_entry = le_links[lexical_entry_ids][other_blob]
                                if word:
                                    new_ent = create_entity(id=obj_id.id_pair(client_id),
                                        parent_id=link_lexical_entry,
                                        additional_metadata=None,
                                        field_id=field_id,
                                        self_id=None,
                                        link_id=None, #
                                        locale_id=2,
                                        filename=None,
                                        content=word,
                                        registry=None,
                                        request=None,
                                        save_object=False)
                                    # DBSession.add(new_ent)
                                    CACHE.set(objects = [new_ent, ], DBSession=DBSession)
                        #i+=1
            DBSession.flush()

    except Exception as exception:

        traceback_string = (

            ''.join(
                traceback.format_exception(
                    exception, exception, exception.__traceback__))[:-1])

        log.warning('\nconvert_starling: exception')
        log.warning('\n' + traceback_string)

        task_status.set(None, -1,
            'Convertion failed, exception:\n' + traceback_string)

    else:
        task_status.set(10, 100, "Finished", "")

    # pr.disable()
    # s = StringIO()
    # ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    # ps.print_stats()
    # uncomment this to see who's calling what
    # ps.print_callers()
    # print(s.getvalue())

@celery.task
def convert_start_async(ids, starling_dictionaries, cache_kwargs, sqlalchemy_url, task_key):
    convert_start(ids, starling_dictionaries, cache_kwargs, sqlalchemy_url, task_key)

def convert_start_sync(ids, starling_dictionaries, cache_kwargs, sqlalchemy_url, task_key):
    convert_start(ids, starling_dictionaries, cache_kwargs, sqlalchemy_url, task_key)
