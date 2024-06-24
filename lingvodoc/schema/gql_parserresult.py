
# Standard library imports.

import collections
import datetime
import hashlib
import io
import json
import logging
import os
import pprint
import re
import shutil
import tempfile
import time
import traceback
import unicodedata
import urllib
import zipfile

# Library imports.

from bs4 import BeautifulSoup

import graphene

from graphql.language.ast import (
    BooleanValue,
    IntValue,
    ListValue)

import minio

from sqlalchemy import (
    create_engine,
    tuple_,
    union)

import transaction
import xlsxwriter

from zope.sqlalchemy import mark_changed

# Project imports.

from lingvodoc.cache.caching import (
    initialize_cache,
    TaskStatus)

import lingvodoc.models as models

from lingvodoc.models import (
    Client,
    DBSession,
    DictionaryPerspective as dbPerspective,
    Entity as dbEntity,
    ENGLISH_LOCALE,
    Language as dbLanguage,
    LexicalEntry as dbLexicalEntry,
    Parser as dbParser,
    ParserResult as dbParserResult,
    PublishingEntity as dbPublishingEntity,
    User as dbUser,
    ValencyAnnotationData as dbValencyAnnotationData,
    ValencyEafData as dbValencyEafData,
    ValencyInstanceData as dbValencyInstanceData,
    ValencyMergeData as dbValencyMergeData,
    ValencyMergeIdSequence as dbValencyMergeIdSequence,
    ValencyParserData as dbValencyParserData,
    ValencySentenceData as dbValencySentenceData,
    ValencySourceData as dbValencySourceData)

from lingvodoc.queue.celery import celery

from lingvodoc.schema.gql_entity import is_subject_for_parsing

from lingvodoc.schema.gql_holders import (
    AdditionalMetadata,
    client_id_check,
    CompositeIdHolder,
    CreatedAt,
    fetch_object,
    LingvodocID,
    LingvodocObjectType,
    MarkedForDeletion,
    ObjectVal,
    ResponseError)

from lingvodoc.schema.gql_parser import ParameterType

from lingvodoc.scripts import elan_parser

import lingvodoc.scripts.export_parser_result as export_parser_result
import lingvodoc.scripts.valency as valency
import lingvodoc.scripts.valency_verb_cases as valency_verb_cases

import lingvodoc.utils as utils

from lingvodoc.utils.creation import (
    create_parser_result,
    json_to_html,
    async_create_parser_result)

import lingvodoc.utils.doc_parser as ParseMethods

from lingvodoc.utils.elan_functions import tgt_to_eaf

from lingvodoc.views.v2.utils import (
    as_storage_file,
    storage_file)

from pdb import set_trace as A


# Setting up logging.
log = logging.getLogger(__name__)


class ParserResult(LingvodocObjectType):
    dbType = dbParserResult
    arguments = ObjectVal()
    content = graphene.String()
    parser_id = LingvodocID()
    entity_id = LingvodocID()

    class Meta:
        interfaces = (CompositeIdHolder, AdditionalMetadata, CreatedAt, MarkedForDeletion)

    @fetch_object('arguments')
    def resolve_arguments(self, info):
        return self.dbObject.arguments

    @fetch_object('content')
    def resolve_content(self, info):
        return self.dbObject.content

    @fetch_object('parser_id')
    def resolve_parser_id(self, info):
        return [self.dbObject.parser_client_id, self.dbObject.parser_object_id]

    @fetch_object('entity_id')
    def resolve_entity_id(self, info):
        return [self.dbObject.entity_client_id, self.dbObject.entity_object_id]


# create parser result
class ExecuteParser(graphene.Mutation):
    class Arguments:
        id = LingvodocID()
        entity_id = LingvodocID(required=True)
        parser_id = LingvodocID(required=True)
        arguments = ObjectVal()
        async_execution = graphene.Boolean()

    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):

        request = info.context.request
        cur_args = dict()

        # check if client
        client = DBSession.query(Client).filter_by(id=info.context["client_id"]).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           info.context["client_id"])
        else:
            user_id = Client.get_user_by_client_id(client.id).id

        id = args.get('id')
        client_id = id[0] if id else info.context["client_id"]
        object_id = id[1] if id else None
        id = [client_id, object_id]
        entity_id = args.get('entity_id')
        parser_id = args.get('parser_id')
        arguments = args.get('arguments')

        parser = DBSession.query(dbParser).filter_by(client_id=parser_id[0],
                                                         object_id=parser_id[1]).first()
        if not parser:
            raise("No such parser in the system")
        parameters = parser.parameters

        for parameter in parameters:
            if arguments[parameter['name']] == None:
                if parameter['is_mandatory']:
                    raise ("Mandatory parameter " + parameter['name'] +
                    " with id " + parameter['id'] + " was not specified")
            else:
                if parameter['type'] == ParameterType.Int:
                    arguments[parameter['name']] = int(arguments[parameter['name']])
                elif parameter['type'] == ParameterType.String:
                    arguments[parameter['name']] = str(arguments[parameter['name']])
                elif parameter['type'] == ParameterType.Boolean:
                    arguments[parameter['name']] = bool(arguments[parameter['name']])
                elif parameter['type'] == ParameterType.File:
                    response = urllib.request.urlopen(arguments[parameter['name']])
                    tmp_file_id, tmp_filename = tempfile.mkstemp()
                    tmp_file = open(tmp_filename, 'wb')
                    tmp_file.write(response.read())
                    arguments[parameter['name']] = tmp_filename

        entity = (
            dbEntity.get(entity_id))

        if entity is None:
            raise ResponseError(message="No such entity in the system")

        cur_args['id'] = id
        cur_args['entity_id'] = args.get('entity_id')
        cur_args['parser_id'] = args.get('parser_id')
        cur_args['arguments'] = args.get('arguments')
        cur_args["save_object"] = True
        try:
            cur_args["dedoc_url"] = request.registry.settings["dedoc_url"]
        except KeyError:
            raise ResponseError(message="Dedoc server url was not provided in configuration")
        if parser.method.find("apertium") != -1:
            msg = "The path to the folder with Apertium parsers was not provided in configuration"
            try:
                cur_args["apertium_path"] = request.registry.settings["apertium_path"]
            except KeyError:
                raise ResponseError(message=msg)
            if len(cur_args["apertium_path"]) == 0:
                raise ResponseError(message=msg)
        else:
            cur_args["apertium_path"] = ""

        cur_args['storage'] = request.registry.settings['storage']

        async_execution = args.get("async_execution")
        if async_execution == None or async_execution == True:
            task = TaskStatus(user_id, "Parsing entity", "", 2)
            cur_args["task_key"] = task.key
            cur_args["cache_kwargs"] = request.registry.settings["cache_kwargs"]
            cur_args["sqlalchemy_url"] = request.registry.settings["sqlalchemy.url"]
            async_create_parser_result.delay(**cur_args)

        else:
            create_parser_result(**cur_args)

        return ExecuteParser(triumph=True)


def check_permissions(info, parser_result):

    client = DBSession.query(Client).filter_by(id=info.context["client_id"]).first()
    if not client:
        raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                       info.context["client_id"])
    else:
        user_id = Client.get_user_by_client_id(client.id).id

        if user_id != 1:
            perspective_id = (
            DBSession
                .query(
                    dbLexicalEntry.parent_client_id,
                    dbLexicalEntry.parent_object_id)
                .filter(
                    dbLexicalEntry.client_id == dbEntity.parent_client_id,
                    dbLexicalEntry.object_id == dbEntity.parent_object_id,
                    dbEntity.client_id == parser_result.entity_client_id,
                    dbEntity.object_id == parser_result.entity_object_id)
                .first())

        else:
            return

        if not perspective_id:
            raise KeyError(
                    'Failed to get perspective of the parser result.',
                    (parser_result.client_id, parser_result.object_id))
        info.context.acl_check(
                    'delete', 'lexical_entries_and_entities', perspective_id)


class DeleteParserResult(graphene.Mutation):
    class Arguments:
        id = LingvodocID(required=True)

    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):

        id = args.get('id')
        parser_result = DBSession.query(dbParserResult).filter_by(client_id=id[0], object_id=id[1]).first()
        if not parser_result:
            raise ResponseError("No such parser result in the system")

        # If not an admin, checking for permissions.
        check_permissions(info, parser_result)

        parser_result.marked_for_deletion = True
        transaction.commit()

        return DeleteParserResult(triumph=True)


def get_parser_result_for_text(text, parse_method, apertium_path):
    method = getattr(ParseMethods, parse_method)
    if parse_method.find("apertium") != -1:
        result = method(text, apertium_path)
    else:
        result = method(text)
    return result


def get_max_id(soup):
    max_id = 0
    for span in soup.find_all("span"):
        if "id" in span.attrs:
            id = span.attrs["id"]
            if id.isdecimal():
                int_id = int(id)
                if int_id > max_id:
                    max_id = int_id
    return max_id


def parse_and_insert_element(old_result, element_id, parse_method, apertium_path):
    old_result_soup = BeautifulSoup(old_result, 'html.parser')
    selector_arg = "span[id^=\"" + element_id + "\"]"
    element_soup = old_result_soup.select(selector_arg)[0]
    if not element_soup:
        return old_result
    element_text = ""
    for child in element_soup.children:
        if str(type(child)).find("NavigableString") != -1:
            element_text = child
    if not element_text:
        return old_result
    parser_result = get_parser_result_for_text(element_text, parse_method, apertium_path)
    parser_result_soup = BeautifulSoup(parser_result, 'html.parser')
    if not parser_result_soup.span:
        return old_result
    max_id = get_max_id(old_result_soup)
    parser_result_soup.span["id"] = element_id
    for span in parser_result_soup.span.find_all("span"):
        span["id"] = str(max_id + 1)
        max_id += 1
    if "user" in element_soup["class"]:
        parser_result_soup.span["class"].append("user")
    if element_soup.span:
        for span in element_soup.find_all("span"):
            if ("user" in span["class"] or "approved" in span["class"]) and "result" in span["class"]:
                parser_result_soup.span.append(span)
                if "approved" in span["class"] and "verified" not in parser_result_soup.span["class"]:
                    parser_result_soup.span["class"].append("verified")
    old_result_soup.select(selector_arg)[0].replace_with(parser_result_soup)
    return str(old_result_soup)


def reexecute_parser(old_result, parse_method, apertium_path):
    ESC_PAT = "$id$"
    old_result_soup = BeautifulSoup(old_result, 'html.parser')
    elements = old_result_soup.select('[class*="verified"]')
    elements_to_skip = list()
    index_skip = 0
    for element in elements:
        if "verified" in element["class"] or "user" in element["class"]:
            element_to_skip = element.replace_with(ESC_PAT + str(index_skip) + ESC_PAT)
            elements_to_skip.append(element_to_skip)
            index_skip += 1

    def extract_text_from_tag(tag):
        result = ""
        if str(type(tag)).find("NavigableString") != -1:
            result = tag
        elif str(type(tag)).find("Tag") != -1 and tag.name in ["strong", "head"]:
            pass
        elif str(type(tag)).find("Tag") != -1 and tag.name in ["html", "body"]:
            for child in tag.children:
                result += extract_text_from_tag(child)
        elif str(type(tag)).find("Tag") != -1 and tag.name == "span":
            if "class" in tag.attrs and "unverified" in tag["class"] and tag.children:
                for child in tag.children:
                    if str(type(child)).find("NavigableString") != -1:
                        result = child
        elif str(type(tag)).find("Tag") != -1:
            if tag.children:
                for child in tag.children:
                    child.replace_with(extract_text_from_tag(child))
            result = str(tag).replace("&lt;", "<").replace("&gt;", ">")
        return result

    text = ""
    for child in old_result_soup.contents:
        text += extract_text_from_tag(child)

    new_result = get_parser_result_for_text(text, parse_method, apertium_path)
    max_id = get_max_id(BeautifulSoup(new_result, "html.parser"))

    def replace(match):
        i = len(ESC_PAT)
        index = int(match.group(0)[i:-i])
        element = elements_to_skip[index]
        nonlocal max_id
        max_id += 1
        element["id"] = str(max_id)
        for child in element.children:
            if str(type(child)).find("Tag") == -1 or "id" not in child.attrs:
                continue
            if child["id"].find('!') != -1:
                child["id"] = element["id"] + '!'*child["id"].count('!')
            else:
                max_id += 1
                child["id"] = str(max_id)
        return str(element)

    new_result = re.sub(r"\$id\$(\d*)\$id\$", replace, new_result)
    return new_result


@celery.task
def async_reexecute_parser(parser_result_id, content, parse_method,
                           task_key, cache_kwargs, sqlalchemy_url, apertium_path):

    engine = create_engine(sqlalchemy_url)
    DBSession.configure(bind=engine)
    initialize_cache(cache_kwargs)
    task_status = TaskStatus.get_from_cache(task_key)
    parser_result = DBSession.query(dbParserResult).filter_by(client_id=parser_result_id[0],
                                                              object_id=parser_result_id[1]).first()
    entity = DBSession.query(dbEntity).filter_by(client_id=parser_result.entity.client_id,
                                                 object_id=parser_result.entity.object_id).first()
    filename = entity.content.split('/')[-1]
    task_status.set(1, 5, "Reparsing of file " + filename + " started")

    try:

        parser_result.content = reexecute_parser(content, parse_method, apertium_path)
        transaction.commit()

    except Exception as err:
        task_status.set(None, -1, "Reparsing of file " + filename + " failed: %s" % str(err))
        raise

    task_status.set(2, 100, "Reparsing of file " + filename + " finished")


class UpdateParserResult(graphene.Mutation):
    class Arguments:
        id = LingvodocID(required=True)
        element_id = graphene.String()
        content = graphene.String()
        content_fmt = graphene.String()
        reexecute = graphene.Boolean()
        synchronous = graphene.Boolean()

    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):

        parser_result_id = args.get('id')
        element_id = args.get('element_id')
        content_from_args = args.get('content')
        content_fmt = args.get('content_fmt', 'html')
        # incoming content may have json format
        if len(content_from_args) > 0 and content_fmt == 'json':
            content_from_args = json_to_html(json.loads(content_from_args))
        reexecute = args.get('reexecute')
        synchronous = args.get('synchronous', False)

        request = info.context.request

        parser_result = DBSession.query(dbParserResult).filter_by(client_id=parser_result_id[0],
                                                        object_id=parser_result_id[1]).first()
        if not parser_result or parser_result.marked_for_deletion:
            raise ResponseError("No such parser result in the system")

        # If not an admin, checking for permissions.
        check_permissions(info, parser_result)

        if content_from_args and not element_id:
            parser_result.content = content_from_args[:]
            transaction.commit()
            return UpdateParserResult(triumph=True)

        if element_id or reexecute:
            parser = DBSession.query(dbParser).filter_by(client_id=parser_result.parser.client_id,
                                                         object_id=parser_result.parser.object_id).first()
            if not parser:
                raise ResponseError("No such parser in the system")

            if content_from_args:
                content = content_from_args
            else:
                content = parser_result.content

            apertium_path = ""
            if parser.method.find("apertium") != -1:
                msg = "The path to the folder with Apertium parsers was not provided in configuration"
                try:
                    apertium_path = request.registry.settings["apertium_path"]
                except KeyError:
                    raise ResponseError(message=msg)
                if len(apertium_path) == 0:
                    raise ResponseError(message=msg)

            if reexecute:

                cur_args = dict()
                cur_args['parser_result_id'] = parser_result_id
                cur_args['content'] = content
                cur_args['parse_method'] = parser.method
                cur_args['apertium_path'] = apertium_path

                if synchronous:
                    raise NotImplementedError

                else:
                    client = DBSession.query(Client).filter_by(id=info.context["client_id"]).first()
                    user_id = Client.get_user_by_client_id(client.id).id
                    task = TaskStatus(user_id, "Reparsing entity", "", 2)
                    cur_args["task_key"] = task.key
                    cur_args["cache_kwargs"] = request.registry.settings["cache_kwargs"]
                    cur_args["sqlalchemy_url"] = request.registry.settings["sqlalchemy.url"]
                    async_reexecute_parser.delay(**cur_args)

                return UpdateParserResult(triumph=True)

            parser_result.content = parse_and_insert_element(content, element_id, parser.method, apertium_path)
            transaction.commit()

        return UpdateParserResult(triumph=True)


@celery.task
def async_valency_compute(
    perspective_id,
    debug_flag,
    full_name,
    task_key,
    storage,
    cache_kwargs,
    sqlalchemy_url):

    # NOTE: copied from phonology.
    #
    # This is a no-op with current settings, we use it to enable logging inside celery tasks, because
    # somehow this does it, and otherwise we couldn't set it up.

    logging.debug('async_valency')

    engine = create_engine(sqlalchemy_url)
    DBSession.configure(bind = engine)
    initialize_cache(cache_kwargs)

    task_status = TaskStatus.get_from_cache(task_key)

    with transaction.manager:

        try:

            Valency.compute(
                perspective_id,
                debug_flag,
                full_name,
                task_key,
                storage,
                cache_kwargs,
                sqlalchemy_url)

        # Some unknown external exception.

        except Exception as exception:

            traceback_string = ''.join(traceback.format_exception(
                exception, exception, exception.__traceback__))[:-1]

            log.warning(
                'valency \'{}\' {}/{}: exception'.format(
                    full_name,
                    perspective_id[0],
                    perspective_id[1]))

            log.warning(traceback_string)

            if task_status is not None:

                task_status.set(1, 100,
                    'ERROR, exception:\n' + traceback_string)


class Valency(graphene.Mutation):
    """
    Extracts valency info.

    Example:

      curl 'http://localhost:6543/graphql'
        -H 'Content-Type: application/json'
        -H 'Cookie: locale_id=2; auth_tkt=$TOKEN; client_id=$ID'
        --data-raw '{
          "operationName": "valency",
          "variables": {"perspectiveId": [3648,8]},
          "query":
            "mutation valency($perspectiveId: LingvodocID!) {
              valency(perspective_id: $perspectiveId, synchronous: true, debug_flag: true) {
                triumph }}"}'
  
      Set $TOKEN and $ID to valid user authentication info.

      To use in a shell, join into a single line or add escaping backslashes at the end of the lines.
    """

    class Arguments:

        perspective_id = LingvodocID(required = True)

        debug_flag = graphene.Boolean()
        synchronous = graphene.Boolean()

    triumph = graphene.Boolean()

    @staticmethod
    def get_parser_result_data(
        perspective_id,
        debug_flag):

        entry_dict = collections.defaultdict(dict)
        entry_list = []

        entity_list = (

            DBSession

                .query(
                    dbEntity)

                .filter(
                    dbLexicalEntry.parent_client_id == perspective_id[0],
                    dbLexicalEntry.parent_object_id == perspective_id[1],
                    dbLexicalEntry.marked_for_deletion == False,
                    dbEntity.parent_client_id == dbLexicalEntry.client_id,
                    dbEntity.parent_object_id == dbLexicalEntry.object_id,
                    dbEntity.marked_for_deletion == False,
                    dbPublishingEntity.client_id == dbEntity.client_id,
                    dbPublishingEntity.object_id == dbEntity.object_id,
                    dbPublishingEntity.published == True,
                    dbPublishingEntity.accepted == True)

                .order_by(
                    dbLexicalEntry.created_at,
                    dbLexicalEntry.client_id,
                    dbLexicalEntry.object_id,
                    dbEntity.created_at,
                    dbEntity.client_id,
                    dbEntity.object_id)

                .all())

        # Processing entities.

        for entity in entity_list:

            entry_id = (
                entity.parent_id)

            new_entry_flag = (
                entry_id not in entry_dict)

            entry_info_dict = entry_dict[entry_id]

            if new_entry_flag:

                entry_info_dict['parser_result_list'] = []
                entry_list.append(entry_info_dict)

            if entity.field_id == (674, 5):

                entry_info_dict['comment'] = entity.content
                continue

            elif not is_subject_for_parsing(entity.content):
                continue

            log.debug(
                f'\n entity {entity.id}: {repr(entity.content)}')

            parser_result_list = (

                DBSession

                    .query(dbParserResult)

                    .filter_by(
                        entity_client_id = entity.client_id,
                        entity_object_id = entity.object_id,
                        marked_for_deletion = False)

                    .order_by(
                        dbParserResult.created_at,
                        dbParserResult.client_id,
                        dbParserResult.object_id)

                    .all())

            # Processing all parser results of this entity.

            for parser_result_index, parser_result in enumerate(parser_result_list):

                paragraph_list, token_count, _ = (

                    export_parser_result.process_parser_result(
                        parser_result.content,
                        debug_flag = debug_flag,
                        format_flag = True))

                entry_info_dict['parser_result_list'].append({
                    'index': parser_result_index,
                    'id': parser_result.id,
                    'hash': hashlib.sha256(parser_result.content.encode('utf-8')).hexdigest(),
                    'paragraphs': paragraph_list})

        # Adding titles to parser results, if we have them.

        parser_result_list = []

        for entry_info_dict in entry_list:

            title_str = (
                entry_info_dict.get('comment'))

            for parser_result in entry_info_dict['parser_result_list']:

                parser_result['title'] = title_str
                parser_result_list.append(parser_result)

        return parser_result_list

    @staticmethod
    def compute(
        perspective_id,
        debug_flag,
        full_name,
        task_key,
        storage,
        cache_kwargs,
        sqlalchemy_url):

        log.debug(
            '\nvalency \'{}\' {}/{}:'
            '\n  debug_flag: {}'.format(
                full_name,
                perspective_id[0],
                perspective_id[1],
                debug_flag))

        task_status = (
            None if task_key is None else
            TaskStatus.get_from_cache(task_key))

        if task_status:
            task_status.set(1, 0, 'Compiling corpus')

        parser_result_list = (

            Valency.get_parser_result_data(
                perspective_id, debug_flag))

        # If we have no parser results, we won't do anything.

        if not parser_result_list:

            if task_status:
                task_status.set(1, 100, 'Finished, no parser result data')

            return

        # Processing parser results.

        if task_status:
            task_status.set(1, 50, 'Processing data')

        sentence_data = (
            valency.corpus_to_sentences(parser_result_list))

        arx_data = (
            valency.corpus_to_arx(parser_result_list))

        valence_data = (
            valency.sentences_arx_to_valencies(sentence_data, arx_data))

        result_data = (
            valency.sentences_valencies_to_result(sentence_data, valence_data))

        # Saving processed data as zipped JSON.

        current_time = time.time()

        date = datetime.datetime.utcfromtimestamp(current_time)

        zip_date = (
            date.year,
            date.month,
            date.day,
            date.hour,
            date.minute,
            date.second)

        storage_temporary = storage['temporary']

        host = storage_temporary['host']
        bucket = storage_temporary['bucket']

        minio_client = (

            minio.Minio(
                host,
                access_key = storage_temporary['access_key'],
                secret_key = storage_temporary['secret_key'],
                secure = True))

        url_list = []

        for data_value, data_name in [
            (parser_result_list, 'corpus'),
            (sentence_data, 'sentences'),
            (arx_data, 'arx'),
            (valence_data, 'valencies'),
            (result_data, 'result')]:

            data_json_str = (

                json.dumps(
                    data_value,
                    ensure_ascii = False,
                    indent = 2))

            temporary_file = (

                tempfile.NamedTemporaryFile(
                    delete = False))

            zip_file = (

                zipfile.ZipFile(
                    temporary_file, 'w',
                    compression = zipfile.ZIP_DEFLATED,
                    compresslevel = 9))

            zip_info = (
                zipfile.ZipInfo(data_name + '.json', zip_date))

            zip_info.compress_type = zipfile.ZIP_DEFLATED

            zip_file.writestr(
                zip_info, data_json_str)

            zip_file.close()
            temporary_file.close()

            if debug_flag:

                shutil.copy(
                    temporary_file.name,
                    '__valency__' + data_name + '.json.zip')

            object_name = (

                storage_temporary['prefix'] +

                '/'.join((
                    'valency',
                    '{:.6f}'.format(current_time),
                    data_name + '.json.zip')))

            (etag, version_id) = (

                minio_client.fput_object(
                    bucket,
                    object_name,
                    temporary_file.name))

            os.remove(
                temporary_file.name)

            url = (

                '/'.join((
                    'https:/',
                    host,
                    bucket,
                    object_name)))

            url_list.append(url)

            log.debug(
                '\nobject_name: {}'
                '\netag: {}'
                '\nversion_id: {}'
                '\nurl: {}'.format(
                    object_name,
                    etag,
                    version_id,
                    url))

        if task_status:
            task_status.set(1, 100, 'Finished', result_link_list = url_list)

    @staticmethod
    def mutate(
        root,
        info,
        perspective_id,
        debug_flag = False,
        synchronous = False):

        try:

            client_id = info.context.client_id
            client = DBSession.query(Client).filter_by(id = client_id).first()

            if not client:

                return (

                    ResponseError(
                        message = 'Only registered users can compute valency information.'))

            if debug_flag and client.user_id != 1:

                return (

                    ResponseError(
                        message = 'Only administrator can use debug mode.'))

            perspective = (
                DBSession.query(dbPerspective).filter_by(
                    client_id = perspective_id[0], object_id = perspective_id[1]).first())

            if not perspective:

                return (

                    ResponseError(
                        message = 'No perspective {}/{} in the system.'.format(*perspective_id)))

            dictionary = perspective.parent

            locale_id = info.context.locale_id or ENGLISH_LOCALE

            dictionary_name = dictionary.get_translation(locale_id)
            perspective_name = perspective.get_translation(locale_id)

            full_name = dictionary_name + ' \u203a ' + perspective_name

            if dictionary.marked_for_deletion:

                return (

                    ResponseError(message =
                        'Dictionary \'{}\' {}/{} is deleted.'.format(
                            dictionary_name,
                            perspective.parent_client_id,
                            perspective.parent_object_id)))

            if perspective.marked_for_deletion:

                return (

                    ResponseError(message =
                        'Perspective \'{}\' {}/{} is deleted.'.format(
                            full_name,
                            perspective_id[0],
                            perspective_id[1])))

            if not synchronous:

                task = TaskStatus(client.user_id, 'Valency', 'Valency: ' + full_name, 1)

            settings = info.context.request.registry.settings

            (Valency.compute if synchronous else async_valency_compute.delay)(
                perspective_id,
                debug_flag,
                full_name,
                task.key if not synchronous else None,
                settings['storage'],
                settings['cache_kwargs'],
                settings['sqlalchemy.url'])

            return (

                Valency(
                    triumph = True))

        except Exception as exception:

            traceback_string = (

                ''.join(
                    traceback.format_exception(
                        exception, exception, exception.__traceback__))[:-1])

            log.warning('valency: exception')
            log.warning(traceback_string)

            return (

                ResponseError(
                    'Exception:\n' + traceback_string))


diacritic_signs = ''.join([
    '\u0300', '\u0301', '\u0302', '\u0303', '\u0304', '\u0305', '\u0306', '\u0307',
    '\u0308', '\u0309', '\u030a', '\u030b', '\u030c', '\u030d', '\u030e', '\u030f', '\u0310',
    '\u0311', '\u0312', '\u0313', '\u0314', '\u0315', '\u0316', '\u0317', '\u0318', '\u0319',
    '\u031a', '\u031b', '\u031c', '\u031d', '\u031e', '\u031f', '\u0320', '\u0321', '\u0322',
    '\u0323', '\u0324', '\u0325', '\u0326', '\u0327', '\u0328', '\u0329', '\u032a', '\u032b',
    '\u032c', '\u032d', '\u032e', '\u032f', '\u0330', '\u0331', '\u0332', '\u0333', '\u0334',
    '\u0335', '\u0336', '\u0337', '\u0338', '\u0339', '\u033a', '\u033b', '\u033c', '\u033d',
    '\u033e', '\u033f', '\u0340', '\u0341', '\u0342', '\u0343', '\u0344', '\u0345', '\u0346',
    '\u0347', '\u0348', '\u0349', '\u034a', '\u034b', '\u034c', '\u034d', '\u034e', '\u034f',
    '\u0350', '\u0351', '\u0352', '\u0353', '\u0354', '\u0355', '\u0356', '\u0357', '\u0358',
    '\u0359', '\u035a', '\u035b', '\u035c', '\u035d', '\u035e', '\u035f', '\u0360', '\u0361',
    '\u0362', '\u0363', '\u0364', '\u0365', '\u0366', '\u0367', '\u0368', '\u0369', '\u036a',
    '\u036b', '\u036c', '\u036d', '\u036e', '\u036f', '\u0483', '\u0484', '\u0485', '\u0486',
    '\u0487', '\u0488', '\u0489', '\u0591', '\u0592', '\u0593', '\u0594', '\u0595', '\u0596',
    '\u0597', '\u0598', '\u0599', '\u059a', '\u059b', '\u059c', '\u059d', '\u059e', '\u059f',
    '\u05a0', '\u05a1', '\u05a2', '\u05a3', '\u05a4', '\u05a5', '\u05a6', '\u05a7', '\u05a8',
    '\u05a9', '\u05aa', '\u05ab', '\u05ac', '\u05ad', '\u05ae', '\u05af', '\u05b0', '\u05b1',
    '\u05b2', '\u05b3', '\u05b4', '\u05b5', '\u05b6', '\u05b7', '\u05b8', '\u05b9', '\u05ba',
    '\u05bb', '\u05bc', '\u05bd', '\u05bf', '\u05c1', '\u05c2', '\u05c4', '\u05c5', '\u05c7',
    '\u0610', '\u0611', '\u0612', '\u0613', '\u0614', '\u0615', '\u0616', '\u0617', '\u0618',
    '\u0619', '\u061a', '\u064b', '\u064c', '\u064d', '\u064e', '\u064f', '\u0650', '\u0651',
    '\u0652', '\u0653', '\u0654', '\u0655', '\u0656', '\u0657', '\u0658', '\u0659', '\u065a',
    '\u065b', '\u065c', '\u065d', '\u065e', '\u065f', '\u0670', '\u06d6', '\u06d7', '\u06d8',
    '\u06d9', '\u06da', '\u06db', '\u06dc', '\u06df', '\u06e0', '\u06e1', '\u06e2', '\u06e3',
    '\u06e4', '\u06e7', '\u06e8', '\u06ea', '\u06eb', '\u06ec', '\u06ed', '\u0711', '\u0730',
    '\u0731', '\u0732', '\u0733', '\u0734', '\u0735', '\u0736', '\u0737', '\u0738', '\u0739',
    '\u073a', '\u073b', '\u073c', '\u073d', '\u073e', '\u073f', '\u0740', '\u0741', '\u0742',
    '\u0743', '\u0744', '\u0745', '\u0746', '\u0747', '\u0748', '\u0749', '\u074a', '\u07a6',
    '\u07a7', '\u07a8', '\u07a9', '\u07aa', '\u07ab', '\u07ac', '\u07ad', '\u07ae', '\u07af',
    '\u07b0', '\u07eb', '\u07ec', '\u07ed', '\u07ee', '\u07ef', '\u07f0', '\u07f1', '\u07f2',
    '\u07f3', '\u0816', '\u0817', '\u0818', '\u0819', '\u081b', '\u081c', '\u081d', '\u081e',
    '\u081f', '\u0820', '\u0821', '\u0822', '\u0823', '\u0825', '\u0826', '\u0827', '\u0829',
    '\u082a', '\u082b', '\u082c', '\u082d', '\u0859', '\u085a', '\u085b', '\u08d4', '\u08d5',
    '\u08d6', '\u08d7', '\u08d8', '\u08d9', '\u08da', '\u08db', '\u08dc', '\u08dd', '\u08de',
    '\u08df', '\u08e0', '\u08e1', '\u08e3', '\u08e4', '\u08e5', '\u08e6', '\u08e7', '\u08e8',
    '\u08e9', '\u08ea', '\u08eb', '\u08ec', '\u08ed', '\u08ee', '\u08ef', '\u08f0', '\u08f1',
    '\u08f2', '\u08f3', '\u08f4', '\u08f5', '\u08f6', '\u08f7', '\u08f8', '\u08f9', '\u08fa',
    '\u08fb', '\u08fc', '\u08fd', '\u08fe', '\u08ff', '\u0900', '\u0901', '\u0902', '\u0903',
    '\u093a', '\u093b', '\u093c', '\u093e', '\u093f', '\u0940', '\u0941', '\u0942', '\u0943',
    '\u0944', '\u0945', '\u0946', '\u0947', '\u0948', '\u0949', '\u094a', '\u094b', '\u094c',
    '\u094d', '\u094e', '\u094f', '\u0951', '\u0952', '\u0953', '\u0954', '\u0955', '\u0956',
    '\u0957', '\u0962', '\u0963', '\u0981', '\u0982', '\u0983', '\u09bc', '\u09be', '\u09bf',
    '\u09c0', '\u09c1', '\u09c2', '\u09c3', '\u09c4', '\u09c7', '\u09c8', '\u09cb', '\u09cc',
    '\u09cd', '\u09d7', '\u09e2', '\u09e3', '\u0a01', '\u0a02', '\u0a03', '\u0a3c', '\u0a3e',
    '\u0a3f', '\u0a40', '\u0a41', '\u0a42', '\u0a47', '\u0a48', '\u0a4b', '\u0a4c', '\u0a4d',
    '\u0a51', '\u0a70', '\u0a71', '\u0a75', '\u0a81', '\u0a82', '\u0a83', '\u0abc', '\u0abe',
    '\u0abf', '\u0ac0', '\u0ac1', '\u0ac2', '\u0ac3', '\u0ac4', '\u0ac5', '\u0ac7', '\u0ac8',
    '\u0ac9', '\u0acb', '\u0acc', '\u0acd', '\u0ae2', '\u0ae3', '\u0b01', '\u0b02', '\u0b03',
    '\u0b3c', '\u0b3e', '\u0b3f', '\u0b40', '\u0b41', '\u0b42', '\u0b43', '\u0b44', '\u0b47',
    '\u0b48', '\u0b4b', '\u0b4c', '\u0b4d', '\u0b56', '\u0b57', '\u0b62', '\u0b63', '\u0b82',
    '\u0bbe', '\u0bbf', '\u0bc0', '\u0bc1', '\u0bc2', '\u0bc6', '\u0bc7', '\u0bc8', '\u0bca',
    '\u0bcb', '\u0bcc', '\u0bcd', '\u0bd7', '\u0c00', '\u0c01', '\u0c02', '\u0c03', '\u0c3e',
    '\u0c3f', '\u0c40', '\u0c41', '\u0c42', '\u0c43', '\u0c44', '\u0c46', '\u0c47', '\u0c48',
    '\u0c4a', '\u0c4b', '\u0c4c', '\u0c4d', '\u0c55', '\u0c56', '\u0c62', '\u0c63', '\u0c81',
    '\u0c82', '\u0c83', '\u0cbc', '\u0cbe', '\u0cbf', '\u0cc0', '\u0cc1', '\u0cc2', '\u0cc3',
    '\u0cc4', '\u0cc6', '\u0cc7', '\u0cc8', '\u0cca', '\u0ccb', '\u0ccc', '\u0ccd', '\u0cd5',
    '\u0cd6', '\u0ce2', '\u0ce3', '\u0d01', '\u0d02', '\u0d03', '\u0d3e', '\u0d3f', '\u0d40',
    '\u0d41', '\u0d42', '\u0d43', '\u0d44', '\u0d46', '\u0d47', '\u0d48', '\u0d4a', '\u0d4b',
    '\u0d4c', '\u0d4d', '\u0d57', '\u0d62', '\u0d63', '\u0d82', '\u0d83', '\u0dca', '\u0dcf',
    '\u0dd0', '\u0dd1', '\u0dd2', '\u0dd3', '\u0dd4', '\u0dd6', '\u0dd8', '\u0dd9', '\u0dda',
    '\u0ddb', '\u0ddc', '\u0ddd', '\u0dde', '\u0ddf', '\u0df2', '\u0df3', '\u0e31', '\u0e34',
    '\u0e35', '\u0e36', '\u0e37', '\u0e38', '\u0e39', '\u0e3a', '\u0e47', '\u0e48', '\u0e49',
    '\u0e4a', '\u0e4b', '\u0e4c', '\u0e4d', '\u0e4e', '\u0eb1', '\u0eb4', '\u0eb5', '\u0eb6',
    '\u0eb7', '\u0eb8', '\u0eb9', '\u0ebb', '\u0ebc', '\u0ec8', '\u0ec9', '\u0eca', '\u0ecb',
    '\u0ecc', '\u0ecd', '\u0f18', '\u0f19', '\u0f35', '\u0f37', '\u0f39', '\u0f3e', '\u0f3f',
    '\u0f71', '\u0f72', '\u0f73', '\u0f74', '\u0f75', '\u0f76', '\u0f77', '\u0f78', '\u0f79',
    '\u0f7a', '\u0f7b', '\u0f7c', '\u0f7d', '\u0f7e', '\u0f7f', '\u0f80', '\u0f81', '\u0f82',
    '\u0f83', '\u0f84', '\u0f86', '\u0f87', '\u0f8d', '\u0f8e', '\u0f8f', '\u0f90', '\u0f91',
    '\u0f92', '\u0f93', '\u0f94', '\u0f95', '\u0f96', '\u0f97', '\u0f99', '\u0f9a', '\u0f9b',
    '\u0f9c', '\u0f9d', '\u0f9e', '\u0f9f', '\u0fa0', '\u0fa1', '\u0fa2', '\u0fa3', '\u0fa4',
    '\u0fa5', '\u0fa6', '\u0fa7', '\u0fa8', '\u0fa9', '\u0faa', '\u0fab', '\u0fac', '\u0fad',
    '\u0fae', '\u0faf', '\u0fb0', '\u0fb1', '\u0fb2', '\u0fb3', '\u0fb4', '\u0fb5', '\u0fb6',
    '\u0fb7', '\u0fb8', '\u0fb9', '\u0fba', '\u0fbb', '\u0fbc', '\u0fc6', '\u102b', '\u102c',
    '\u102d', '\u102e', '\u102f', '\u1030', '\u1031', '\u1032', '\u1033', '\u1034', '\u1035',
    '\u1036', '\u1037', '\u1038', '\u1039', '\u103a', '\u103b', '\u103c', '\u103d', '\u103e',
    '\u1056', '\u1057', '\u1058', '\u1059', '\u105e', '\u105f', '\u1060', '\u1062', '\u1063',
    '\u1064', '\u1067', '\u1068', '\u1069', '\u106a', '\u106b', '\u106c', '\u106d', '\u1071',
    '\u1072', '\u1073', '\u1074', '\u1082', '\u1083', '\u1084', '\u1085', '\u1086', '\u1087',
    '\u1088', '\u1089', '\u108a', '\u108b', '\u108c', '\u108d', '\u108f', '\u109a', '\u109b',
    '\u109c', '\u109d', '\u135d', '\u135e', '\u135f', '\u1712', '\u1713', '\u1714', '\u1732',
    '\u1733', '\u1734', '\u1752', '\u1753', '\u1772', '\u1773', '\u17b4', '\u17b5', '\u17b6',
    '\u17b7', '\u17b8', '\u17b9', '\u17ba', '\u17bb', '\u17bc', '\u17bd', '\u17be', '\u17bf',
    '\u17c0', '\u17c1', '\u17c2', '\u17c3', '\u17c4', '\u17c5', '\u17c6', '\u17c7', '\u17c8',
    '\u17c9', '\u17ca', '\u17cb', '\u17cc', '\u17cd', '\u17ce', '\u17cf', '\u17d0', '\u17d1',
    '\u17d2', '\u17d3', '\u17dd', '\u180b', '\u180c', '\u180d', '\u1885', '\u1886', '\u18a9',
    '\u1920', '\u1921', '\u1922', '\u1923', '\u1924', '\u1925', '\u1926', '\u1927', '\u1928',
    '\u1929', '\u192a', '\u192b', '\u1930', '\u1931', '\u1932', '\u1933', '\u1934', '\u1935',
    '\u1936', '\u1937', '\u1938', '\u1939', '\u193a', '\u193b', '\u1a17', '\u1a18', '\u1a19',
    '\u1a1a', '\u1a1b', '\u1a55', '\u1a56', '\u1a57', '\u1a58', '\u1a59', '\u1a5a', '\u1a5b',
    '\u1a5c', '\u1a5d', '\u1a5e', '\u1a60', '\u1a61', '\u1a62', '\u1a63', '\u1a64', '\u1a65',
    '\u1a66', '\u1a67', '\u1a68', '\u1a69', '\u1a6a', '\u1a6b', '\u1a6c', '\u1a6d', '\u1a6e',
    '\u1a6f', '\u1a70', '\u1a71', '\u1a72', '\u1a73', '\u1a74', '\u1a75', '\u1a76', '\u1a77',
    '\u1a78', '\u1a79', '\u1a7a', '\u1a7b', '\u1a7c', '\u1a7f', '\u1ab0', '\u1ab1', '\u1ab2',
    '\u1ab3', '\u1ab4', '\u1ab5', '\u1ab6', '\u1ab7', '\u1ab8', '\u1ab9', '\u1aba', '\u1abb',
    '\u1abc', '\u1abd', '\u1abe', '\u1b00', '\u1b01', '\u1b02', '\u1b03', '\u1b04', '\u1b34',
    '\u1b35', '\u1b36', '\u1b37', '\u1b38', '\u1b39', '\u1b3a', '\u1b3b', '\u1b3c', '\u1b3d',
    '\u1b3e', '\u1b3f', '\u1b40', '\u1b41', '\u1b42', '\u1b43', '\u1b44', '\u1b6b', '\u1b6c',
    '\u1b6d', '\u1b6e', '\u1b6f', '\u1b70', '\u1b71', '\u1b72', '\u1b73', '\u1b80', '\u1b81',
    '\u1b82', '\u1ba1', '\u1ba2', '\u1ba3', '\u1ba4', '\u1ba5', '\u1ba6', '\u1ba7', '\u1ba8',
    '\u1ba9', '\u1baa', '\u1bab', '\u1bac', '\u1bad', '\u1be6', '\u1be7', '\u1be8', '\u1be9',
    '\u1bea', '\u1beb', '\u1bec', '\u1bed', '\u1bee', '\u1bef', '\u1bf0', '\u1bf1', '\u1bf2',
    '\u1bf3', '\u1c24', '\u1c25', '\u1c26', '\u1c27', '\u1c28', '\u1c29', '\u1c2a', '\u1c2b',
    '\u1c2c', '\u1c2d', '\u1c2e', '\u1c2f', '\u1c30', '\u1c31', '\u1c32', '\u1c33', '\u1c34',
    '\u1c35', '\u1c36', '\u1c37', '\u1cd0', '\u1cd1', '\u1cd2', '\u1cd4', '\u1cd5', '\u1cd6',
    '\u1cd7', '\u1cd8', '\u1cd9', '\u1cda', '\u1cdb', '\u1cdc', '\u1cdd', '\u1cde', '\u1cdf',
    '\u1ce0', '\u1ce1', '\u1ce2', '\u1ce3', '\u1ce4', '\u1ce5', '\u1ce6', '\u1ce7', '\u1ce8',
    '\u1ced', '\u1cf2', '\u1cf3', '\u1cf4', '\u1cf8', '\u1cf9', '\u1dc0', '\u1dc1', '\u1dc2',
    '\u1dc3', '\u1dc4', '\u1dc5', '\u1dc6', '\u1dc7', '\u1dc8', '\u1dc9', '\u1dca', '\u1dcb',
    '\u1dcc', '\u1dcd', '\u1dce', '\u1dcf', '\u1dd0', '\u1dd1', '\u1dd2', '\u1dd3', '\u1dd4',
    '\u1dd5', '\u1dd6', '\u1dd7', '\u1dd8', '\u1dd9', '\u1dda', '\u1ddb', '\u1ddc', '\u1ddd',
    '\u1dde', '\u1ddf', '\u1de0', '\u1de1', '\u1de2', '\u1de3', '\u1de4', '\u1de5', '\u1de6',
    '\u1de7', '\u1de8', '\u1de9', '\u1dea', '\u1deb', '\u1dec', '\u1ded', '\u1dee', '\u1def',
    '\u1df0', '\u1df1', '\u1df2', '\u1df3', '\u1df4', '\u1df5', '\u1dfb', '\u1dfc', '\u1dfd',
    '\u1dfe', '\u1dff', '\u20d0', '\u20d1', '\u20d2', '\u20d3', '\u20d4', '\u20d5', '\u20d6',
    '\u20d7', '\u20d8', '\u20d9', '\u20da', '\u20db', '\u20dc', '\u20dd', '\u20de', '\u20df',
    '\u20e0', '\u20e1', '\u20e2', '\u20e3', '\u20e4', '\u20e5', '\u20e6', '\u20e7', '\u20e8',
    '\u20e9', '\u20ea', '\u20eb', '\u20ec', '\u20ed', '\u20ee', '\u20ef', '\u20f0', '\u2cef',
    '\u2cf0', '\u2cf1', '\u2d7f', '\u2de0', '\u2de1', '\u2de2', '\u2de3', '\u2de4', '\u2de5',
    '\u2de6', '\u2de7', '\u2de8', '\u2de9', '\u2dea', '\u2deb', '\u2dec', '\u2ded', '\u2dee',
    '\u2def', '\u2df0', '\u2df1', '\u2df2', '\u2df3', '\u2df4', '\u2df5', '\u2df6', '\u2df7',
    '\u2df8', '\u2df9', '\u2dfa', '\u2dfb', '\u2dfc', '\u2dfd', '\u2dfe', '\u2dff', '\u302a',
    '\u302b', '\u302c', '\u302d', '\u302e', '\u302f', '\u3099', '\u309a', '\ua66f', '\ua670',
    '\ua671', '\ua672', '\ua674', '\ua675', '\ua676', '\ua677', '\ua678', '\ua679', '\ua67a',
    '\ua67b', '\ua67c', '\ua67d', '\ua69e', '\ua69f', '\ua6f0', '\ua6f1', '\ua802', '\ua806',
    '\ua80b', '\ua823', '\ua824', '\ua825', '\ua826', '\ua827', '\ua880', '\ua881', '\ua8b4',
    '\ua8b5', '\ua8b6', '\ua8b7', '\ua8b8', '\ua8b9', '\ua8ba', '\ua8bb', '\ua8bc', '\ua8bd',
    '\ua8be', '\ua8bf', '\ua8c0', '\ua8c1', '\ua8c2', '\ua8c3', '\ua8c4', '\ua8c5', '\ua8e0',
    '\ua8e1', '\ua8e2', '\ua8e3', '\ua8e4', '\ua8e5', '\ua8e6', '\ua8e7', '\ua8e8', '\ua8e9',
    '\ua8ea', '\ua8eb', '\ua8ec', '\ua8ed', '\ua8ee', '\ua8ef', '\ua8f0', '\ua8f1', '\ua926',
    '\ua927', '\ua928', '\ua929', '\ua92a', '\ua92b', '\ua92c', '\ua92d', '\ua947', '\ua948',
    '\ua949', '\ua94a', '\ua94b', '\ua94c', '\ua94d', '\ua94e', '\ua94f', '\ua950', '\ua951',
    '\ua952', '\ua953', '\ua980', '\ua981', '\ua982', '\ua983', '\ua9b3', '\ua9b4', '\ua9b5',
    '\ua9b6', '\ua9b7', '\ua9b8', '\ua9b9', '\ua9ba', '\ua9bb', '\ua9bc', '\ua9bd', '\ua9be',
    '\ua9bf', '\ua9c0', '\ua9e5', '\uaa29', '\uaa2a', '\uaa2b', '\uaa2c', '\uaa2d', '\uaa2e',
    '\uaa2f', '\uaa30', '\uaa31', '\uaa32', '\uaa33', '\uaa34', '\uaa35', '\uaa36', '\uaa43',
    '\uaa4c', '\uaa4d', '\uaa7b', '\uaa7c', '\uaa7d', '\uaab0', '\uaab2', '\uaab3', '\uaab4',
    '\uaab7', '\uaab8', '\uaabe', '\uaabf', '\uaac1', '\uaaeb', '\uaaec', '\uaaed', '\uaaee',
    '\uaaef', '\uaaf5', '\uaaf6', '\uabe3', '\uabe4', '\uabe5', '\uabe6', '\uabe7', '\uabe8',
    '\uabe9', '\uabea', '\uabec', '\uabed', '\ufb1e', '\ufe00', '\ufe01', '\ufe02', '\ufe03',
    '\ufe04', '\ufe05', '\ufe06', '\ufe07', '\ufe08', '\ufe09', '\ufe0a', '\ufe0b', '\ufe0c',
    '\ufe0d', '\ufe0e', '\ufe0f', '\ufe20', '\ufe21', '\ufe22', '\ufe23', '\ufe24', '\ufe25',
    '\ufe26', '\ufe27', '\ufe28', '\ufe29', '\ufe2a', '\ufe2b', '\ufe2c', '\ufe2d', '\ufe2e',
    '\ufe2f', '\U000101fd', '\U000102e0', '\U00010376', '\U00010377', '\U00010378',
    '\U00010379', '\U0001037a', '\U00010a01', '\U00010a02', '\U00010a03', '\U00010a05',
    '\U00010a06', '\U00010a0c', '\U00010a0d', '\U00010a0e', '\U00010a0f', '\U00010a38',
    '\U00010a39', '\U00010a3a', '\U00010a3f', '\U00010ae5', '\U00010ae6', '\U00011000',
    '\U00011001', '\U00011002', '\U00011038', '\U00011039', '\U0001103a', '\U0001103b',
    '\U0001103c', '\U0001103d', '\U0001103e', '\U0001103f', '\U00011040', '\U00011041',
    '\U00011042', '\U00011043', '\U00011044', '\U00011045', '\U00011046', '\U0001107f',
    '\U00011080', '\U00011081', '\U00011082', '\U000110b0', '\U000110b1', '\U000110b2',
    '\U000110b3', '\U000110b4', '\U000110b5', '\U000110b6', '\U000110b7', '\U000110b8',
    '\U000110b9', '\U000110ba', '\U00011100', '\U00011101', '\U00011102', '\U00011127',
    '\U00011128', '\U00011129', '\U0001112a', '\U0001112b', '\U0001112c', '\U0001112d',
    '\U0001112e', '\U0001112f', '\U00011130', '\U00011131', '\U00011132', '\U00011133',
    '\U00011134', '\U00011173', '\U00011180', '\U00011181', '\U00011182', '\U000111b3',
    '\U000111b4', '\U000111b5', '\U000111b6', '\U000111b7', '\U000111b8', '\U000111b9',
    '\U000111ba', '\U000111bb', '\U000111bc', '\U000111bd', '\U000111be', '\U000111bf',
    '\U000111c0', '\U000111ca', '\U000111cb', '\U000111cc', '\U0001122c', '\U0001122d',
    '\U0001122e', '\U0001122f', '\U00011230', '\U00011231', '\U00011232', '\U00011233',
    '\U00011234', '\U00011235', '\U00011236', '\U00011237', '\U0001123e', '\U000112df',
    '\U000112e0', '\U000112e1', '\U000112e2', '\U000112e3', '\U000112e4', '\U000112e5',
    '\U000112e6', '\U000112e7', '\U000112e8', '\U000112e9', '\U000112ea', '\U00011300',
    '\U00011301', '\U00011302', '\U00011303', '\U0001133c', '\U0001133e', '\U0001133f',
    '\U00011340', '\U00011341', '\U00011342', '\U00011343', '\U00011344', '\U00011347',
    '\U00011348', '\U0001134b', '\U0001134c', '\U0001134d', '\U00011357', '\U00011362',
    '\U00011363', '\U00011366', '\U00011367', '\U00011368', '\U00011369', '\U0001136a',
    '\U0001136b', '\U0001136c', '\U00011370', '\U00011371', '\U00011372', '\U00011373',
    '\U00011374', '\U00011435', '\U00011436', '\U00011437', '\U00011438', '\U00011439',
    '\U0001143a', '\U0001143b', '\U0001143c', '\U0001143d', '\U0001143e', '\U0001143f',
    '\U00011440', '\U00011441', '\U00011442', '\U00011443', '\U00011444', '\U00011445',
    '\U00011446', '\U000114b0', '\U000114b1', '\U000114b2', '\U000114b3', '\U000114b4',
    '\U000114b5', '\U000114b6', '\U000114b7', '\U000114b8', '\U000114b9', '\U000114ba',
    '\U000114bb', '\U000114bc', '\U000114bd', '\U000114be', '\U000114bf', '\U000114c0',
    '\U000114c1', '\U000114c2', '\U000114c3', '\U000115af', '\U000115b0', '\U000115b1',
    '\U000115b2', '\U000115b3', '\U000115b4', '\U000115b5', '\U000115b8', '\U000115b9',
    '\U000115ba', '\U000115bb', '\U000115bc', '\U000115bd', '\U000115be', '\U000115bf',
    '\U000115c0', '\U000115dc', '\U000115dd', '\U00011630', '\U00011631', '\U00011632',
    '\U00011633', '\U00011634', '\U00011635', '\U00011636', '\U00011637', '\U00011638',
    '\U00011639', '\U0001163a', '\U0001163b', '\U0001163c', '\U0001163d', '\U0001163e',
    '\U0001163f', '\U00011640', '\U000116ab', '\U000116ac', '\U000116ad', '\U000116ae',
    '\U000116af', '\U000116b0', '\U000116b1', '\U000116b2', '\U000116b3', '\U000116b4',
    '\U000116b5', '\U000116b6', '\U000116b7', '\U0001171d', '\U0001171e', '\U0001171f',
    '\U00011720', '\U00011721', '\U00011722', '\U00011723', '\U00011724', '\U00011725',
    '\U00011726', '\U00011727', '\U00011728', '\U00011729', '\U0001172a', '\U0001172b',
    '\U00011c2f', '\U00011c30', '\U00011c31', '\U00011c32', '\U00011c33', '\U00011c34',
    '\U00011c35', '\U00011c36', '\U00011c38', '\U00011c39', '\U00011c3a', '\U00011c3b',
    '\U00011c3c', '\U00011c3d', '\U00011c3e', '\U00011c3f', '\U00011c92', '\U00011c93',
    '\U00011c94', '\U00011c95', '\U00011c96', '\U00011c97', '\U00011c98', '\U00011c99',
    '\U00011c9a', '\U00011c9b', '\U00011c9c', '\U00011c9d', '\U00011c9e', '\U00011c9f',
    '\U00011ca0', '\U00011ca1', '\U00011ca2', '\U00011ca3', '\U00011ca4', '\U00011ca5',
    '\U00011ca6', '\U00011ca7', '\U00011ca9', '\U00011caa', '\U00011cab', '\U00011cac',
    '\U00011cad', '\U00011cae', '\U00011caf', '\U00011cb0', '\U00011cb1', '\U00011cb2',
    '\U00011cb3', '\U00011cb4', '\U00011cb5', '\U00011cb6', '\U00016af0', '\U00016af1',
    '\U00016af2', '\U00016af3', '\U00016af4', '\U00016b30', '\U00016b31', '\U00016b32',
    '\U00016b33', '\U00016b34', '\U00016b35', '\U00016b36', '\U00016f51', '\U00016f52',
    '\U00016f53', '\U00016f54', '\U00016f55', '\U00016f56', '\U00016f57', '\U00016f58',
    '\U00016f59', '\U00016f5a', '\U00016f5b', '\U00016f5c', '\U00016f5d', '\U00016f5e',
    '\U00016f5f', '\U00016f60', '\U00016f61', '\U00016f62', '\U00016f63', '\U00016f64',
    '\U00016f65', '\U00016f66', '\U00016f67', '\U00016f68', '\U00016f69', '\U00016f6a',
    '\U00016f6b', '\U00016f6c', '\U00016f6d', '\U00016f6e', '\U00016f6f', '\U00016f70',
    '\U00016f71', '\U00016f72', '\U00016f73', '\U00016f74', '\U00016f75', '\U00016f76',
    '\U00016f77', '\U00016f78', '\U00016f79', '\U00016f7a', '\U00016f7b', '\U00016f7c',
    '\U00016f7d', '\U00016f7e', '\U00016f8f', '\U00016f90', '\U00016f91', '\U00016f92',
    '\U0001bc9d', '\U0001bc9e', '\U0001d165', '\U0001d166', '\U0001d167', '\U0001d168',
    '\U0001d169', '\U0001d16d', '\U0001d16e', '\U0001d16f', '\U0001d170', '\U0001d171',
    '\U0001d172', '\U0001d17b', '\U0001d17c', '\U0001d17d', '\U0001d17e', '\U0001d17f',
    '\U0001d180', '\U0001d181', '\U0001d182', '\U0001d185', '\U0001d186', '\U0001d187',
    '\U0001d188', '\U0001d189', '\U0001d18a', '\U0001d18b', '\U0001d1aa', '\U0001d1ab',
    '\U0001d1ac', '\U0001d1ad', '\U0001d242', '\U0001d243', '\U0001d244', '\U0001da00',
    '\U0001da01', '\U0001da02', '\U0001da03', '\U0001da04', '\U0001da05', '\U0001da06',
    '\U0001da07', '\U0001da08', '\U0001da09', '\U0001da0a', '\U0001da0b', '\U0001da0c',
    '\U0001da0d', '\U0001da0e', '\U0001da0f', '\U0001da10', '\U0001da11', '\U0001da12',
    '\U0001da13', '\U0001da14', '\U0001da15', '\U0001da16', '\U0001da17', '\U0001da18',
    '\U0001da19', '\U0001da1a', '\U0001da1b', '\U0001da1c', '\U0001da1d', '\U0001da1e',
    '\U0001da1f', '\U0001da20', '\U0001da21', '\U0001da22', '\U0001da23', '\U0001da24',
    '\U0001da25', '\U0001da26', '\U0001da27', '\U0001da28', '\U0001da29', '\U0001da2a',
    '\U0001da2b', '\U0001da2c', '\U0001da2d', '\U0001da2e', '\U0001da2f', '\U0001da30',
    '\U0001da31', '\U0001da32', '\U0001da33', '\U0001da34', '\U0001da35', '\U0001da36',
    '\U0001da3b', '\U0001da3c', '\U0001da3d', '\U0001da3e', '\U0001da3f', '\U0001da40',
    '\U0001da41', '\U0001da42', '\U0001da43', '\U0001da44', '\U0001da45', '\U0001da46',
    '\U0001da47', '\U0001da48', '\U0001da49', '\U0001da4a', '\U0001da4b', '\U0001da4c',
    '\U0001da4d', '\U0001da4e', '\U0001da4f', '\U0001da50', '\U0001da51', '\U0001da52',
    '\U0001da53', '\U0001da54', '\U0001da55', '\U0001da56', '\U0001da57', '\U0001da58',
    '\U0001da59', '\U0001da5a', '\U0001da5b', '\U0001da5c', '\U0001da5d', '\U0001da5e',
    '\U0001da5f', '\U0001da60', '\U0001da61', '\U0001da62', '\U0001da63', '\U0001da64',
    '\U0001da65', '\U0001da66', '\U0001da67', '\U0001da68', '\U0001da69', '\U0001da6a',
    '\U0001da6b', '\U0001da6c', '\U0001da75', '\U0001da84', '\U0001da9b', '\U0001da9c',
    '\U0001da9d', '\U0001da9e', '\U0001da9f', '\U0001daa1', '\U0001daa2', '\U0001daa3',
    '\U0001daa4', '\U0001daa5', '\U0001daa6', '\U0001daa7', '\U0001daa8', '\U0001daa9',
    '\U0001daaa', '\U0001daab', '\U0001daac', '\U0001daad', '\U0001daae', '\U0001daaf',
    '\U0001e000', '\U0001e001', '\U0001e002', '\U0001e003', '\U0001e004', '\U0001e005',
    '\U0001e006', '\U0001e008', '\U0001e009', '\U0001e00a', '\U0001e00b', '\U0001e00c',
    '\U0001e00d', '\U0001e00e', '\U0001e00f', '\U0001e010', '\U0001e011', '\U0001e012',
    '\U0001e013', '\U0001e014', '\U0001e015', '\U0001e016', '\U0001e017', '\U0001e018',
    '\U0001e01b', '\U0001e01c', '\U0001e01d', '\U0001e01e', '\U0001e01f', '\U0001e020',
    '\U0001e021', '\U0001e023', '\U0001e024', '\U0001e026', '\U0001e027', '\U0001e028',
    '\U0001e029', '\U0001e02a', '\U0001e8d0', '\U0001e8d1', '\U0001e8d2', '\U0001e8d3',
    '\U0001e8d4', '\U0001e8d5', '\U0001e8d6', '\U0001e944', '\U0001e945', '\U0001e946',
    '\U0001e947', '\U0001e948', '\U0001e949', '\U0001e94a', '\U000e0100', '\U000e0101',
    '\U000e0102', '\U000e0103', '\U000e0104', '\U000e0105', '\U000e0106', '\U000e0107',
    '\U000e0108', '\U000e0109', '\U000e010a', '\U000e010b', '\U000e010c', '\U000e010d',
    '\U000e010e', '\U000e010f', '\U000e0110', '\U000e0111', '\U000e0112', '\U000e0113',
    '\U000e0114', '\U000e0115', '\U000e0116', '\U000e0117', '\U000e0118', '\U000e0119',
    '\U000e011a', '\U000e011b', '\U000e011c', '\U000e011d', '\U000e011e', '\U000e011f',
    '\U000e0120', '\U000e0121', '\U000e0122', '\U000e0123', '\U000e0124', '\U000e0125',
    '\U000e0126', '\U000e0127', '\U000e0128', '\U000e0129', '\U000e012a', '\U000e012b',
    '\U000e012c', '\U000e012d', '\U000e012e', '\U000e012f', '\U000e0130', '\U000e0131',
    '\U000e0132', '\U000e0133', '\U000e0134', '\U000e0135', '\U000e0136', '\U000e0137',
    '\U000e0138', '\U000e0139', '\U000e013a', '\U000e013b', '\U000e013c', '\U000e013d',
    '\U000e013e', '\U000e013f', '\U000e0140', '\U000e0141', '\U000e0142', '\U000e0143',
    '\U000e0144', '\U000e0145', '\U000e0146', '\U000e0147', '\U000e0148', '\U000e0149',
    '\U000e014a', '\U000e014b', '\U000e014c', '\U000e014d', '\U000e014e', '\U000e014f',
    '\U000e0150', '\U000e0151', '\U000e0152', '\U000e0153', '\U000e0154', '\U000e0155',
    '\U000e0156', '\U000e0157', '\U000e0158', '\U000e0159', '\U000e015a', '\U000e015b',
    '\U000e015c', '\U000e015d', '\U000e015e', '\U000e015f', '\U000e0160', '\U000e0161',
    '\U000e0162', '\U000e0163', '\U000e0164', '\U000e0165', '\U000e0166', '\U000e0167',
    '\U000e0168', '\U000e0169', '\U000e016a', '\U000e016b', '\U000e016c', '\U000e016d',
    '\U000e016e', '\U000e016f', '\U000e0170', '\U000e0171', '\U000e0172', '\U000e0173',
    '\U000e0174', '\U000e0175', '\U000e0176', '\U000e0177', '\U000e0178', '\U000e0179',
    '\U000e017a', '\U000e017b', '\U000e017c', '\U000e017d', '\U000e017e', '\U000e017f',
    '\U000e0180', '\U000e0181', '\U000e0182', '\U000e0183', '\U000e0184', '\U000e0185',
    '\U000e0186', '\U000e0187', '\U000e0188', '\U000e0189', '\U000e018a', '\U000e018b',
    '\U000e018c', '\U000e018d', '\U000e018e', '\U000e018f', '\U000e0190', '\U000e0191',
    '\U000e0192', '\U000e0193', '\U000e0194', '\U000e0195', '\U000e0196', '\U000e0197',
    '\U000e0198', '\U000e0199', '\U000e019a', '\U000e019b', '\U000e019c', '\U000e019d',
    '\U000e019e', '\U000e019f', '\U000e01a0', '\U000e01a1', '\U000e01a2', '\U000e01a3',
    '\U000e01a4', '\U000e01a5', '\U000e01a6', '\U000e01a7', '\U000e01a8', '\U000e01a9',
    '\U000e01aa', '\U000e01ab', '\U000e01ac', '\U000e01ad', '\U000e01ae', '\U000e01af',
    '\U000e01b0', '\U000e01b1', '\U000e01b2', '\U000e01b3', '\U000e01b4', '\U000e01b5',
    '\U000e01b6', '\U000e01b7', '\U000e01b8', '\U000e01b9', '\U000e01ba', '\U000e01bb',
    '\U000e01bc', '\U000e01bd', '\U000e01be', '\U000e01bf', '\U000e01c0', '\U000e01c1',
    '\U000e01c2', '\U000e01c3', '\U000e01c4', '\U000e01c5', '\U000e01c6', '\U000e01c7',
    '\U000e01c8', '\U000e01c9', '\U000e01ca', '\U000e01cb', '\U000e01cc', '\U000e01cd',
    '\U000e01ce', '\U000e01cf', '\U000e01d0', '\U000e01d1', '\U000e01d2', '\U000e01d3',
    '\U000e01d4', '\U000e01d5', '\U000e01d6', '\U000e01d7', '\U000e01d8', '\U000e01d9',
    '\U000e01da', '\U000e01db', '\U000e01dc', '\U000e01dd', '\U000e01de', '\U000e01df',
    '\U000e01e0', '\U000e01e1', '\U000e01e2', '\U000e01e3', '\U000e01e4', '\U000e01e5',
    '\U000e01e6', '\U000e01e7', '\U000e01e8', '\U000e01e9', '\U000e01ea', '\U000e01eb',
    '\U000e01ec', '\U000e01ed', '\U000e01ee', '\U000e01ef'])

diacritic_re = re.compile('[' + diacritic_signs + ']')

def diacritic_xform(value_str):

    return (

        re.sub(
            diacritic_re,
            '',
            unicodedata.normalize('NFKD', value_str)))


class CreateValencyData(graphene.Mutation):

    case_list = [
        'nom', 'acc', 'gen', 'ad', 'abl', 'dat', 'ab', 'ins', 'car', 'term', 'cns', 'com', 'comp',
        'trans', 'sim', 'par', 'loc', 'prol', 'in', 'ill', 'el', 'egr',  'lat', 'allat']

    case_index_dict = {
        case: index
        for index, case in enumerate(case_list)}

    class Arguments:

        perspective_id = LingvodocID(required = True)
        debug_flag = graphene.Boolean()

    triumph = graphene.Boolean()

    @staticmethod
    def align(
        token_list,
        word_list,
        debug_flag):
        """
        Aligns words to text tokens via Levenshtein matching.
        """

        token_chr_list = []

        for i, token in enumerate(token_list):
            for j, chr in enumerate(token):

                token_chr_list.append((i, j, chr.lower()))

        word_chr_list = []

        for i, word in enumerate(word_list):
            for j, chr in enumerate(word or ''):

                word_chr_list.append((i, j, chr.lower()))

        if debug_flag:

            log.debug(
                f'\ntoken_chr_list: {token_chr_list}'
                f'\nword_chr_list: {word_chr_list}'
                f'\n{"".join(token_list)}'
                f'\n{"".join(word or "" for word in word_list)}')

        # Standard 2-row Wagner-Fischer with addition of substitution tracking.

        value_list = [
            (i, None)
            for i in range(len(token_chr_list) + 1)]

        for i in range(len(word_chr_list)):

            before_list = value_list
            value_list = [(i + 1, None)]

            for j in range(len(token_chr_list)):

                delete_source = before_list[j + 1]
                delete_value = (delete_source[0] + 1, delete_source[1])

                insert_source = value_list[j]
                insert_value = (insert_source[0] + 1, insert_source[1])

                substitute_source = before_list[j]
                substitute_cost = substitute_source[0]

                if token_chr_list[j][2] != word_chr_list[i][2]:
                    substitute_cost += 1

                substitute_value = (

                    substitute_cost,
                    (token_chr_list[j][:2], word_chr_list[i][:2], substitute_source[1]))

                value_list.append(
                    min(delete_value, insert_value, substitute_value))

        result = (
            value_list[len(token_chr_list)])

        log.debug(f'\n{result[0]}')

        # Matching words to tokens by number of substitution and token ordering.

        map_tuple = result[1]
        map_list = []

        while map_tuple:

            map_list.append(map_tuple[:2])
            map_tuple = map_tuple[2]

        log_list = []

        map_counter = (
            collections.defaultdict(collections.Counter))

        for index_from, index_to in reversed(map_list):

            if debug_flag:

                token = token_list[index_from[0]]
                word = word_list[index_to[0]]

                log_list.append(
                    f'\n{index_from}, {index_to}: '
                    f'{token[: index_from[1]]}[{token[index_from[1]]}]{token[index_from[1] + 1 :]} / '
                    f'{word[: index_to[1]]}[{word[index_to[1]]}]{word[index_to[1] + 1 :]}')

            map_counter[index_to[0]][index_from[0]] += 1

        if debug_flag:

            log.debug(
                ''.join(log_list))

        word_token_dict = {}
        token_already_set = set()

        for word_index in range(len(word_list)):

            token_result = (

                max(
                    ((count, -token_index)
                        for token_index, count in map_counter[word_index].items()
                        if token_index not in token_already_set),
                    default = None))

            if token_result is not None:

                token_count, token_index_value = token_result

                token_index = -token_index_value

                word_token_dict[word_index] = token_index
                token_already_set.add(token_index)

        if debug_flag:

            log.debug(
                ''.join(
                    f'\n{repr(word_list[word_index])} ({word_index}) -> '
                    f'{repr(token_list[token_index])} ({token_index})'
                    for word_index, token_index in word_token_dict.items()))

        return (
            result[0], word_token_dict)

    @staticmethod
    def process_parser(
        perspective_id,
        data_case_set,
        instance_insert_list,
        debug_flag):

        # Getting parser result data.

        parser_result_list = (

            Valency.get_parser_result_data(
                perspective_id, debug_flag))

        sentence_data_list = (
            valency.corpus_to_sentences(parser_result_list))

        if debug_flag:

            parser_result_file_name = (
                f'create valency {perspective_id[0]} {perspective_id[1]} parser result.json')

            with open(
                parser_result_file_name, 'w') as parser_result_file:

                json.dump(
                    parser_result_list,
                    parser_result_file,
                    ensure_ascii = False,
                    indent = 2)

            sentence_data_file_name = (
                f'create valency {perspective_id[0]} {perspective_id[1]} sentence data.json')

            with open(
                sentence_data_file_name, 'w') as sentence_data_file:

                json.dump(
                    sentence_data_list,
                    sentence_data_file,
                    ensure_ascii = False,
                    indent = 2)

        # Initializing annotation data from parser results.

        for i in sentence_data_list:

            parser_result_id = i['id']

            # Checking if we already have such parser result valency data.

            valency_parser_data = (

                DBSession

                    .query(
                        dbValencyParserData)

                    .filter(
                        dbValencySourceData.perspective_client_id == perspective_id[0],
                        dbValencySourceData.perspective_object_id == perspective_id[1],
                        dbValencySourceData.id == dbValencyParserData.id,
                        dbValencyParserData.parser_result_client_id == parser_result_id[0],
                        dbValencyParserData.parser_result_object_id == parser_result_id[1])

                    .first())

            if valency_parser_data:

                # The same hash, we just skip it.

                if valency_parser_data.hash == i['hash']:
                    continue

                # Not the same hash, we actually should update it, but for now we leave it for later.

                continue

            valency_source_data = (

                dbValencySourceData(
                    perspective_client_id = perspective_id[0],
                    perspective_object_id = perspective_id[1]))

            DBSession.add(valency_source_data)
            DBSession.flush()

            valency_parser_data = (

                dbValencyParserData(
                    id = valency_source_data.id,
                    parser_result_client_id = parser_result_id[0],
                    parser_result_object_id = parser_result_id[1],
                    hash = i['hash']))

            DBSession.add(valency_parser_data)
            DBSession.flush()

            for p in i['paragraphs']:

                for s in p['sentences']:

                    instance_list = []

                    for index, (lex, cs, indent, ind, r, animacy) in (
                        enumerate(valency.sentence_instance_gen(s))):

                        instance_list.append({
                            'index': index,
                            'location': (ind, r),
                            'case': cs})

                        data_case_set.add(cs)

                    sentence_data = {
                        'tokens': s,
                        'instances': instance_list}

                    valency_sentence_data = (

                        dbValencySentenceData(
                            source_id = valency_source_data.id,
                            data = sentence_data,
                            instance_count = len(instance_list)))

                    DBSession.add(valency_sentence_data)
                    DBSession.flush()

                    for instance in instance_list:

                        instance_insert_list.append({
                            'sentence_id': valency_sentence_data.id,
                            'index': instance['index'],
                            'verb_lex': s[instance['location'][0]]['lex'].lower(),
                            'case_str': instance['case'].lower()})

                    log.debug(
                        '\n' +
                        pprint.pformat(
                            (valency_source_data.id, len(instance_list), sentence_data),
                            width = 192))

    @staticmethod
    def process_eaf(
        info,
        perspective_id,
        data_case_set,
        instance_insert_list,
        debug_flag):

        # Getting ELAN corpus data, processing each ELAN file.

        entity_list = (

            DBSession

                .query(
                    dbEntity)

                .filter(
                    dbLexicalEntry.parent_client_id == perspective_id[0],
                    dbLexicalEntry.parent_object_id == perspective_id[1],
                    dbLexicalEntry.marked_for_deletion == False,
                    dbEntity.parent_client_id == dbLexicalEntry.client_id,
                    dbEntity.parent_object_id == dbLexicalEntry.object_id,
                    dbEntity.marked_for_deletion == False,
                    dbEntity.content.ilike('%.eaf'),
                    dbEntity.additional_metadata.contains({'data_type': 'elan markup'}),
                    dbPublishingEntity.client_id == dbEntity.client_id,
                    dbPublishingEntity.object_id == dbEntity.object_id,
                    dbPublishingEntity.published == True,
                    dbPublishingEntity.accepted == True)

                .order_by(
                    dbLexicalEntry.created_at,
                    dbLexicalEntry.client_id,
                    dbLexicalEntry.object_id,
                    dbEntity.created_at,
                    dbEntity.client_id,
                    dbEntity.object_id)

                .all())

        storage = (
            info.context.request.registry.settings['storage'])

        storage_f = (
            as_storage_file if debug_flag else storage_file)

        delimiter_re = '[-\xad\xaf\x96\u2013\x97\u2014.]'

        verb_gloss_str_list = [

            'PRS',
            'FUT',
            f'1{delimiter_re}?PST',
            f'2{delimiter_re}?PST',

            'IMP',
            'COND',
            'SBJV',

            'CAUS',
            'REFL',
            'IMPERS',
            'ITER',

            'OPT',
            'INF',

            'NPST',
            'NST',
            'PST1',
            'PST2',
            'PST3']

        verb_re = (

            re.compile(
                f'{delimiter_re}\\b({"|".join(verb_gloss_str_list)})\\b',
                re.IGNORECASE))

        case_re = (

            re.compile(
                f'{delimiter_re}\\b({"|".join(CreateValencyData.case_list)})\\b',
                re.IGNORECASE))

        lex_xlat_dict = collections.defaultdict(set)
        xlat_lex_dict = collections.defaultdict(set)

        for entity in entity_list:

            # Checking if we already have such EAF corpus valency data.

            valency_eaf_data = (

                DBSession

                    .query(dbValencyEafData)

                    .filter(
                        dbValencySourceData.perspective_client_id == perspective_id[0],
                        dbValencySourceData.perspective_object_id == perspective_id[1],
                        dbValencySourceData.id == dbValencyEafData.id,
                        dbValencyEafData.entity_client_id == entity.client_id,
                        dbValencyEafData.entity_object_id == entity.object_id)

                    .first())

            if valency_eaf_data:

                # The same hash, we just skip it.

                if valency_eaf_data.hash == entity.additional_metadata['hash']:
                    continue

                # Not the same hash, we actually should update it, but for now we leave it for later.

                continue

            valency_source_data = (

                dbValencySourceData(
                    perspective_client_id = perspective_id[0],
                    perspective_object_id = perspective_id[1]))

            DBSession.add(valency_source_data)
            DBSession.flush()

            valency_eaf_data = (

                dbValencyEafData(
                    id = valency_source_data.id,
                    entity_client_id = entity.client_id,
                    entity_object_id = entity.object_id,
                    hash = entity.additional_metadata['hash']))

            DBSession.add(valency_eaf_data)
            DBSession.flush()

            create_valency_str = (
                f'create valency '
                f'{perspective_id[0]} {perspective_id[1]} '
                f'{entity.client_id} {entity.object_id}')

            # Getting and parsing corpus file.

            log.debug(
                f'\nentity.content:\n{entity.content}')

            try:
                with storage_f(storage, entity.content) as eaf_stream:
                    content = eaf_stream.read()

            except:
                raise ResponseError(f'Cannot access {entity.content}')

            with tempfile.NamedTemporaryFile() as temporary_file:

                temporary_file.write(
                    tgt_to_eaf(content, entity.additional_metadata).encode('utf-8'))

                temporary_file.flush()

                elan_check = elan_parser.ElanCheck(temporary_file.name)
                elan_check.parse()

                if not elan_check.check():
                    continue

                elan_reader = elan_parser.Elan(temporary_file.name)
                elan_reader.parse()

                eaf_data = elan_reader.proc()

                # Saving corpus file if required.

                if debug_flag:

                    shutil.copyfile(
                        temporary_file.name,
                        f'{create_valency_str}.eaf')

            if debug_flag:

                log.debug(
                    '\n' +
                    pprint.pformat(eaf_data, width = 192))

                with open(
                    f'{create_valency_str}.pprint', 'w') as pprint_file:

                    pprint_file.write(
                        pprint.pformat(eaf_data, width = 192))

            # Processing extracted data.

            for eaf_item in eaf_data:

                if len(eaf_item) < 3:
                    continue

                if debug_flag:

                    log.debug(
                        '\neaf_item:\n{}\n{}\n{}'.format(
                            pprint.pformat(eaf_item[0], width = 192),
                            pprint.pformat(eaf_item[1], width = 192),
                            pprint.pformat(eaf_item[2], width = 192)))

                if not isinstance(eaf_item[2], collections.OrderedDict):
                    continue

                # Text tokenization.

                if (len(eaf_item[0]) < 1 or
                    eaf_item[0][0].tier != 'text'):

                    raise NotImplementedError

                if eaf_item[0][0].text is None:
                    continue

                text_source_str = (

                    ' '.join(
                        item.text
                        for item in eaf_item[0]
                        if item.text))

                token_list = []

                for text_str in re.split(r'\s+', text_source_str):

                    last_index = 0

                    for match in re.finditer(r'\b\S+\b', text_str):

                        if match.start() > last_index:
                            token_list.append(text_str[last_index : match.start()])

                        if match.end() > match.start():
                            token_list.append(match.group())

                        last_index = match.end()

                    if last_index < len(text_str):
                        token_list.append(text_str[last_index :])

                xlat_list = []
                xcript_list = []
                word_list = []

                for key, value in eaf_item[2].items():

                    if (key.text is None and
                        all(item.text is None for item in value)):

                        continue

                    if key.tier != 'translation':

                        log.warning(f'\nkey: {key}')
                        raise NotImplementedError

                    xlat = key.text

                    xcript = None
                    word = None

                    for item in value:

                        if item.tier == 'transcription':
                            xcript = item.text

                        elif item.tier == 'word':
                            word = item.text

                    xlat_list.append(xlat)
                    xcript_list.append(xcript)
                    word_list.append(word)

                log.debug(
                    f'\ntext: {repr(eaf_item[0][0].text)}'
                    f'\ntoken_list: {token_list}'
                    f'\nxlat_list: {xlat_list}'
                    f'\nxcript_list: {xcript_list}'
                    f'\nword_list: {word_list}')

                # Aligning words to text tokens.

                xcript_alignment = (

                    CreateValencyData.align(
                        token_list, xcript_list, debug_flag))

                word_alignment = (

                    CreateValencyData.align(
                        token_list, word_list, debug_flag))

                (distance, word_token_dict) = (

                    min(
                        word_alignment,
                        xcript_alignment,
                        key = lambda x: (x[0], -len(x[1]))))

                log.debug(
                    f'\ndistance: {distance}'
                    f'\nword_token_dict: {word_token_dict}' +
                    ''.join(
                        f'\n{repr(word_list[word_index])} ({word_index}) -> '
                        f'{repr(token_list[token_index])} ({token_index})'
                        for word_index, token_index in word_token_dict.items()))

                token_word_dict = {
                    token_index: word_index
                    for word_index, token_index in word_token_dict.items()}

                # Constructing phrase's data.

                token_data_list = []

                for i, token in enumerate(token_list):

                    token_dict = {'token': token}
                    token_data_list.append(token_dict)

                    word_index = token_word_dict.get(i)

                    if word_index is None:
                        continue

                    xlat = xlat_list[word_index]

                    token_dict.update({
                        'translation': xlat,
                        'transcription': xcript_list[word_index],
                        'word': word_list[word_index]})

                    if xlat is None:
                        continue

                    if verb_re.search(xlat) is not None:
                        token_dict['gr'] = 'V'

                    case_match = case_re.search(xlat)

                    if case_match is not None:

                        case_str = (
                            case_match.group(1).lower())

                        if 'gr' in token_dict:
                            token_dict['gr'] += ',' + case_str

                        else:
                            token_dict['gr'] = case_str

                instance_list = []

                for index, (lex, cs, indent, ind, r, animacy) in (

                    enumerate(
                        valency.sentence_instance_gen(
                            token_data_list, False))):

                    instance_list.append({
                        'index': index,
                        'location': (ind, r),
                        'case': cs})

                    data_case_set.add(cs)

                sentence_data = {
                    'tokens': token_data_list,
                    'instances': instance_list}

                valency_sentence_data = (

                    dbValencySentenceData(
                        source_id = valency_source_data.id,
                        data = sentence_data,
                        instance_count = len(instance_list)))

                DBSession.add(valency_sentence_data)
                DBSession.flush()

                # Generating instance info.

                for instance in instance_list:

                    token = (
                        token_data_list[instance['location'][0]])

                    xcript = token['transcription']

                    xcript_split_list = (
                        re.split('(-|\u2013|\u2014)', xcript, maxsplit = 1))

                    xcript_str = (
                        xcript_split_list[0] if len(xcript_split_list) <= 1 else
                        xcript_split_list[0] + xcript_split_list[1])

                    match = (
                        re.search('([-.][\dA-Z]+)+$', xcript_str))

                    if match:
                        xcript_str = xcript_str[:match.start() + 1]

                    verb_lex = (

                        (xcript_str or
                            token['word'] or
                            token['token'] or
                            xcript or
                            '')

                            .strip()
                            .lower())

                    if not verb_lex:
                        continue

                    instance_insert_list.append({
                        'sentence_id': valency_sentence_data.id,
                        'index': instance['index'],
                        'verb_lex': verb_lex,
                        'case_str': instance['case'].lower()})

                    # Verb grouping by translations.

                    xlat = token['translation']
                    match = re.search('[-.][\dA-Z]+', xlat)

                    if match:
                        xlat = xlat[:match.start()]

                    lex_xlat_dict[verb_lex].add(xlat)
                    xlat_lex_dict[xlat].add(verb_lex)

                log.debug(
                    '\n' +
                    pprint.pformat(
                        (valency_source_data.id, len(instance_list), sentence_data),
                        width = 192))

        # Computing and saving translation-based verb mergings.
        #
        # Bipartite graph connected components depth-first search.

        if debug_flag:

            log.debug(

                f'\nlex_xlat_dict ({len(lex_xlat_dict)}):\n' +

                pprint.pformat(
                    lex_xlat_dict, width = 144) + 

                f'\nxlat_lex_dict ({len(xlat_lex_dict)}):\n' + 

                pprint.pformat(
                    xlat_lex_dict, width = 144))

        lex_set_list = []

        lex_index_set = set()
        xlat_index_set = set()

        def f(lex_from, lex_prefix, lex_set):

            lex_index_set.add(lex_from)
            lex_set.add(lex_from)

            for xlat in lex_xlat_dict[lex_from]:

                if xlat in xlat_index_set:
                    continue

                xlat_index_set.add(xlat)

                for lex_to in xlat_lex_dict[xlat]:

                    if lex_to in lex_index_set:
                        continue

                    if diacritic_xform(lex_to)[:2] != lex_prefix:
                        continue

                    f(lex_to, lex_prefix, lex_set)

        for lex in lex_xlat_dict.keys():

            if lex in lex_index_set:
                continue

            lex_prefix = (
                diacritic_xform(lex)[:2])

            lex_set = set()

            xlat_index_set.clear()

            f(lex, lex_prefix, lex_set)

            lex_set_list.append(lex_set)

        if debug_flag:

            lex_set_list = (

                sorted(
                    tuple(lex_set)
                    for lex_set in lex_set_list))

            log.debug(

                '\nlex_set_list:\n' +

                pprint.pformat(
                    lex_set_list, width = 144))

        merge_insert_list = []

        for lex_set in lex_set_list:

            if len(lex_set) <= 1:
                continue

            merge_id = (
                DBSession.execute(dbValencyMergeIdSequence))

            for verb_lex in lex_set:

                merge_insert_list.append({
                    'perspective_client_id': perspective_id[0],
                    'perspective_object_id': perspective_id[1],
                    'verb_lex': verb_lex,
                    'merge_id': merge_id})

        if merge_insert_list:

            DBSession.execute(

                dbValencyMergeData.__table__
                    .insert()
                    .values(merge_insert_list))

    @staticmethod
    def process(
        info,
        perspective_id,
        debug_flag):

        order_case_set = (

            set([
                'nom', 'acc', 'gen', 'ad', 'abl', 'dat', 'ab', 'ins', 'car', 'term', 'cns', 'com',
                'comp', 'trans', 'sim', 'par', 'loc', 'prol', 'in', 'ill', 'el', 'egr', 'lat',
                'allat']))

        data_case_set = set()
        instance_insert_list = []

        CreateValencyData.process_parser(
            perspective_id,
            data_case_set,
            instance_insert_list,
            debug_flag)

        CreateValencyData.process_eaf(
            info,
            perspective_id,
            data_case_set,
            instance_insert_list,
            debug_flag)

        if instance_insert_list:

            DBSession.execute(

                dbValencyInstanceData.__table__
                    .insert()
                    .values(instance_insert_list))

        log.debug(
            f'\ndata_case_set:\n{data_case_set}'
            f'\ndata_case_set - order_case_set:\n{data_case_set - order_case_set}'
            f'\norder_case_set - data_case_set:\n{order_case_set - data_case_set}')

        return len(instance_insert_list)

    @staticmethod
    def test(
        info, debug_flag):

        parser_result_query = (

            DBSession

                .query(
                    dbLexicalEntry.parent_client_id,
                    dbLexicalEntry.parent_object_id)

                .filter(
                    dbLexicalEntry.marked_for_deletion == False,
                    dbEntity.parent_client_id == dbLexicalEntry.client_id,
                    dbEntity.parent_object_id == dbLexicalEntry.object_id,
                    dbEntity.marked_for_deletion == False,
                    dbEntity.content.op('~*')('.*\.(doc|docx|odt)'),
                    dbPublishingEntity.client_id == dbEntity.client_id,
                    dbPublishingEntity.object_id == dbEntity.object_id,
                    dbPublishingEntity.published == True,
                    dbPublishingEntity.accepted == True,
                    dbParserResult.entity_client_id == dbEntity.client_id,
                    dbParserResult.entity_object_id == dbEntity.object_id,
                    dbParserResult.marked_for_deletion == False)

                .group_by(
                    dbLexicalEntry.parent_client_id,
                    dbLexicalEntry.parent_object_id))

        eaf_corpus_query = (

            DBSession

                .query(
                    dbLexicalEntry.parent_client_id,
                    dbLexicalEntry.parent_object_id)

                .filter(
                    dbLexicalEntry.marked_for_deletion == False,
                    dbEntity.parent_client_id == dbLexicalEntry.client_id,
                    dbEntity.parent_object_id == dbLexicalEntry.object_id,
                    dbEntity.marked_for_deletion == False,
                    dbEntity.content.ilike('%.eaf'),
                    dbEntity.additional_metadata.contains({'data_type': 'elan markup'}),
                    dbPublishingEntity.client_id == dbEntity.client_id,
                    dbPublishingEntity.object_id == dbEntity.object_id,
                    dbPublishingEntity.published == True,
                    dbPublishingEntity.accepted == True)

                .group_by(
                    dbLexicalEntry.parent_client_id,
                    dbLexicalEntry.parent_object_id))

        valency_data_query = (

            DBSession

                .query(
                    dbValencySourceData.perspective_client_id,
                    dbValencySourceData.perspective_object_id)

                .distinct())

        perspective_list = (

            DBSession

                .query(
                    dbPerspective)

                .filter(
                    dbPerspective.marked_for_deletion == False,

                    tuple_(
                        dbPerspective.client_id,
                        dbPerspective.object_id)

                        .notin_(
                            DBSession.query(valency_data_query.cte())),

                    tuple_(
                        dbPerspective.client_id,
                        dbPerspective.object_id)

                        .in_(
                            union(
                                DBSession.query(parser_result_query.cte()),
                                DBSession.query(eaf_corpus_query.cte()))))

                .order_by(
                    dbPerspective.client_id,
                    dbPerspective.object_id)

                .all())

        import random
        random.shuffle(perspective_list)

        for perspective in perspective_list:

            log.debug(
                f'\nperspective_id: {perspective.id}')

            CreateValencyData.process(
                info, perspective.id, debug_flag)

            if utils.get_resident_memory() > 2 * 2**30:
                break

    @staticmethod
    def mutate(
        root,
        info,
        perspective_id,
        debug_flag = False):

        try:

            client_id = info.context.client_id
            client = DBSession.query(Client).filter_by(id = client_id).first()

            if not client:

                return (

                    ResponseError(
                        message = 'Only registered users can create valency data.'))

            if debug_flag and client.user_id != 1:

                return (

                    ResponseError(
                        message = 'Only administrator can use debug mode.'))

            perspective = (
                DBSession.query(dbPerspective).filter_by(
                    client_id = perspective_id[0], object_id = perspective_id[1]).first())

            if not perspective:

                return (

                    ResponseError(
                        message = 'No perspective {}/{} in the system.'.format(*perspective_id)))

            dictionary = perspective.parent

            locale_id = info.context.locale_id or 2

            dictionary_name = dictionary.get_translation(locale_id)
            perspective_name = perspective.get_translation(locale_id)

            full_name = dictionary_name + ' \u203a ' + perspective_name

            if dictionary.marked_for_deletion:

                return (

                    ResponseError(message =
                        'Dictionary \'{}\' {}/{} of perspective \'{}\' {}/{} is deleted.'.format(
                            dictionary_name,
                            dictionary.client_id,
                            dictionary.object_id,
                            perspective_name,
                            perspective.client_id,
                            perspective.object_id)))

            if perspective.marked_for_deletion:

                return (

                    ResponseError(message =
                        'Perspective \'{}\' {}/{} is deleted.'.format(
                            full_name,
                            perspective.client_id,
                            perspective.object_id)))

            CreateValencyData.process(
                info,
                perspective_id,
                debug_flag)

            if False:

                CreateValencyData.test(
                    info,
                    debug_flag)

            return (

                CreateValencyData(
                    triumph = True))

        except Exception as exception:

            traceback_string = (

                ''.join(
                    traceback.format_exception(
                        exception, exception, exception.__traceback__))[:-1])

            log.warning('create_valency_data: exception')
            log.warning(traceback_string)

            transaction.abort()

            return (

                ResponseError(
                    'Exception:\n' + traceback_string))


class SaveValencyData(graphene.Mutation):

    class Arguments:

        perspective_id = LingvodocID(required = True)
        debug_flag = graphene.Boolean()

    triumph = graphene.Boolean()
    data_url = graphene.String()

    @staticmethod
    def get_annotation_data(perspective_id):

        # Getting valency annotation data.

        annotation_list = (

            DBSession

                .query(
                    dbValencyAnnotationData)

                .filter(
                    dbValencyAnnotationData.accepted != None,
                    dbValencyAnnotationData.instance_id == dbValencyInstanceData.id,
                    dbValencyInstanceData.sentence_id == dbValencySentenceData.id,
                    dbValencySentenceData.source_id == dbValencySourceData.id,
                    dbValencySourceData.perspective_client_id == perspective_id[0],
                    dbValencySourceData.perspective_object_id == perspective_id[1])

                .all())

        instance_id_set = set()
        user_id_set = set()

        for annotation in annotation_list:

            instance_id_set.add(annotation.instance_id)
            user_id_set.add(annotation.user_id)

        instance_list = []

        if instance_id_set:

            instance_list = (

                DBSession

                    .query(
                        dbValencyInstanceData)

                    .filter(
                        dbValencyInstanceData.id.in_(

                            utils.values_query(
                                instance_id_set, models.SLBigInteger)))

                    .all())

        user_list = []

        if user_id_set:

            user_list = (

                DBSession

                    .query(
                        dbUser.id, dbUser.name)

                    .filter(
                        dbUser.id.in_(

                            utils.values_query(
                                user_id_set, models.SLBigInteger)))

                    .all())

        sentence_id_set = (
            set(instance.sentence_id for instance in instance_list))

        sentence_list = []

        if sentence_id_set:

            sentence_list = (

                DBSession

                    .query(
                        dbValencySentenceData)

                    .filter(
                        dbValencySentenceData.id.in_(

                            utils.values_query(
                                sentence_id_set, models.SLBigInteger)))

                    .all())

        # Preparing valency annotation data.

        sentence_data_list = []

        for sentence in sentence_list:

            sentence_data = sentence.data
            sentence_data['id'] = sentence.id

            sentence_data_list.append(sentence_data)

        instance_data_list = [

            {'id': instance.id,
                'sentence_id': instance.sentence_id,
                'index': instance.index,
                'verb_lex': instance.verb_lex,
                'case_str': instance.case_str}

                for instance in instance_list]

        annotation_data_list = [

            {'instance_id': annotation.instance_id,
                'user_id': annotation.user_id,
                'accepted': annotation.accepted}

                for annotation in annotation_list]

        user_data_list = [

            {'id': user.id,
                'name': user.name}

                for user in user_list]

        return {
            'sentence_list': sentence_data_list,
            'instance_list': instance_data_list,
            'annotation_list': annotation_data_list,
            'user_list': user_data_list}

    @staticmethod
    def mutate(
        root,
        info,
        perspective_id,
        debug_flag = False):

        try:

            client_id = info.context.client_id
            client = DBSession.query(Client).filter_by(id = client_id).first()

            if not client:

                return (

                    ResponseError(
                        message = 'Only registered users can create valency data.'))

            if debug_flag and client.user_id != 1:

                return (

                    ResponseError(
                        message = 'Only administrator can use debug mode.'))

            perspective = (
                DBSession.query(dbPerspective).filter_by(
                    client_id = perspective_id[0], object_id = perspective_id[1]).first())

            if not perspective:

                return (

                    ResponseError(
                        message = 'No perspective {}/{} in the system.'.format(*perspective_id)))

            dictionary = perspective.parent

            locale_id = info.context.locale_id or 2

            dictionary_name = dictionary.get_translation(locale_id)
            perspective_name = perspective.get_translation(locale_id)

            full_name = dictionary_name + ' \u203a ' + perspective_name

            if dictionary.marked_for_deletion:

                return (

                    ResponseError(message =
                        'Dictionary \'{}\' {}/{} of perspective \'{}\' {}/{} is deleted.'.format(
                            dictionary_name,
                            dictionary.client_id,
                            dictionary.object_id,
                            perspective_name,
                            perspective.client_id,
                            perspective.object_id)))

            if perspective.marked_for_deletion:

                return (

                    ResponseError(message =
                        'Perspective \'{}\' {}/{} is deleted.'.format(
                            full_name,
                            perspective.client_id,
                            perspective.object_id)))

            # Getting valency annotation data.

            data_dict = (
                SaveValencyData.get_annotation_data(perspective_id))

            # Saving valency annotation data as zipped JSON.

            current_time = (
                time.time())

            current_date = (
                datetime.datetime.utcfromtimestamp(current_time))

            zip_date = (
                current_date.year,
                current_date.month,
                current_date.day,
                current_date.hour,
                current_date.minute,
                current_date.second)

            storage_temporary = (
                info.context.request.registry.settings['storage']['temporary'])

            host = storage_temporary['host']
            bucket = storage_temporary['bucket']

            minio_client = (
                    
                minio.Minio(
                    host,
                    access_key = storage_temporary['access_key'],
                    secret_key = storage_temporary['secret_key'],
                    secure = True))

            temporary_file = (
                    
                tempfile.NamedTemporaryFile(
                    delete = False))

            zip_file = (

                zipfile.ZipFile(
                    temporary_file,
                    'w',
                    compression = zipfile.ZIP_DEFLATED,
                    compresslevel = 9))

            zip_info = (

                zipfile.ZipInfo(
                    'data.json', zip_date))

            zip_info.compress_type = zipfile.ZIP_DEFLATED

            with zip_file.open(
                zip_info, 'w') as binary_data_file:

                with io.TextIOWrapper(
                    binary_data_file, 'utf-8') as text_data_file:

                    json.dump(
                        data_dict,
                        text_data_file,
                        ensure_ascii = False,
                        sort_keys = True,
                        indent = 2)

            zip_file.close()
            temporary_file.close()

            if debug_flag:

                shutil.copy(
                    temporary_file.name,
                    '__data__.json.zip')

            object_name = (

                storage_temporary['prefix'] +
            
                '/'.join((
                    'valency_data',
                    '{:.6f}'.format(current_time),
                    'data.json.zip')))

            (etag, version_id) = (

                minio_client.fput_object(
                    bucket,
                    object_name,
                    temporary_file.name))

            os.remove(
                temporary_file.name)

            url = (

                '/'.join((
                    'https:/',
                    host,
                    bucket,
                    object_name)))

            return (

                SaveValencyData(
                    triumph = True,
                    data_url = url))

        except Exception as exception:

            traceback_string = (

                ''.join(
                    traceback.format_exception(
                        exception, exception, exception.__traceback__))[:-1])

            log.warning('save_valency_data: exception')
            log.warning(traceback_string)

            transaction.abort()

            return (

                ResponseError(
                    'Exception:\n' + traceback_string))


class SetValencyAnnotation(graphene.Mutation):

    class ValencyInstanceAnnotation(graphene.types.Scalar):

        @staticmethod
        def identity(value):
            return value

        serialize = identity
        parse_value = identity

        @staticmethod
        def parse_literal(ast):

            if not isinstance(ast, ListValue) or len(ast.values) != 2:
                return None

            a_value, b_value = ast.values

            if (not isinstance(a_value, IntValue) or
                not isinstance(b_value, BooleanValue)):
                return None

            return [int(a_value.value), bool(b_value.value)]

    class Arguments:
        pass

    Arguments.annotation_list = (
        graphene.List(ValencyInstanceAnnotation, required = True))

    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):

        try:

            client_id = info.context.client_id
            client = DBSession.query(Client).filter_by(id = client_id).first()

            if not client:

                return (

                    ResponseError(
                        message = 'Only registered users can set valency annotations.'))

            annotation_list = args['annotation_list']

            log.debug(
                f'\nuser_id: {client.user_id}'
                f'\nannotation_list: {annotation_list}')

            # NOTE:
            #
            # Directly formatting arguments in in general can be unsafe, but here it's ok because we are
            # relying on GraphQL's argument validation.

            value_list_str = (

                ', '.join(
                    '({}, {}, {})'.format(
                        instance_id, client.user_id, 'true' if accepted else 'false')
                    for instance_id, accepted in annotation_list))

            sql_str = (

                f'''
                insert into
                valency_annotation_data
                values {value_list_str}
                on conflict on constraint valency_annotation_data_pkey
                do update set accepted = excluded.accepted;
                ''')

            DBSession.execute(sql_str)

            mark_changed(DBSession())

            return (

                SetValencyAnnotation(
                    triumph = True))

        except Exception as exception:

            traceback_string = (

                ''.join(
                    traceback.format_exception(
                        exception, exception, exception.__traceback__))[:-1])

            log.warning('set_valency_annotation: exception')
            log.warning(traceback_string)

            return (

                ResponseError(
                    'Exception:\n' + traceback_string))


class ValencyVerbCases(graphene.Mutation):
    """
    Compiles valency verb and cases info.
    """

    class Arguments:

        perspective_id = LingvodocID()
        language_arg_list = ObjectVal()

        debug_flag = graphene.Boolean()

    triumph = graphene.Boolean()
    verb_data_list = graphene.List(ObjectVal)
    xlsx_url = graphene.String()

    @staticmethod
    def process_perspective(
        perspective_id,
        locale_id,
        verb_data_dict,
        language_str,
        by_perspective_flag,
        debug_flag):
        """
        Gathers and accumulates valency verb case data of a perspective.
        """

        perspective = (

            DBSession

                .query(dbPerspective)

                .filter_by(
                    client_id = perspective_id[0],
                    object_id = perspective_id[1])

                .first())

        if not perspective:

            raise (

                ResponseError(
                    message = 'No perspective {}/{} in the system.'.format(*perspective_id)))

        dictionary = perspective.parent

        dictionary_name = dictionary.get_translation(locale_id)
        perspective_name = perspective.get_translation(locale_id)

        full_name = (
            dictionary_name + ' \u203a ' + perspective_name)

        if dictionary.marked_for_deletion:

            raise (

                ResponseError(message =
                    'Dictionary \'{}\' {}/{} of perspective \'{}\' {}/{} is deleted.'.format(
                        dictionary_name,
                        dictionary.client_id,
                        dictionary.object_id,
                        perspective_name,
                        perspective.client_id,
                        perspective.object_id)))

        if perspective.marked_for_deletion:

            raise (

                ResponseError(message =
                    'Perspective \'{}\' {}/{} is deleted.'.format(
                        full_name,
                        perspective_id[0],
                        perspective_id[1])))

        if debug_flag:

            log.debug(
                '\nperspective '
                f'{dictionary.id} {repr(dictionary_name)} '
                f'{perspective.id} {repr(perspective_name)}')

        # We might need data separate by perspective.

        if by_perspective_flag:

            language_str = (
                language_str + ' \u203a\u203a ' + full_name)

        # Getting data of accepted instances and their sentences.
        #
        # Instance is accepted if it has at least one acceptance annotation.

        instance_list = (

            DBSession

                .query(
                    dbValencyInstanceData)

                .filter(
                    dbValencyAnnotationData.accepted == True,
                    dbValencyAnnotationData.instance_id == dbValencyInstanceData.id,
                    dbValencyInstanceData.sentence_id == dbValencySentenceData.id,
                    dbValencySentenceData.source_id == dbValencySourceData.id,
                    dbValencySourceData.perspective_client_id == perspective_id[0],
                    dbValencySourceData.perspective_object_id == perspective_id[1])

                .group_by(
                    dbValencyInstanceData.id)

                .all())

        sentence_id_set = (

            set(
                instance.sentence_id
                for instance in instance_list))

        sentence_list = []

        if sentence_id_set:

            sentence_list = (

                DBSession

                    .query(
                        dbValencySentenceData)

                    .filter(
                        dbValencySentenceData.id.in_(

                            utils.values_query(
                                sentence_id_set, models.SLBigInteger)))

                    .all())

        sentence_dict = {
            sentence.id: sentence
            for sentence in sentence_list}

        sentence_str_dict = {}

        # Processing each instance.

        for instance in instance_list:

            sentence_id = (
                instance.sentence_id)

            sentence = (
                sentence_dict[sentence_id])

            token_list = (
                sentence.data['tokens'])

            token_info_dict = (

                token_list[
                    sentence.data['instances'][instance.index]['location'][0]])

            verb_xlat = (

                token_info_dict.get('trans_ru') or
                token_info_dict.get('translation') or
                instance.verb_lex)

            sentence_str = (
                sentence_str_dict.get(sentence_id))

            if sentence_str is None:

                sentence_str = (

                    valency_verb_cases.get_sentence_str(
                        token_list))

                sentence_str_dict[sentence_id] = (
                    sentence_str)

            # Relying on Python dictionary insertion order preservation (assumption valid starting with
            # Python 3.7).

            verb_data_dict[
                verb_xlat][
                language_str][
                instance.case_str][
                instance.verb_lex][
                sentence_str] = None

    @staticmethod
    def get_case_verb_sentence_list(
        case_verb_dict):
        """
        Sorts case verb sentence data by cases and verbs.
        """

        case_verb_sentence_list = []

        for case, verb_sentence_dict in (

            sorted(
                case_verb_dict.items(),
                key = lambda item: CreateValencyData.case_index_dict[item[0]])):

            verb_sentence_list = (

                sorted(
                    (verb, list(sentence_dict.keys()))
                    for verb, sentence_dict in verb_sentence_dict.items()))

            verb_list = [
                verb
                for verb, sentence_list in verb_sentence_list]

            case_verb_sentence_list.append(
                (case, verb_list, verb_sentence_list))

        return case_verb_sentence_list

    @staticmethod
    def save_xlsx_file(
        info,
        workbook_stream,
        debug_flag):
        """
        Saves XLSX file.
        """

        if debug_flag:

            workbook_stream.seek(0)

            with open('valency_verb_cases.xlsx', 'wb') as xlsx_file:
                shutil.copyfileobj(workbook_stream, xlsx_file)

        storage = (
            info.context.request.registry.settings['storage'])

        storage_temporary = storage['temporary']

        host = storage_temporary['host']
        bucket = storage_temporary['bucket']

        minio_client = (

            minio.Minio(
                host,
                access_key = storage_temporary['access_key'],
                secret_key = storage_temporary['secret_key'],
                secure = True))

        current_time = time.time()

        object_name = (

            storage_temporary['prefix'] +

            '/'.join((
                'valency_verb_cases',
                '{:.6f}'.format(current_time),
                'valency_verb_cases.xlsx')))

        object_length = (
            workbook_stream.tell())

        workbook_stream.seek(0)

        (etag, version_id) = (

            minio_client.put_object(
                bucket,
                object_name,
                workbook_stream,
                object_length))

        url = (

            '/'.join((
                'https:/',
                host,
                bucket,
                object_name)))

        log.debug(
            '\nobject_name:\n{}'
            '\netag:\n{}'
            '\nversion_id:\n{}'
            '\nurl:\n{}'.format(
                object_name,
                etag,
                version_id,
                url))

        return url

    @staticmethod
    def mutate(
        root,
        info,
        perspective_id = None,
        language_arg_list = None,
        debug_flag = False):

        try:

            # Checking user and arguments.

            client_id = info.context.client_id
            client = DBSession.query(Client).filter_by(id = client_id).first()

            if not client:

                return (

                    ResponseError(
                        message = 'Only registered users can get valency verb cases info.'))

            if debug_flag and client.user_id != 1:

                return (

                    ResponseError(
                        message = 'Only administrator can use debug mode.'))

            if perspective_id is None and language_arg_list is None:

                return (

                    ResponseError(
                        message = 'Please specify either perspective or a set of languages.'))

            locale_id = info.context.locale_id

            # For a single corpus.

            if perspective_id is not None:

                verb_data_dict = (

                    collections.defaultdict(
                        lambda: collections.defaultdict(
                            lambda: collections.defaultdict(
                                lambda: collections.defaultdict(dict)))))

                try:

                    ValencyVerbCases.process_perspective(
                        perspective_id,
                        locale_id,
                        verb_data_dict,
                        None,
                        False,
                        debug_flag)

                except ResponseError as error:

                    return error

                if debug_flag:

                    log.debug(
                        '\nverb_data_dict:\n' +
                        pprint.pformat(
                            verb_data_dict, width = 192))

                verb_data_list = []

                for verb_xlat, language_dict in sorted(verb_data_dict.items()):

                    case_verb_sentence_dict = language_dict[None]

                    case_verb_sentence_list = (
                        ValencyVerbCases.get_case_verb_sentence_list(case_verb_sentence_dict))

                    verb_list = (

                        sorted(
                            set.union(
                                *(set(verb_list)
                                    for _, verb_list, _ in case_verb_sentence_list))))

                    verb_data_list.append(
                        (verb_xlat, case_verb_sentence_list, verb_list))

                if debug_flag:

                    log.debug(
                        '\nverb_data_list:\n' + 
                        pprint.pformat(
                            verb_data_list, width = 192))

                # Saving as XLSX file.

                workbook_stream = (
                    io.BytesIO())

                workbook = (
                    xlsxwriter.Workbook(
                        workbook_stream, {'in_memory': True}))

                worksheet = (
                    workbook.add_worksheet(
                        utils.sanitize_worksheet_name('Verb cases')))

                worksheet.set_column(
                    0, 0, 32)

                worksheet.set_column(
                    2, 2, 16)

                row_count = 0

                for verb_xlat, case_verb_sentence_list, _ in verb_data_list:

                    case, verb_list, _ = case_verb_sentence_list[0]

                    worksheet.write_row(
                        row_count, 0, [verb_xlat, case, ', '.join(verb_list)])

                    row_count += 1

                    for case, verb_list, _ in case_verb_sentence_list[1:]:

                        worksheet.write_row(
                            row_count, 1, [case, ', '.join(verb_list)])

                        row_count += 1

                # With sentences.

                worksheet = (

                    workbook.add_worksheet(
                        utils.sanitize_worksheet_name('Verb cases and sentences')))

                worksheet.set_column(
                    0, 0, 32)

                worksheet.set_column(
                    2, 2, 16)

                worksheet.set_column(
                    3, 3, 64)

                row_count = 0

                for verb_xlat, case_verb_sentence_list, _ in verb_data_list:

                    for case, _, verb_sentence_list in case_verb_sentence_list:

                        for verb, sentence_list in verb_sentence_list:

                            for sentence in sentence_list:

                                worksheet.write_row(
                                    row_count, 0, [verb_xlat, case, verb, sentence])

                                if debug_flag:

                                    log.debug([verb_xlat, case, verb, sentence])

                                row_count += 1

                                verb_xlat = ''
                                case = ''
                                verb = ''

                workbook.close()

                # Saving XLSX file, returning data.

                xlsx_url = (

                    ValencyVerbCases.save_xlsx_file(
                        info,
                        workbook_stream,
                        debug_flag))

                return (

                    ValencyVerbCases(
                        triumph = True,
                        verb_data_list = verb_data_list,
                        xlsx_url = xlsx_url))

            # For corpora in a set of languages.

            if language_arg_list is not None:

                log.debug(
                    '\nlanguage_arg_list:\n' +
                    pprint.pformat(
                        language_arg_list, width = 192))

                # Processing all languages with their perspective sets.

                verb_data_dict = (

                    collections.defaultdict(
                        lambda: collections.defaultdict(
                            lambda: collections.defaultdict(
                                lambda: collections.defaultdict(dict)))))

                for language_id, perspective_id_list, by_perspective_flag in language_arg_list:

                    language = (

                        DBSession

                            .query(dbLanguage)

                            .filter_by(
                                client_id = language_id[0],
                                object_id = language_id[1])

                            .first())

                    if not language:

                        return (

                            ResponseError(
                                message = 'No language {}/{} in the system.'.format(*language_id)))

                    language_name = (

                        language.get_translation(
                            locale_id))

                    if debug_flag:

                        log.debug(
                            f'\nlanguage {language.id} {repr(language_name)}')
                    
                    for perspective_id in perspective_id_list:

                        try:

                            ValencyVerbCases.process_perspective(
                                perspective_id,
                                locale_id,
                                verb_data_dict,
                                language_name,
                                by_perspective_flag,
                                debug_flag)

                        except ResponseError as error:

                            return error

                # Processing gathered verb case data, sorting by verb translations, languaged, cases and
                # verb lexemes.

                verb_data_list = []

                for verb_xlat, language_dict in sorted(verb_data_dict.items()):

                    language_list = []

                    for language_str, case_verb_sentence_dict in language_dict.items():

                        case_verb_sentence_list = (
                            ValencyVerbCases.get_case_verb_sentence_list(case_verb_sentence_dict))

                        language_list.append(
                            (language_str, case_verb_sentence_list))

                    verb_list = (

                        sorted(
                            set.union(
                                *(set(verb_list)
                                    for _, case_verb_sentence_list in language_list
                                    for _, verb_list, _ in case_verb_sentence_list))))

                    verb_data_list.append(
                        (verb_xlat, language_list, verb_list))

                if debug_flag:

                    log.debug(
                        '\nverb_data_list:\n' + 
                        pprint.pformat(
                            verb_data_list, width = 192))

                # Saving as XLSX file.

                workbook_stream = (
                    io.BytesIO())

                workbook = (
                    xlsxwriter.Workbook(
                        workbook_stream, {'in_memory': True}))

                worksheet = (
                    workbook.add_worksheet(
                        utils.sanitize_worksheet_name('Verb cases')))

                worksheet.set_column(
                    0, 0, 32)

                worksheet.set_column(
                    1, 1, 12)

                worksheet.set_column(
                    3, 3, 16)

                row_count = 0

                for verb_xlat, language_list, _ in verb_data_list:

                    for language_str, case_verb_sentence_list in language_list:

                        for case, verb_list, _ in case_verb_sentence_list:

                            worksheet.write_row(
                                row_count, 0, [verb_xlat, language_str, case, ', '.join(verb_list)])

                            row_count += 1

                            verb_xlat = ''
                            language_str = ''
                            case = ''

                # With sentences.

                worksheet = (

                    workbook.add_worksheet(
                        utils.sanitize_worksheet_name('Verb cases and sentences')))

                worksheet.set_column(
                    0, 0, 32)

                worksheet.set_column(
                    1, 1, 12)

                worksheet.set_column(
                    3, 3, 16)

                worksheet.set_column(
                    4, 4, 64)

                row_count = 0

                for verb_xlat, language_list, _ in verb_data_list:

                    for language_str, case_verb_sentence_list in language_list:

                        for case, _, verb_sentence_list in case_verb_sentence_list:

                            for verb, sentence_list in verb_sentence_list:

                                for sentence in sentence_list:

                                    worksheet.write_row(
                                        row_count, 0, [verb_xlat, language_str, case, verb, sentence])

                                    if debug_flag:

                                        log.debug([verb_xlat, language_str, case, verb, sentence])

                                    row_count += 1

                                    verb_xlat = ''
                                    language_str = ''
                                    case = ''
                                    verb = ''

                workbook.close()

                # Saving XLSX file, returning data.

                xlsx_url = (

                    ValencyVerbCases.save_xlsx_file(
                        info,
                        workbook_stream,
                        debug_flag))

                return (

                    ValencyVerbCases(
                        triumph = True,
                        verb_data_list = verb_data_list,
                        xlsx_url = xlsx_url))

        except Exception as exception:

            traceback_string = (

                ''.join(
                    traceback.format_exception(
                        exception, exception, exception.__traceback__))[:-1])

            log.warning('valency_verb_cases: exception')
            log.warning(traceback_string)

            return (

                ResponseError(
                    'Exception:\n' + traceback_string))

