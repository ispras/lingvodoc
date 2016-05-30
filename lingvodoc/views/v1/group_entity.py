__author__ = 'alexander'

from lingvodoc.models import (
    DBSession,
    GroupingEntity
)

from pyramid.httpexceptions import (
    HTTPNotFound,
    HTTPOk
)
from pyramid.view import view_config


@view_config(route_name='get_group_entity', renderer='json', request_method='GET')
def view_group_entity(request):  # TODO: test
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')

    entity = DBSession.query(GroupingEntity).filter_by(client_id=client_id, object_id=object_id).first()
    if entity:
        if not entity.marked_for_deletion:
            ent = dict()
            ent['entity_type'] = entity.entity_type
            ent['tag'] = entity.content
            entities2 = DBSession.query(GroupingEntity).filter_by(content=entity.content)
            objs = []
            for entry in entities2:
                obj = {'client_id': entry.parent_client_id, 'object_id': entry.parent_object_id}
                if obj not in objs:
                    objs += [obj]
            ent['connections'] = objs
            response = ent
            request.response.status = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No entities in the system")}


@view_config(route_name='get_group_entity', renderer='json', request_method='DELETE', permission='delete')
def delete_group_entity(request):  # TODO: test
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    entities = DBSession.query(GroupingEntity).filter_by(parent_client_id=client_id, parent_object_id=object_id).all()
    if entities:
        for entity in entities:
            if not entity.marked_for_deletion:
                entity.marked_for_deletion = True
        request.response.status = HTTPOk.code
        return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such entity in the system")}