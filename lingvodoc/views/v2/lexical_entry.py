__author__ = 'alexander'

from lingvodoc.exceptions import CommonException
from lingvodoc.models import (
    BaseGroup,
    Client,
    DBSession,
    DictionaryPerspective,
    Group,
    LexicalEntry,
    User,
    Entity,
    Field,
    PublishingEntity,
    ObjectTOC
)
from sqlalchemy import (
    func,
    or_,
    and_,
    tuple_
)

from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPConflict,
    HTTPInternalServerError,
    HTTPNotFound,
    HTTPOk,
    HTTPForbidden
)
from pyramid.request import Request
from pyramid.security import authenticated_userid
from pyramid.view import view_config

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from lingvodoc.views.v2.delete import real_delete_lexical_entry
from lingvodoc.views.v2.utils import check_client_id

import logging
import random
import string
import time

log = logging.getLogger(__name__)


@view_config(route_name='get_connected_words', renderer='json', request_method='GET')
@view_config(route_name='get_connected_words_indict', renderer='json', request_method='GET')
def view_connected_words(request):
    response = list()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    accepted = request.params.get('accepted', False)
    if type(accepted) == str and 'false' in accepted.lower():
        accepted = False
    if accepted:
        accepted = True
    published = request.params.get('published', False)
    if type(published) == str and 'false' in published.lower():
        published = False
    if published:
        published = True
    field_client_id = int(request.params.get('field_client_id'))
    field_object_id = int(request.params.get('field_object_id'))
    lexical_entry = DBSession.query(LexicalEntry).filter_by(client_id=client_id, object_id=object_id).first()
    if lexical_entry and not lexical_entry.marked_for_deletion:
        tags = find_all_tags(lexical_entry, field_client_id, field_object_id, accepted)
        lexes = find_lexical_entries_by_tags(tags, field_client_id, field_object_id, accepted)
        lexes_composite_list = [(lex.created_at,
                                 lex.client_id, lex.object_id, lex.parent_client_id, lex.parent_object_id,
                                 lex.marked_for_deletion, lex.additional_metadata,
                                 lex.additional_metadata.get('came_from')
                                 if lex.additional_metadata and 'came_from' in lex.additional_metadata else None)
                                for lex in lexes]

        result = LexicalEntry.track_multiple(lexes_composite_list, int(request.cookies.get('locale_id') or 2),
                                             publish=published, accept=accepted)
        if published:
            result = [lex for lex in result if have_tag(lex, tags, field_client_id, field_object_id)]

        response = list(result)
        request.response.status = HTTPOk.code
        return response

    request.response.status = HTTPNotFound.code
    return {'error': str("No such lexical entry in the system")}


def have_tag(lex, tags, field_client_id, field_object_id):
    return bool([x for x in lex['contains'] if x['field_client_id'] == field_client_id and x['field_object_id'] == field_object_id and x['content'] in tags and x['published'] and x['accepted']])


def find_lexical_entries_by_tags(tags, field_client_id, field_object_id, accepted):
    result = DBSession.query(LexicalEntry) \
        .join(LexicalEntry.entity) \
        .join(Entity.publishingentity) \
        .join(Entity.field) \
        .filter(Entity.content.in_(tags),
                Entity.marked_for_deletion == False,
                Field.client_id == field_client_id,
                Field.object_id == field_object_id)
    if accepted:
        result = result.filter(PublishingEntity.accepted == True)
    result = result.all()
    return result


def find_all_tags(lexical_entry, field_client_id, field_object_id, accepted):
    tag = None
    for entity in lexical_entry.entity:
        if not entity.marked_for_deletion and entity.field_client_id == field_client_id and entity.field_object_id == field_object_id:
            if accepted:
                if not entity.publishingentity.accepted:
                    continue
            tag = entity.content
            break
    if not tag:
        return []
    else:
        tags = [tag]
        new_tags = [tag]
        while new_tags:
            lexical_entries = find_lexical_entries_by_tags(new_tags, field_client_id, field_object_id, accepted)
            new_tags = list()
            for lex in lexical_entries:
                entities = DBSession.query(Entity) \
                    .join(Entity.field) \
                    .join(Entity.publishingentity) \
                    .filter(Entity.parent == lex,
                            Field.client_id == field_client_id,
                            Field.object_id == field_object_id,
                            Entity.marked_for_deletion==False)
                if accepted:
                    entities = entities.filter(PublishingEntity.accepted == True)

                entities = entities.all()
                for entity in entities:
                    if entity.content not in tags:
                        tags.append(entity.content)
                        new_tags.append(entity.content)
        return tags


@view_config(route_name='bulk_group_entities', renderer='json', request_method='POST')
def bulk_group_entities(request):  # tested
    try:
        variables = {'auth': authenticated_userid(request)}
        response = dict()
        req = request.json_body
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        field_client_id = req['field_client_id']
        field_object_id = req['field_object_id']
        counter = req['counter']
        accepted = request.params.get('accepted', False)
        if type(accepted) == str and 'false' in accepted.lower():
            accepted = False
        if accepted:
            accepted = True
        published = request.params.get('published', False)
        if type(published) == str and 'false' in published.lower():
            published = False
        if published:
            published = True
        field = DBSession.query(Field).\
            filter_by(client_id=field_client_id, object_id=field_object_id).first()

        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")
        client.counter = counter
        DBSession.flush()
        if not field:
            request.response.status = HTTPNotFound
            return {'error': str("No such field in the system")}
        if field.data_type != 'Grouping Tag':
            raise KeyError("wrong field data type")

        for tag in req['tag_groups']:
            for tag_ent in req['tag_groups'][tag]:
                tag_entity = DBSession.query(Entity) \
                    .join(Entity.field) \
                    .filter(Entity.parent_client_id == tag_ent['parent_client_id'],
                            Entity.parent_object_id == tag_ent['parent_object_id'],
                            Field.client_id == tag_ent['field_client_id'],
                            Field.object_id == tag_ent['field_object_id'],
                            Entity.content == tag).first()
                if not tag_entity:
                    tag_entity = Entity(client_id=client.id,
                                        object_id=tag_ent['object_id'],
                                        field=field,
                                        content=tag_ent['content'],
                                        parent_client_id=tag_ent['parent_client_id'],
                                        parent_object_id=tag_ent['parent_object_id'])
                    lex = DBSession.query(LexicalEntry).filter_by(client_id=tag_ent['parent_client_id'],
                                                                  object_id=tag_ent['parent_object_id']).one()
                    group = DBSession.query(Group).join(BaseGroup).filter(
                        BaseGroup.subject == 'lexical_entries_and_entities',
                        Group.subject_client_id == lex.parent_client_id,
                        Group.subject_object_id == lex.parent_object_id,
                        BaseGroup.action == 'create').one()
                    if user in group.users:
                        tag_entity.publishingentity.accepted = True
        # if 'tag' in req:
        #     tags.append(req['tag'])

        for tag in req['tag_groups']:
            tags = list()
            tag_ent = req['tag_groups'][tag][0]
            parent = DBSession.query(LexicalEntry).\
                filter_by(client_id=tag_ent['parent_client_id'], object_id=tag_ent['parent_object_id']).first()
            if not parent:
                request.response.status = HTTPNotFound.code
                return {'error': str("No such lexical entry in the system")}
            par_tags = find_all_tags(parent, field_client_id, field_object_id, accepted)
            for tag in par_tags:
                if tag not in tags:
                    tags.append(tag)
            lexical_entries = find_lexical_entries_by_tags(tags, field_client_id, field_object_id, accepted)
            if parent not in lexical_entries:
                lexical_entries.append(parent)

            for lex in lexical_entries:
                for tag in tags:
                    tag_entity = DBSession.query(Entity) \
                        .join(Entity.field) \
                        .join(Entity.publishingentity) \
                        .filter(Entity.parent == lex,
                                Entity.marked_for_deletion == False,
                                Field.client_id == field_client_id,
                                Field.object_id == field_object_id,
                                Entity.content == tag).first()
                    if not tag_entity:
                        tag_entity = Entity(client_id=client.id,
                                            field=field, content=tag, parent=lex)

                        group = DBSession.query(Group).join(BaseGroup).filter(
                            BaseGroup.subject == 'lexical_entries_and_entities',
                            Group.subject_client_id == lex.parent_client_id,
                            Group.subject_object_id == lex.parent_object_id,
                            BaseGroup.action == 'create').one()
                        if user in group.users:
                            tag_entity.publishingentity.accepted = True
            request.response.status = HTTPOk.code
            response['counter'] = client.counter
            return response
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'error': str(e)}


@view_config(route_name='add_group_indict', renderer='json', request_method='POST')
@view_config(route_name='add_group_entity', renderer='json', request_method='POST')
def create_group_entity(request):  # tested
    try:
        variables = {'auth': authenticated_userid(request)}
        response = dict()
        req = request.json_body
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        object_id = req.get('object_id', None)
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")
        tags = list()
        if 'tag' in req:
            tags.append(req['tag'])
        field_client_id=req['field_client_id']
        field_object_id=req['field_object_id']
        field = DBSession.query(Field).\
            filter_by(client_id=field_client_id, object_id=field_object_id).first()

        if not field:
            request.response.status = HTTPNotFound.code
            return {'error': str("No such field in the system")}
        if field.data_type != 'Grouping Tag':
            raise KeyError("wrong field data type")

        for par in req['connections']:
            parent = DBSession.query(LexicalEntry).\
                filter_by(client_id=par['client_id'], object_id=par['object_id']).first()
            if not parent:
                request.response.status = HTTPNotFound.code
                return {'error': str("No such lexical entry in the system")}
            par_tags = find_all_tags(parent, field_client_id, field_object_id, False)
            for tag in par_tags:
                if tag not in tags:
                    tags.append(tag)
        if not tags:
            n = 10  # better read from settings
            tag = time.ctime() + ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits)
                                         for c in range(n))
            tags.append(tag)
        lexical_entries = find_lexical_entries_by_tags(tags, field_client_id, field_object_id, False)
        for par in req['connections']:
            parent = DBSession.query(LexicalEntry).\
                filter_by(client_id=par['client_id'], object_id=par['object_id']).first()
            if parent not in lexical_entries:
                lexical_entries.append(parent)

        for lex in lexical_entries:
            for tag in tags:
                tag_entity = DBSession.query(Entity) \
                    .join(Entity.field) \
                    .join(Entity.publishingentity) \
                    .filter(Entity.parent == lex,
                            Field.client_id == field_client_id,
                            Field.object_id == field_object_id,
                            Entity.content == tag,
                            Entity.marked_for_deletion == False).first()
                if not tag_entity:
                    tag_entity = Entity(client_id=client.id,
                                        object_id=object_id,
                                        field=field, content=tag, parent=lex)   # wait, what? this shouldn't work if given object i and more than one tag is created

                    group = DBSession.query(Group).join(BaseGroup).filter(
                        BaseGroup.subject == 'lexical_entries_and_entities',
                        Group.subject_client_id == tag_entity.parent.parent.client_id,
                        Group.subject_object_id == tag_entity.parent.parent.object_id,
                        BaseGroup.action == 'create').one()
                    if user in group.users:
                        tag_entity.publishingentity.accepted = True
        request.response.status = HTTPOk.code
        return response
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'error': str(e)}


@view_config(route_name='create_lexical_entry', renderer='json', request_method='POST')
def create_lexical_entry(request):  # tested
    try:
        dictionary_client_id = request.matchdict.get('dictionary_client_id')
        dictionary_object_id = request.matchdict.get('dictionary_object_id')
        perspective_client_id = request.matchdict.get('perspective_client_id')
        perspective_object_id = request.matchdict.get('perspective_object_id')
        try:

            object_id = request.json_body.get('object_id', None)
        except ValueError:
            object_id=None

        variables = {'auth': request.authenticated_userid}
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           variables['auth'])
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")
        perspective = DBSession.query(DictionaryPerspective).\
            filter_by(client_id=perspective_client_id, object_id = perspective_object_id).first()
        if not perspective:
            request.response.status = HTTPNotFound.code
            return {'error': str("No such perspective in the system")}

        client_id = variables['auth']
        try:

            object_id = request.json_body.get('object_id', None)
            if 'client_id' in request.json_body:
                if check_client_id(authenticated = client.id, client_id=request.json_body['client_id']):
                    client_id = request.json_body['client_id']
                else:
                    request.response.status_code = HTTPBadRequest
                    return {'error': 'client_id from another user'}
        except ValueError:
            client_id = variables['auth']

        lexentr = LexicalEntry(object_id=object_id, client_id=client_id,
                               parent_object_id=perspective_object_id, parent=perspective)
        DBSession.add(lexentr)
        DBSession.flush()

        request.response.status = HTTPOk.code
        return {'object_id': lexentr.object_id,
                'client_id': lexentr.client_id}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'error': str(e)}


@view_config(route_name='create_lexical_entry_bulk', renderer='json', request_method='POST', permission='create')
def create_lexical_entry_bulk(request):  # TODO: test
    try:
        dictionary_client_id = request.matchdict.get('dictionary_client_id')
        dictionary_object_id = request.matchdict.get('dictionary_object_id')
        perspective_client_id = request.matchdict.get('perspective_client_id')
        perspective_object_id = request.matchdict.get('perspective_object_id')

        count = request.json_body.get('count') or 0

        variables = {'auth': request.authenticated_userid}

        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           variables['auth'])
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")
        perspective = DBSession.query(DictionaryPerspective). \
            filter_by(client_id=perspective_client_id, object_id = perspective_object_id).first()
        if not perspective:
            request.response.status = HTTPNotFound.code
            return {'error': str("No such perspective in the system")}

        lexes_list = []
        for i in range(0, count):
            lexentr = LexicalEntry(client_id=variables['auth'],
                                   parent_object_id=perspective_object_id, parent=perspective)
            DBSession.add(lexentr)
            lexes_list.append(lexentr)
        DBSession.flush()
        lexes_ids_list = []
        for lexentr in lexes_list:
            lexes_ids_list.append({'client_id': lexentr.client_id, 'object_id': lexentr.object_id})

        request.response.status = HTTPOk.code
        return lexes_ids_list
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'error': str(e)}


@view_config(route_name='lexical_entry_in_perspective', renderer='json', request_method='GET')
@view_config(route_name='lexical_entry', renderer='json', request_method='GET')
def view_lexical_entry(request):  # TODO: test
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')


    entry = DBSession.query(LexicalEntry) \
        .filter_by(client_id=client_id, object_id=object_id).first()
    if entry:
        if entry.moved_to:
            url = request.route_url('lexical_entry',
                                    client_id=entry.moved_to.split("/")[0],
                                    object_id=entry.moved_to.split("/")[1])
            subreq = Request.blank(url)
            subreq.method = 'GET'
            subreq.headers = request.headers
            return request.invoke_subrequest(subreq)
        else:
            if not entry.marked_for_deletion:
                response = entry.track(False, int(request.cookies.get('locale_id') or 2))
                # response['client_id'] = entry.client_id
                # response['object_id'] = entry.object_id
                request.response.status = HTTPOk.code
                return response
            else:
                request.response.status = HTTPNotFound.code
                return {'error': 'Lexical entry is marked as deleted'}
    request.response.status = HTTPNotFound.code
    return {'error': str("No such lexical entry in the system")}


@view_config(route_name='lexical_entry_in_perspective', renderer='json', request_method='DELETE', permission='delete')
@view_config(route_name='lexical_entry', renderer='json', request_method='DELETE', permission='delete')
def delete_entity(request):
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')


    entry = DBSession.query(LexicalEntry) \
        .filter_by(client_id=client_id, object_id=object_id).first()
    if entry:
        if entry.moved_to:
            url = request.route_url('lexical_entry',
                                    client_id=entry.moved_to.split("/")[0],
                                    object_id=entry.moved_to.split("/")[1])
            subreq = Request.blank(url)
            subreq.method = 'DELETE'
            subreq.headers = request.headers
            return request.invoke_subrequest(subreq)
        else:
            if not entry.marked_for_deletion:
                if 'desktop' in request.registry.settings:
                    real_delete_lexical_entry(entry, request.registry.settings)
                else:
                    entry.marked_for_deletion = True
                    objecttoc = DBSession.query(ObjectTOC).filter_by(client_id=entry.client_id,
                                                                     object_id=entry.object_id).one()
                    objecttoc.marked_for_deletion = True
                request.response.status = HTTPOk.code
                return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such entity in the system")}


@view_config(route_name='approve_lexical_entry', renderer='json', request_method='PATCH', permission='create')
def approve_lexical_entry(request):
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')

    entry = DBSession.query(LexicalEntry).filter_by(client_id=client_id,
                                                    object_id=object_id,
                                                    marked_for_deletion=False).first()
    if entry:
        entities = DBSession.query(Entity).filter_by(parent_client_id=client_id,
                                                     parent_object_id=object_id,
                                                     marked_for_deletion=False)
        for entity in entities.all():
            entity.publishingentity.published = True

    request.response.status = HTTPOk.code
    return response

# TODO: completely broken!
@view_config(route_name='move_lexical_entry', renderer='json', request_method='PATCH', permission='create')
def move_lexical_entry(request):
    req = request.json_body
    variables = {'auth': request.authenticated_userid}
    client = DBSession.query(Client).filter_by(id=variables['auth']).first()
    if not client:
        raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                       variables['auth'])
    user = DBSession.query(User).filter_by(id=client.user_id).first()
    if not user:
        raise CommonException("This client id is orphaned. Try to logout and then login once more.")
    object_id = request.matchdict.get('object_id')
    client_id = request.matchdict.get('client_id')
    cli_id = req['client_id']
    obj_id = req['object_id']
    real_delete = req.get('real_delete')   # With great power comes great responsibility
    # Maybe there needs to be check for permission of some sort (can really delete only when updating dictionary)
    entry = DBSession.query(LexicalEntry).filter_by(client_id=client_id, object_id=object_id).first()
    parent = DBSession.query(LexicalEntry).filter_by(client_id=cli_id, object_id=obj_id).first()
    if entry and parent:
        groupoverride = DBSession.query(Group)\
            .filter_by(subject_override=True)\
            .join(BaseGroup)\
            .filter_by(subject='lexical_entries_and_entities')\
            .first()
        group = DBSession.query(Group)\
            .filter_by(subject_client_id=parent.parent_client_id, subject_object_id=parent.parent_object_id)\
            .join(BaseGroup)\
            .filter_by(subject='lexical_entries_and_entities')\
            .first()
        if user not in groupoverride.users and  user not in group.users:
                raise CommonException("You should only move to lexical entires you own")
        if parent.moved_to is None:
            if entry.moved_to is None:

                if not entry.marked_for_deletion and not parent.marked_for_deletion:
                    # l1e = DBSession.query(LevelOneEntity).filter_by(parent = entry).all()
                    l1e = list()
                    for entity in l1e:
                        # ent = DBSession.query(LevelOneEntity)\
                        #     .filter_by(parent=parent, entity_type=entity.entity_type, content = entity.content)\
                        #     .first()
                        ent = None
                        if ent:
                            entity.marked_for_deletion = True
                            if real_delete:
                                for publent in entity.publishleveloneentity:
                                    DBSession.delete(publent)  #TODO: delete objecttoc
                                DBSession.delete(entity)
                                continue
                        entity.parent = parent

                        for publent in entity.publishleveloneentity:
                            publent.marked_for_deletion = True
                            publent.parent = parent
                        DBSession.flush()
                    # ge = DBSession.query(GroupingEntity).filter_by(parent = entry).all()
                    ge = list()
                    for entity in ge:
                        entity.parent = parent
                        for publent in entity.publishgroupingentity:
                            publent.marked_for_deletion = True
                            publent.parent = parent
                        DBSession.flush()
                    entry.moved_to = str(cli_id) + '/' + str(obj_id)
                    entry.marked_for_deletion = True
                    request.response.status = HTTPOk.code
                    return {}
    request.response.status = HTTPNotFound.code
    return {'error': str("No such lexical entry in the system")}


# TODO: completely broken!
@view_config(route_name='move_lexical_entry_bulk', renderer='json', request_method='PATCH')
def move_lexical_entry_bulk(request):
    req = request.json_body
    real_delete = req.get('real_delete')  # With great power comes great responsibility
    # Maybe there needs to be check for permission of some sort (can really delete only when updating dictionary)
    variables = {'auth': request.authenticated_userid}
    client = DBSession.query(Client).filter_by(id=variables['auth']).first()
    if not client:
        raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                       variables['auth'])
    user = DBSession.query(User).filter_by(id=client.user_id).first()
    if not user:
        raise CommonException("This client id is orphaned. Try to logout and then login once more.")
    groups = DBSession.query(Group)\
        .join(BaseGroup, BaseGroup.id == Group.base_group_id)\
        .filter(BaseGroup.subject == 'lexical_entries_and_entities')\
        .filter(BaseGroup.action == 'create')\
        .join(User, Group.users)\
        .filter(User.id == user.id)\
        .group_by(Group)\
        .order_by('subject_override')\
        .all()

    wat = [o for o in groups]
    override = False
    ids = [{'client_id': o.subject_client_id,'object_id': o.subject_object_id} for o in groups]
    for group in groups:
        if group.subject_override:
            override = True
            break
    for par in req['move_list']:
        cli_id = par['client_id']
        obj_id = par['object_id']
        parent = DBSession.query(LexicalEntry).filter_by(client_id=cli_id, object_id=obj_id).first()
        can = True
        if parent:
            if not override:
                if {'client_id': parent.parent_client_id, 'object_id': parent.parent_object_id} not in ids:
                    can = False
            if can:
                for ent in par['lexical_entries']:
                    can = True
                    object_id = ent['object_id']
                    client_id = ent['client_id']
                    entry = DBSession.query(LexicalEntry).filter_by(client_id=client_id, object_id=object_id).first()
                    if entry:
                        if not override:
                            if {'client_id': entry.parent_client_id, 'object_id': entry.parent_object_id} not in ids:
                                can = False

                        if can:
                                if entry:
                                    if parent.moved_to is None:
                                        if entry.moved_to is None:

                                            if not entry.marked_for_deletion and not parent.marked_for_deletion:
                                                # l1e = DBSession.query(LevelOneEntity).filter_by(parent = entry).all()
                                                l1e = list()
                                                for entity in l1e:
                                                    # ent = DBSession.query(LevelOneEntity)\
                                                    #     .filter_by(parent=parent,
                                                    #                entity_type=entity.entity_type,
                                                    #                content = entity.content)\
                                                    #     .first()
                                                    ent = None
                                                    if ent:
                                                        entity.marked_for_deletion = True
                                                        if real_delete:
                                                            for publent in entity.publishleveloneentity:
                                                                DBSession.delete(publent)
                                                            DBSession.delete(entity)
                                                            continue
                                                    entity.parent = parent

                                                    for publent in entity.publishleveloneentity:
                                                        publent.marked_for_deletion = True
                                                        publent.parent = parent
                                                    DBSession.flush()
                                                # ge = DBSession.query(GroupingEntity).filter_by(parent = entry).all()
                                                ge = list()
                                                for entity in ge:
                                                    entity.parent = parent
                                                    for publent in entity.publishgroupingentity:
                                                        publent.marked_for_deletion = True
                                                        publent.parent = parent
                                                    DBSession.flush()
                                                entry.moved_to = str(cli_id) + '/' + str(obj_id)
                                                entry.marked_for_deletion = True
    request.response.status = HTTPOk.code
    return {}
