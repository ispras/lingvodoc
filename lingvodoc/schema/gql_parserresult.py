import base64
import tempfile
import urllib

import graphene
import transaction
from sqlalchemy import create_engine

from lingvodoc.cache.caching import TaskStatus
from lingvodoc.queue.celery import celery
from lingvodoc.schema.gql_entity import Entity
from lingvodoc.schema.gql_holders import LingvodocID, LingvodocObjectType, AdditionalMetadata, CreatedAt, \
    MarkedForDeletion, fetch_object, client_id_check, CompositeIdHolder, ObjectVal, ResponseError
from lingvodoc.models import (
    DBSession,
    ParserResult as dbParserResult,
    Entity as dbEntity,
    Parser as dbParser,
    Client,
    LexicalEntry as dbLexicalEntry
)
from lingvodoc.schema.gql_parser import Parser
from lingvodoc.utils.creation import create_parser_result, async_create_parser_result
from lingvodoc.schema.gql_parser import ParameterType
import lingvodoc.utils.doc_parser as ParseMethods

from lingvodoc.cache.caching import CACHE
from bs4 import BeautifulSoup
import re

from lingvodoc.utils.verification import check_is_admin

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


        # entity = DBSession.query(dbEntity). \
        #     filter_by(client_id=entity_id[0], object_id=entity_id[1]).first()
        entity = CACHE.get(objects =
            {
                dbEntity : (entity_id, )
            },
        DBSession=DBSession)
        if not entity:
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

        if not check_is_admin(user_id):
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
        info.context.acl_check(info.context,
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
    if parse_method.find("timarkh") != -1:
        result = method(text)
    elif parse_method.find("apertium") != -1:
        result = method(text, apertium_path)
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
    result = old_result
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

    from lingvodoc.cache.caching import initialize_cache
    engine = create_engine(sqlalchemy_url)
    DBSession.configure(bind=engine)
    initialize_cache(cache_kwargs)
    global CACHE
    from lingvodoc.cache.caching import CACHE
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
        reexecute = graphene.Boolean()
        synchronous = graphene.Boolean()

    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):

        parser_result_id = args.get('id')
        element_id = args.get('element_id')
        content_from_args = args.get('content')
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








