import json

import graphene
from lingvodoc.models import (
    Parser as dbParser,
    DBSession,
    Base
)

from lingvodoc.schema.gql_holders import (
    LingvodocObjectType,
    CreatedAt,
    AdditionalMetadata, LingvodocID, client_id_check, CompositeIdHolder, fetch_object, ObjectVal,
)
from lingvodoc.utils.creation import create_parser

class ParameterType(graphene.Enum):
    Int = 1
    String = 2
    Boolean = 3
    File = 4

class Parameter(graphene.ObjectType):
    name = graphene.String()
    type = ParameterType()
    is_mandatory = graphene.Boolean()

class Parameters(graphene.Interface):
    parameters = graphene.List(Parameter)

    @fetch_object('parameters')
    def resolve_parameters(self, info):
        db_object = self.dbObject
        if not db_object.parameters:
            return None
        res_list = list()
        for parameter in db_object.parameters:
            parameter_dict = {i: None for i in Parameter().__class__.__dict__}
            new_parameter = {key: parameter[key] for key in parameter}
            parameter_dict.update(new_parameter)
            parameter_object = Parameter(**parameter_dict)
            res_list.append(parameter_object)
        return res_list

class Parser(LingvodocObjectType):

    dbType = dbParser
    name = graphene.String()

    class Meta:
        interfaces = (Parameters, CompositeIdHolder, AdditionalMetadata, CreatedAt)

    @fetch_object('name')
    def resolve_name(self, info):
        return self.dbObject.name