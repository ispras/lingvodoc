import transaction
from collections import defaultdict
import logging
import traceback
import re
import urllib

import graphene
from sqlalchemy import create_engine
from lingvodoc.queue.celery import celery

from lingvodoc.cache.caching import TaskStatus, initialize_cache
from lingvodoc.models import (
    Client as dbClient,
    DBSession,
    ENGLISH_LOCALE,
    Entity as dbEntity,
    LexicalEntry as dbLexicalEntry,
    RUSSIAN_LOCALE,
    User as dbUser,
    UserBlobs as dbUserBlobs,
)
from lingvodoc.utils.creation import create_gists_with_atoms, update_metadata, add_user_to_group
from lingvodoc.schema.gql_holders import (
    ResponseError,
    ObjectVal,
    LingvodocID
)

from lingvodoc.utils.lexgraph_marker import get_lexgraph_list
from lingvodoc.utils.creation import (create_perspective,
                                      create_dbdictionary,
                                      create_dictionary_persp_to_field)

from lingvodoc.utils.search import translation_gist_search
from lingvodoc.utils.corpus_converter import get_field_id

# Setting up logging.
log = logging.getLogger(__name__)

#order_field_id = get_field_id('Order')

def txt_to_column(path, url, columns_dict=defaultdict(list), column=None):

    try:
        txt_file = (
            open(path, 'rb')
                .read()
                .decode('utf-8-sig', 'ignore'))

    except FileNotFoundError:
        txt_file = (
            urllib.request.urlopen(
                urllib.parse.quote(url, safe='/:'))
                .read()
                .decode('utf-8-sig', 'ignore'))

    page = r'\d+[ab]?'
    line = r'\d+'
    tib_end = r'\|\|+'
    oir_end = r':+'

    position_marker = re.compile(f'\[{page}:{line}\]|'
                                 f'\[{page}\]')

    line_marker = re.compile(f'\({line}\)')

    sentence_marker = re.compile(f'{tib_end}|'
                                 f'{oir_end}|'
                                 f'\[{tib_end}\]|'
                                 f'\[{oir_end}\]')

    if not (txt_start := re.search(position_marker, txt_file)):
        raise ValueError("Be careful, meaningful text must start with a marker like '[12a:23]' or '[12b]' or just '[12]'.")

    txt_file = txt_file[txt_start.start():]
    txt_file = txt_file.replace('\r\n', ' ').replace('\n', ' ').replace('  ', ' ')
    # Replace colons in markers to another symbol to differ from colons in text
    txt_file = re.sub(r':(\d)', r'#\1', txt_file)

    if not (sentences := re.split(sentence_marker, txt_file)[:-1]):
        raise ValueError("No one sentence is found. Be careful, sentences must end with '||' or ':' simbols. These symbols may be closed in square brackets.")

    if not column:
        column = path.split('/')[-1]

    if column in columns_dict:
        raise ValueError("Different columns in the table have identical names.")

    col_num = len(columns_dict)

    count = 0
    for x in sentences:
        line = x.replace('#', ':').strip()

        if not line:
            continue

        columns_dict[column].append(line)
        count += 1

    return columns_dict, count


def txt_to_parallel_columns(columns_inf):
    columns_dict = defaultdict(list)

    # Init field to be the first one in result table
    order_field_id = get_field_id('Order')
    columns_dict[order_field_id] = []

    max_count = 0
    for column_inf in columns_inf:
        blob_id = tuple(column_inf.get("blob_id"))
        field_id = tuple(column_inf.field_map.get("field_id"))
        blob = DBSession.query(dbUserBlobs).filter_by(client_id=blob_id[0], object_id=blob_id[1]).first()

        columns_dict, count = txt_to_column(blob.real_storage_path, blob.content, columns_dict, field_id)
        if count > max_count:
            max_count = count

    columns_dict[order_field_id] = get_lexgraph_list(max_count)

    return columns_dict


def join_sentences(columns_dict):
    order_field_id = get_field_id('Order')
    iterators = {}
    for f_id, lines in columns_dict.items():
        if f_id == order_field_id:
            order_it = iter(lines)
        else:
            iterators[f_id] = iter(lines)

    count = 0
    result = defaultdict(list)
    for order in order_it:
        # Read all the columns to find the longest sentence
        sentence = {}
        words = {}
        for f_id, it in iterators.items():
            if not (note := next(it, None)):
                continue
            sentence[f_id] = note
            words[f_id] = len(note.split())

        # To interrupt if all the columns have ended
        if not sentence:
            break

        count += 1
        result[order_field_id].append(order)

        longest = max(words.values())

        for f_id, wrd in words.items():
            while wrd > 0 and longest // wrd > 1:
                if not (note := next(iterators[f_id], None)):
                    break
                sentence[f_id] += f' // {note}'
                wrd += len(note.split())

            result[f_id].append(sentence[f_id])

    return result, count


def create_entity(
    id = None,
    parent_id = None,
    additional_metadata = None,
    field_id = None,
    locale_id = ENGLISH_LOCALE,
    content = None,
    save_object = False):

    if not parent_id:
        raise ResponseError(message="Bad parent ids")

    client_id, object_id = id
    parent_client_id, parent_object_id = parent_id
    field_client_id, field_object_id = field_id if field_id else (None, None)

    # TODO: check permissions if object_id != None

    dbentity = dbEntity(client_id=client_id,
                        object_id=object_id,
                        field_client_id=field_client_id,
                        field_object_id=field_object_id,
                        locale_id=locale_id,
                        additional_metadata=additional_metadata,
                        parent_client_id=parent_client_id,
                        parent_object_id=parent_object_id,
                        content=content)

    dbentity.publishingentity.accepted = True

    if save_object:
        CACHE.set(objects = [dbentity, ], DBSession=DBSession)

    return dbentity


class FieldInf(graphene.InputObjectType):
    column_name = graphene.String()
    field_id = LingvodocID(required=True)


class ColumnInf(graphene.InputObjectType):
    blob_id = LingvodocID(required=True)
    field_map = FieldInf(required=True)


class CorpusInf(graphene.InputObjectType):
    parent_id = LingvodocID(required=True)
    translation_atoms = graphene.List(ObjectVal, required=True)
    license = graphene.String()


class GqlParallelCorpora(graphene.Mutation):
    triumph = graphene.Boolean()

    class Arguments:
        corpus_inf = CorpusInf(required=True)
        columns_inf = graphene.List(ColumnInf, required=True)

    def mutate(root, info, **args):
        corpus_inf = args.get("corpus_inf")
        columns_inf = args.get("columns_inf")
        cache_kwargs = info.context["request"].registry.settings["cache_kwargs"]
        sqlalchemy_url = info.context["request"].registry.settings["sqlalchemy.url"]

        default_name = "corpus #1"
        translation_atoms = corpus_inf.get("translation_atoms")
        task_name = translation_atoms[0].get('content', default_name) if translation_atoms else default_name

        user_id = dbClient.get_user_by_client_id(info.context["client_id"]).id
        task = TaskStatus(user_id, "Txt corpora conversion", task_name, 5)

        convert_start( #.delay(
            [info.context["client_id"], None],
            corpus_inf,
            columns_inf,
            cache_kwargs,
            sqlalchemy_url,
            task.key)

        return GqlParallelCorpora(triumph=True)


class ObjectId:

    object_id_counter = 0

    @property
    def next(self):
        self.object_id_counter += 1
        return self.object_id_counter

    def id_pair(self, client_id):
        return [client_id, self.next]


def get_translation_gist_id(translation_atoms, client_id, gist_type):
    if (translation_gist := translation_gist_search(translation_atoms[0].get('content'),
                                                    gist_type=gist_type)):
        translation_gist_id = translation_gist.id
        #print(f"Found {gist_type} gist: {translation_gist_id}")
    else:
        translation_gist_id = create_gists_with_atoms(translation_atoms,
                                                      None,
                                                      (client_id, None),
                                                      gist_type=gist_type)
    return translation_gist_id


#@celery.task
def convert_start(ids, corpus_inf, columns_inf, cache_kwargs, sqlalchemy_url, task_key):
    """
    TODO: change the description below
        mutation myQuery($starling_dictionaries: [StarlingDictionary]) {
      convert_starling(starling_dictionaries: $starling_dictionaries){
            triumph
        }
    }
    """
    initialize_cache(cache_kwargs)
    global CACHE
    from lingvodoc.cache.caching import CACHE
    try:
        with transaction.manager:
            task_status = TaskStatus.get_from_cache(task_key)

            task_status.set(1, 1, "Preparing")

            engine = create_engine(sqlalchemy_url)
            DBSession.configure(bind=engine, autoflush=False)
            obj_id = ObjectId()
            old_client_id = ids[0]
            old_client = DBSession.query(dbClient).filter_by(id=old_client_id).first()
            user = DBSession.query(dbUser).filter_by(id=old_client.user_id).first()
            client = dbClient(user_id=user.id)
            DBSession.add(client)
            DBSession.flush()
            client_id = client.id

            task_status.set(2, 20, "converting...")

            # Getting txt data, checking that the txt file is Lingvodoc-valid.
            columns_dict, max_count = join_sentences(txt_to_parallel_columns(columns_inf))

            task_status.set(3, 50, "creating dictionary and perspective...")

            parent_id = corpus_inf.get("parent_id")
            dbdictionary_obj = (
                create_dbdictionary(
                    id=obj_id.id_pair(client_id),
                    parent_id=parent_id,
                    translation_gist_id=
                        get_translation_gist_id(corpus_inf.get("translation_atoms"), old_client_id, "Dictionary"),
                    add_group=True,
                    additional_metadata={
                        'license': corpus_inf.get('license') or 'proprietary'
                    }))

            dictionary_id = [dbdictionary_obj.client_id, dbdictionary_obj.object_id]
            translation_atoms = [
                {"locale_id": ENGLISH_LOCALE, "content": "Parallel corpora"},
                {"locale_id": RUSSIAN_LOCALE, "content": "Параллельные корпуса"}]

            new_persp = (
                create_perspective(
                    id=obj_id.id_pair(client_id),
                    parent_id=dictionary_id,  # TODO: use all object attrs
                    translation_gist_id=
                        get_translation_gist_id(translation_atoms, old_client_id, "Perspective"),
                    add_group=True))

            perspective_id = [new_persp.client_id, new_persp.object_id]

            for position, field_id in enumerate(columns_dict):
                create_dictionary_persp_to_field(id=obj_id.id_pair(client_id),
                                                 parent_id=perspective_id,
                                                 field_id=field_id,
                                                 upper_level=None,
                                                 link_id=None,
                                                 position=position)

            task_status.set(4, 70, "uploading...")

            for i in range(max_count):
                le_client_id, le_object_id = client_id, obj_id.next
                lexentr = dbLexicalEntry(object_id=le_object_id,
                                         client_id=le_client_id,
                                         parent_client_id=perspective_id[0],
                                         parent_object_id=perspective_id[1])
                DBSession.add(lexentr)
                lexentr_tuple = le_client_id, le_object_id

                for field_id, contents in columns_dict.items():
                    if i >= len(contents):
                        continue

                    content = contents[i]

                    if content:
                        new_ent = (
                            create_entity(
                                id = obj_id.id_pair(client_id),
                                parent_id = lexentr_tuple,
                                additional_metadata = None,
                                field_id = field_id,
                                locale_id = ENGLISH_LOCALE,
                                content = content,
                                save_object = False))

                        CACHE.set(objects = [new_ent, ], DBSession=DBSession)
                        # DBSession.add(new_ent)
        DBSession.flush()

    except Exception as exception:
        traceback_string = (
            ''.join(
                traceback.format_exception(
                    exception, exception, exception.__traceback__))[:-1])

        log.warning('\nconvert_txt_corpora: exception')
        log.warning('\n' + traceback_string)

        task_status.set(None, -1,
            'Convertion failed, exception:\n' + traceback_string)

    else:
        task_status.set(5, 100, "Finished", "")
