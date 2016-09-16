__author__ = 'alexander'

from lingvodoc.models import (
    BaseGroup,
    Client,
    DBSession,
    DictionaryPerspective,
    Group,
    LexicalEntry,
    User,
    Entity,
    TranslationAtom
)

from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPOk
)
from pyramid.view import view_config

from sqlalchemy import (
    func,
    or_,
    and_,
    tuple_
)
from sqlalchemy.orm import joinedload, subqueryload


# TODO: completely broken!
@view_config(route_name='basic_search', renderer='json', request_method='GET')
def basic_search(request):
    can_add_tags = request.params.get('can_add_tags')
    searchstring = request.params.get('searchstring')
    perspective_client_id = request.params.get('perspective_client_id')
    perspective_object_id = request.params.get('perspective_object_id')
    if searchstring:
        if len(searchstring) >= 2:
            searchstring = request.params.get('searchstring')
            group = DBSession.query(Group).filter(Group.subject_override == True).join(BaseGroup)\
                    .filter(BaseGroup.subject=='lexical_entries_and_entities', BaseGroup.action=='view')\
                    .join(User, Group.users).join(Client)\
                    .filter(Client.id == request.authenticated_userid).first()
            if group:
                results_cursor = DBSession.query(Entity).filter(Entity.content.like('%'+searchstring+'%'))
                # results_cursor = list()
                if perspective_client_id and perspective_object_id:
                    results_cursor = results_cursor.join(LexicalEntry)\
                        .join(DictionaryPerspective)\
                        .filter(DictionaryPerspective.client_id == perspective_client_id,
                                DictionaryPerspective.object_id == perspective_object_id)
            else:
                results_cursor = DBSession.query(Entity)\
                    .join(Entity.parent)\
                    .join(DictionaryPerspective)
                # results_cursor = list()
                if perspective_client_id and perspective_object_id:
                    results_cursor = results_cursor.filter(DictionaryPerspective.client_id == perspective_client_id,
                                DictionaryPerspective.object_id == perspective_object_id)
                results_cursor = results_cursor.join(Group, and_(DictionaryPerspective.client_id == Group.subject_client_id, DictionaryPerspective.object_id == Group.subject_object_id ))\
                    .join(BaseGroup)\
                    .join(User, Group.users)\
                    .join(Client)\
                    .filter(Client.id == request.authenticated_userid, Entity.content.like('%'+searchstring+'%'))
            results = []
            entries = set()
            if can_add_tags:
                results_cursor = results_cursor\
                    .filter(BaseGroup.subject=='lexical_entries_and_entities',
                            or_(BaseGroup.action=='create', BaseGroup.action=='view'))\
                    .group_by(Entity).having(func.count('*') == 2)
                # results_cursor = list()
            else:
                results_cursor = results_cursor.filter(BaseGroup.subject=='lexical_entries_and_entities', BaseGroup.action=='view')
            for item in results_cursor:
                print(item.content)
                entries.add(item.parent)
            for entry in entries:
                if not entry.marked_for_deletion:
                    result = dict()
                    result['lexical_entry'] = entry.track(False)
                    result['client_id'] = entry.parent_client_id
                    result['object_id'] = entry.parent_object_id
                    perspective_tr = entry.parent.get_translation(request.cookies['locale_id'])
                    result['translation'] = perspective_tr
                    result['is_template'] = entry.parent.is_template
                    result['state_translation_gist_client_id'] = entry.parent.state_translation_gist_client_id
                    result['state_translation_gist_object_id'] = entry.parent.state_translation_gist_object_id
                    status = DBSession.query(TranslationAtom).filter_by(
                        parent_client_id = entry.parent.state_translation_gist_client_id,
                        parent_object_id = entry.parent.state_translation_gist_client_id,
                        locale_id=request.cookies['locale_id']
                    ).first()
                    if status:
                        result['status'] = status.content
                    result['marked_for_deletion'] = entry.parent.marked_for_deletion
                    result['parent_client_id'] = entry.parent.parent_client_id
                    result['parent_object_id'] = entry.parent.parent_object_id
                    dict_tr = entry.parent.parent.get_translation(request.cookies['locale_id'])
                    result['parent_translation'] = dict_tr
                    results.append(result)
            request.response.status = HTTPOk.code
            return results
    request.response.status = HTTPBadRequest.code
    return {'error': 'search is too short'}


# TODO: completely broken!
@view_config(route_name='advanced_search', renderer='json', request_method='POST')
def advanced_search(request):
    req = request.json
    searchstrings = req.get('searchstrings') or []

    def make_expression_component(searchstring):
        if not searchstring['searchstring']:
            raise HTTPBadRequest
        search_parts = searchstring['searchstring'].split()
        search_expression = Entity.content.like('%' + search_parts[0] + '%')
        for part in search_parts[1:]:
            # search_expression = or_(search_expression, Entity.content.like('%' + part + '%'))
            search_expression = list()
        if 'entity_type' in searchstring:
            # print(searchstring['entity_type'])
            # search_expression = and_(search_expression, Entity.entity_type == searchstring['entity_type'])
            search_expression = list()
        return search_expression, searchstring['search_by_or']

    if not searchstrings:
        request.response.status = HTTPBadRequest.code
        return {'error': 'The query string couldn\'t be empty'}

    try:
        search_expression, to_do_or = make_expression_component(searchstrings[0])
    except HTTPBadRequest:
        request.response.status = HTTPBadRequest.code
        return {'error': 'The query string couldn\'t be empty'}
    for search_string in searchstrings[1:]:
        if to_do_or:
            operator_func = or_
        else:
            operator_func = and_
        tmp_expression, to_do_or = make_expression_component(search_string)
        search_expression = operator_func(search_expression, tmp_expression)

    # results_cursor = DBSession.query(LevelOneEntity.parent_client_id, Entity.parent_object_id) \
    #     .distinct(Entity.parent_client_id, Entity.parent_object_id) \
    #     .filter(search_expression)
    results_cursor = list()
    tmp_list = list()
    for item in results_cursor.all():
        tmp_list.append(item)

    results_cursor = DBSession.query(LexicalEntry) \
        .options(joinedload('entity').subqueryload('publishentity'))
        # .filter(tuple_(LexicalEntry.client_id, LexicalEntry.object_id).in_(tmp_list))
    result_list = list()

    results = list()
    for item in results_cursor.all():
        if (item.client_id, item.object_id) in tmp_list:
            tmp_result = dict()
            tmp_result['lexical_entry'] = item.track(True)
            tmp_result['client_id'] = item.parent_client_id
            tmp_result['object_id'] = item.parent_object_id
            perspective_tr = item.parent.get_translation(request)
            tmp_result['translation_string'] = perspective_tr['translation_string']
            tmp_result['translation'] = perspective_tr['translation']
            tmp_result['is_template'] = item.parent.is_template
            tmp_result['status'] = item.parent.state
            tmp_result['marked_for_deletion'] = item.parent.marked_for_deletion
            tmp_result['parent_client_id'] = item.parent.parent_client_id
            tmp_result['parent_object_id'] = item.parent.parent_object_id
            dict_tr = item.parent.parent.get_translation(request)
            tmp_result['parent_translation_string'] = dict_tr['translation_string']
            tmp_result['parent_translation'] = dict_tr['translation']
            results.append(tmp_result)
    request.response.status = HTTPOk.code
    return results


# TODO: completely broken!
@view_config(route_name='entity_metadata_search', renderer='json', request_method='GET')
def entity_metadata_search(request):  # TODO: test
    # TODO: add same check for permission as in basic_search
    searchstring = request.params.get('searchstring')
    if type(searchstring) != str:
        searchstring = str(searchstring)
    searchtype = request.params.get('searchtype')
    perspective_client_id = request.params.get('perspective_client_id')
    perspective_object_id = request.params.get('perspective_object_id')
    # results_cursor = DBSession.query(LevelOneEntity)\
    #     .filter(LevelOneEntity.entity_type.like('%'+searchtype+'%'),
    #             LevelOneEntity.additional_metadata.like('%'+searchstring+'%'))
    results_cursor = list()
    if perspective_client_id and perspective_object_id:
        results_cursor = results_cursor.join(LexicalEntry).join(DictionaryPerspective).filter(DictionaryPerspective.client_id == perspective_client_id,
                                               DictionaryPerspective.object_id == perspective_object_id)
    results = []
    entries = set()
    for item in results_cursor:
        entries.add(item)
    for entry in entries:
        if not entry.marked_for_deletion:
            result = dict()
            result['client_id'] = entry.client_id
            result['object_id'] = entry.object_id
            result['additional_metadata'] = entry.additional_metadata
            results.append(result)
    return results