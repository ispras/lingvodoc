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
    TranslationAtom,
    Field,
    PublishingEntity
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
from pyramid.request import Request


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
            # print(group)
            # if not group:
            #     group = 1
            if  group: # todo: change!!!!!
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
            entries = list()
            if can_add_tags:
                results_cursor = results_cursor\
                    .filter(BaseGroup.subject=='lexical_entries_and_entities',
                            or_(BaseGroup.action=='create', BaseGroup.action=='view'))\
                    .group_by(Entity).having(func.count('*') == 2)
                # results_cursor = list()
            else:
                results_cursor = results_cursor.filter(BaseGroup.subject=='lexical_entries_and_entities', BaseGroup.action=='view')
            # print(results_cursor)
            for item in results_cursor:
                if item.parent not in entries:
                    entries.append(item.parent)
            # print(entries)
            for entry in entries:
                if not entry.marked_for_deletion:
                    result = dict()
                    # print(entry.__class__)
                    url = request.route_url('perspective',
                                            dictionary_client_id=entry.parent.parent.client_id,
                                            dictionary_object_id=entry.parent.parent.object_id,
                                            perspective_client_id=entry.parent_client_id,
                                            perspective_object_id=entry.parent_object_id)
                    subreq = Request.blank(url)
                    subreq.method = 'GET'
                    headers = {'Cookie': request.headers['Cookie']}
                    subreq.headers = headers
                    resp = request.invoke_subrequest(subreq)
                    result = resp.json
                    result['lexical_entry'] = entry.track(False)
                    dict_tr = entry.parent.parent.get_translation(request.cookies['locale_id'])
                    result['parent_translation'] = dict_tr
                    results.append(result)
            request.response.status = HTTPOk.code
            return results
    request.response.status = HTTPBadRequest.code
    return {'error': 'search is too short'}

from sqlalchemy.sql import select
# TODO: completely broken!
@view_config(route_name='advanced_search', renderer='json', request_method='POST')
def advanced_search(request):
    from sqlalchemy import bindparam
    req = request.json
    searchstrings = req.get('searchstrings') or []

    def make_query(searchstring):

        results_cursor = DBSession.query(LexicalEntry).join(Entity.parent) \
            .join(Entity.field).join(TranslationAtom,
                                     and_(Field.translation_gist_client_id == TranslationAtom.parent_client_id,
                                          Field.translation_gist_object_id == TranslationAtom.parent_object_id)) \
            .distinct(Entity.parent_client_id, Entity.parent_object_id)
        if not searchstring['searchstring']:
            raise HTTPBadRequest
        search_parts = searchstring['searchstring'].split()
        search_expression = Entity.content.like('%' + search_parts[0] + '%')
        to_do_or = searchstring.get('search_by_or', True)

        for part in search_parts[1:]:
            search_expression = or_(search_expression, Entity.content.like('%' + part + '%'))
        if 'entity_type' in searchstring:
            search_expression = and_(search_expression, TranslationAtom.content == searchstring['entity_type'],
                                     TranslationAtom.locale_id==2)
        results_cursor = results_cursor.filter(search_expression)
        return results_cursor, to_do_or

    if not searchstrings:
        request.response.status = HTTPBadRequest.code
        return {'error': 'The query string couldn\'t be empty'}

    try:
        results_cursor, to_do_or = make_query(searchstrings[0])
    except HTTPBadRequest:
        request.response.status = HTTPBadRequest.code
        return {'error': 'The query string couldn\'t be empty'}
    pre_results = set(results_cursor.all())
    for search_string in searchstrings[1:]:
        results_cursor, to_do_or_new = make_query(search_string)
        if to_do_or:
            pre_results = pre_results or set(results_cursor.all())
        else:
            pre_results = pre_results and set(results_cursor.all())
        to_do_or = to_do_or_new

    # s = select([LexicalEntry.__table__])\
    #     .select_from(LexicalEntry.__table__.join(Entity.__table__,
    #                  and_(
    #                      LexicalEntry.__table__.c.client_id == Entity.__table__.c.parent_client_id,
    #                      LexicalEntry.__table__.c.object_id == Entity.__table__.c.parent_object_id))
    #                  .join(PublishingEntity.__table__,
    #                  and_(
    #                      Entity.__table__.c.client_id == PublishingEntity.__table__.c.client_id,
    #                      Entity.__table__.c.object_id == PublishingEntity.__table__.c.object_id))) \
    #     .where(and_(LexicalEntry.__table__.c.client_id == bindparam('client_id'),
    #                 LexicalEntry.__table__.c.object_id == bindparam('object_id')))
    #
    # DBSession.query(LexicalEntry).filter(or_())
    #
    # results = [{"client_id":o[0], "object_id":o[1]} for o in list(results)]
    # res = DBSession.execute(s, results)
    #
    # # results_cursor = DBSession.query(LexicalEntry) \
    # #     .options(joinedload('entity').subqueryload('publishingentity')) \
    # #     .filter(tuple_(LexicalEntry.client_id, LexicalEntry.object_id).in_(results))
    results = list()

    lexes_composite_list = [(lex.client_id, lex.object_id, lex.parent_client_id, lex.parent_object_id,
                             lex.marked_for_deletion, lex.additional_metadata,
                             lex.additional_metadata.get('came_from')
                             if lex.additional_metadata and 'came_from' in lex.additional_metadata else None)
                            for lex in pre_results]

    results = LexicalEntry.track_multiple(True, lexes_composite_list, int(request.cookies.get('locale_id') or 2))

    # for entry in pre_results:
    #     results.append(entry.track(False, int(request.cookies.get('locale_id') or 2)))
        # tmp_result = dict()
        # # tmp_result['lexical_entry'] = item.track(True)
        # tmp_result['lex_client_id'] = item.client_id
        # tmp_result['lex_object_id'] = item.object_id
        # tmp_result['client_id'] = item.parent_client_id
        # tmp_result['object_id'] = item.parent_object_id
        # perspective_tr = item.parent.get_translation(2)
        # tmp_result['translation'] = perspective_tr
        # tmp_result['is_template'] = item.parent.is_template
        # tmp_result['status'] = item.parent.state
        # tmp_result['marked_for_deletion'] = item.parent.marked_for_deletion
        # tmp_result['parent_client_id'] = item.parent.parent_client_id
        # tmp_result['parent_object_id'] = item.parent.parent_object_id
        # dict_tr = item.parent.parent.get_translation(2)
        # tmp_result['parent_translation'] = dict_tr
        # results.append(tmp_result)
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