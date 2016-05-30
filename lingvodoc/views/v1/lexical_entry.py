__author__ = 'alexander'

from lingvodoc.exceptions import CommonException
from lingvodoc.models import (
    BaseGroup,
    Client,
    DBSession,
    DictionaryPerspective,
    Group,
    GroupingEntity,
    LevelOneEntity,
    LexicalEntry,
    User
)

from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPConflict,
    HTTPInternalServerError,
    HTTPNotFound,
    HTTPOk
)
from pyramid.request import Request
from pyramid.security import authenticated_userid
from pyramid.view import view_config

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

import logging
import random
import string
import time

log = logging.getLogger(__name__)


@view_config(route_name='get_connected_words', renderer='json', request_method='GET')
@view_config(route_name='get_connected_words_indict', renderer='json', request_method='GET')
def view_connected_words(request):  # tested, found some shit(tags here are not the same, as in view_group_entity) # TODO: fix
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    lexical_entry = DBSession.query(LexicalEntry).filter_by(client_id=client_id, object_id=object_id).first()
    if lexical_entry:
        if not lexical_entry.marked_for_deletion:
            tags = DBSession.query(GroupingEntity.content).filter_by(parent = lexical_entry).all()
            equal = False
            while not equal:
                new_tags = []
                lexes = []
                for tag in tags:
                    entity = DBSession.query(GroupingEntity).filter_by(content = tag).first()
                    path = request.route_url('get_group_entity',
                                         client_id = entity.client_id,
                                         object_id = entity.object_id)
                    subreq = Request.blank(path)
                    subreq.method = 'GET'
                    subreq.headers = request.headers
                    resp = request.invoke_subrequest(subreq)
                    for lex in resp.json['connections']:
                        if lex not in lexes:
                            lexes.append((lex['client_id'], lex['object_id']))
                for lex in lexes:
                    tags = DBSession.query(GroupingEntity.content)\
                               .filter_by(parent_client_id=lex[0],
                                          parent_object_id=lex[1]).all()
                    for tag in tags:
                        if tag not in new_tags:
                            new_tags.append(tag)

                old_tags = list(tags)
                tags = list(new_tags)
                if set(old_tags) == set(tags):
                    equal = True
            lexes = list()
            for tag in tags:
                entity = DBSession.query(GroupingEntity).filter_by(content = tag).first()
                path = request.route_url('get_group_entity',
                                         client_id = entity.client_id,
                                         object_id = entity.object_id)
                subreq = Request.blank(path)
                subreq.method = 'GET'
                subreq.headers = request.headers
                resp = request.invoke_subrequest(subreq)
                for lex in resp.json['connections']:
                    if lex not in lexes:
                        lexes.append((lex['client_id'], lex['object_id']))
            words = []
            for lex in lexes:
                path = request.route_url('lexical_entry',
                                         client_id=lex[0],
                                         object_id=lex[1])
                subreq = Request.blank(path)
                subreq.method = 'GET'
                subreq.headers = request.headers
                try:
                    resp = request.invoke_subrequest(subreq)
                    if resp.json not in words:
                        words += [resp.json]
                except:
                    pass
            response['words'] = words
            request.response.status = HTTPOk.code
            return response

    request.response.status = HTTPNotFound.code
    return {'error': str("No such lexical entry in the system")}


@view_config(route_name='add_group_indict', renderer='json', request_method='POST')  # TODO: check for permission
@view_config(route_name='add_group_entity', renderer='json', request_method='POST')
def create_group_entity(request):  # tested
    try:
        variables = {'auth': authenticated_userid(request)}
        response = dict()
        req = request.json_body
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")

        tags = []
        if 'tag' in req:
            tags += [req['tag']]
        for par in req['connections']:
            parent = DBSession.query(LexicalEntry).\
                filter_by(client_id=par['client_id'], object_id=par['object_id']).first()
            if not parent:
                request.response.status = HTTPNotFound.code
                return {'error': str("No such lexical entry in the system")}
            par_tags = DBSession.query(GroupingEntity).\
                filter_by(entity_type=req['entity_type'], parent=parent).all()
            tags += [o.content for o in par_tags]
        if not tags:
            n = 10  # better read from settings
            tag = time.ctime() + ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits)
                                         for c in range(n))
            tags += [tag]
        parents = req['connections']
        for par in parents:
            parent = DBSession.query(LexicalEntry).\
                filter_by(client_id=par['client_id'], object_id=par['object_id']).first()
            for tag in tags:
                ent = DBSession.query(GroupingEntity).\
                    filter_by(entity_type=req['entity_type'], content=tag, parent=parent).first()
                if not ent:
                    entity = GroupingEntity(client_id=client.id, object_id=DBSession.query(GroupingEntity).filter_by(client_id=client.id).count() + 1,
                                            entity_type=req['entity_type'], content=tag, parent=parent)
                    DBSession.add(entity)
                    DBSession.flush()
        log.debug('TAGS: %s', tags)
        request.response.status = HTTPOk.code
        return {}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'error': str(e)}


@view_config(route_name='create_lexical_entry', renderer='json', request_method='POST', permission='create')
def create_lexical_entry(request):  # tested
    try:
        dictionary_client_id = request.matchdict.get('dictionary_client_id')
        dictionary_object_id = request.matchdict.get('dictionary_object_id')
        perspective_client_id = request.matchdict.get('perspective_client_id')
        perspective_id = request.matchdict.get('perspective_id')

        variables = {'auth': request.authenticated_userid}
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           variables['auth'])
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")
        perspective = DBSession.query(DictionaryPerspective).\
            filter_by(client_id=perspective_client_id, object_id = perspective_id).first()
        if not perspective:
            request.response.status = HTTPNotFound.code
            return {'error': str("No such perspective in the system")}

        lexentr = LexicalEntry(object_id=DBSession.query(LexicalEntry).filter_by(client_id=client.id).count() + 1, client_id=variables['auth'],
                               parent_object_id=perspective_id, parent=perspective)
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
        perspective_id = request.matchdict.get('perspective_id')

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
            filter_by(client_id=perspective_client_id, object_id = perspective_id).first()
        if not perspective:
            request.response.status = HTTPNotFound.code
            return {'error': str("No such perspective in the system")}

        lexes_list = []
        for i in range(0, count):
            lexentr = LexicalEntry(object_id=DBSession.query(LexicalEntry).filter_by(client_id=client.id).count() + 1, client_id=variables['auth'],
                                   parent_object_id=perspective_id, parent=perspective)
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


@view_config(route_name='lexical_entry_in_perspective', renderer='json', request_method='GET', permission='view')
@view_config(route_name='lexical_entry', renderer='json', request_method='GET', permission='view')
def view_lexical_entry(request):  # TODO: test
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')

    entry = DBSession.query(LexicalEntry) \
        .options(joinedload('leveloneentity').joinedload('leveltwoentity').joinedload('publishleveltwoentity')) \
        .options(joinedload('leveloneentity').joinedload('publishleveloneentity')) \
        .options(joinedload('groupingentity').joinedload('publishgroupingentity')) \
        .options(joinedload('publishleveloneentity')) \
        .options(joinedload('publishleveltwoentity')) \
        .options(joinedload('publishgroupingentity')) \
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
                response['lexical_entry'] = entry.track(False)

                request.response.status = HTTPOk.code
                return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such lexical entry in the system")}


@view_config(route_name='move_lexical_entry', renderer='json', request_method='PATCH', permission='create')
def move_lexical_entry(request):  # TODO: test
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
        if user not in groupoverride.users:
            if user not in group.users:
                raise CommonException("You should only move to lexical entires you own")
        if parent.moved_to is None:
            if entry.moved_to is None:

                if not entry.marked_for_deletion and not parent.marked_for_deletion:
                    l1e = DBSession.query(LevelOneEntity).filter_by(parent = entry).all()
                    for entity in l1e:
                        ent = DBSession.query(LevelOneEntity)\
                            .filter_by(parent=parent, entity_type=entity.entity_type, content = entity.content)\
                            .first()
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
                    ge = DBSession.query(GroupingEntity).filter_by(parent = entry).all()
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


@view_config(route_name='move_lexical_entry_bulk', renderer='json', request_method='PATCH')
def move_lexical_entry_bulk(request):  # TODO: test
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
                                                l1e = DBSession.query(LevelOneEntity).filter_by(parent = entry).all()
                                                for entity in l1e:
                                                    ent = DBSession.query(LevelOneEntity)\
                                                        .filter_by(parent=parent,
                                                                   entity_type=entity.entity_type,
                                                                   content = entity.content)\
                                                        .first()
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
                                                ge = DBSession.query(GroupingEntity).filter_by(parent = entry).all()
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