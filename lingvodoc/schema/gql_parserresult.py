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


        entity = DBSession.query(dbEntity). \
            filter_by(client_id=entity_id[0], object_id=entity_id[1]).first()
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
        if parser.method.find("apertium") == -1:
            cur_args["apertium_path"] = ""
        else:
            msg = "The path to the folder with Apertium parsers was not provided in configuration"
            try:
                cur_args["apertium_path"] = request.registry.settings["apertium_path"]
            except KeyError:
                raise ResponseError(message=msg)
            if len(cur_args["apertium_path"]) == 0:
                raise ResponseError(message=msg)

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

            if not perspective_id:

                raise KeyError(
                    'Failed to get perspective of the parser result.',
                    (parser_result.client_id, parser_result.object_id))

            info.context.acl_check(
                'delete', 'lexical_entries_and_entities', perspective_id)

        parser_result.marked_for_deletion = True
        transaction.commit()

        return DeleteParserResult(triumph=True)


class UpdateParserResult(graphene.Mutation):
    class Arguments:
        id = LingvodocID(required=True)
        content = graphene.String()

    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):

        id = args.get('id')
        content = args.get('content')
        parser_result = DBSession.query(dbParserResult).filter_by(client_id=id[0], object_id=id[1]).first()
        if not parser_result or parser_result.marked_for_deletion:
            raise ResponseError("No such parser result in the system")

        # If not an admin, checking for permissions.

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

            if not perspective_id:

                raise KeyError(
                    'Failed to get perspective of the parser result.',
                    (parser_result.client_id, parser_result.object_id))

            info.context.acl_check('edit', 'perspective', perspective_id)

        parser_result.content = content[:]
        transaction.commit()

        return UpdateParserResult(triumph=True)

