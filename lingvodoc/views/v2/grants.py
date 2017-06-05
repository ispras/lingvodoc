#
# from lingvodoc.exceptions import CommonException
# from lingvodoc.models import (
#     BaseGroup,
#     Client,
#     DBSession,
#     Group,
#     Language,
#     User,
#     Grant,
# )
#
# from lingvodoc.views.v2.utils import (
#     all_languages,
#     cache_clients,
#     check_for_client,
#     get_user_by_client_id,
#     group_by_languages,
#     group_by_organizations,
#     user_counter
# )
#
# from pyramid.httpexceptions import (
#     HTTPBadRequest,
#     HTTPConflict,
#     HTTPForbidden,
#     HTTPFound,
#     HTTPInternalServerError,
#     HTTPNotFound,
#     HTTPOk
# )
# from pyramid.renderers import render_to_response
# from pyramid.request import Request
# from pyramid.response import Response
# from pyramid.security import authenticated_userid
# from pyramid.view import view_config
#
# import sqlalchemy
# from sqlalchemy import (
#     func,
#     tuple_,
#     case
# )
# from sqlalchemy.exc import IntegrityError
#
# import datetime
# import json
# from sqlalchemy.orm.exc import NoResultFound
# from lingvodoc.views.v2.utils import json_request_errors, translation_atom_decorator, add_user_to_group, check_client_id
# from lingvodoc.views.v2.delete import real_delete_translation_gist
# # search (filter by input, type and (?) locale)
#
#
# def grant_contents(grant):
#     result = dict()
#     return result
#
#
#
# @view_config(route_name='all_grants', renderer='json', request_method='GET', permission='view')
# def all_grants(request):
#     response = list()
#     grants = DBSession.query(Grant).order_by(Grant.grant_number).all()
#     for grant in grants:
#         response.append(grant_contents(grant))
#     return response
#
# @view_config(route_name='grant', renderer='json', request_method='GET')
# def view_grant(request):
#     response = dict()
#     grant_id = request.matchdict.get('id')
#     grant = DBSession.query(Grant).filter_by(id=grant_id).first()
#     if grant:
#         response = grant_id(grant)
#         return response
#     request.response.status = HTTPNotFound.code
#     return {'error': str("No such grant in the system")}
#
#
# @view_config(route_name='grant', renderer='json', request_method='DELETE', permission='admin')  # delete grant???
# def delete_grant(request):
#     response = dict()
#     grant_id = request.matchdict.get('id')
#     grant = DBSession.query(Grant).filter_by(id=grant_id).first()
#     if grant:
#         DBSession.delete(grant)
#         request.response.status = HTTPOk.code
#         return response
#     request.response.status = HTTPNotFound.code
#     return {'error': str("No such grant in the system")}
#
#
# @view_config(route_name='create_grant', renderer='json', request_method='POST', permission='create')
# def create_grant(request):
#     try:
#         variables = {'auth': request.authenticated_userid}
#         #
#         # req = request.json_body
#         # object_id = req.get('object_id', None)
#         # type = req['type']
#         # client = DBSession.query(Client).filter_by(id=variables['auth']).first()
#         #
#         # if not client:
#         #     raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
#         #                    variables['auth'])
#         # user = DBSession.query(User).filter_by(id=client.user_id).first()
#         # if not user:
#         #     raise CommonException("This client id is orphaned. Try to logout and then login once more.")
#         # client_id = variables['auth']
#         # if 'client_id' in req:
#         #     if check_client_id(authenticated = client.id, client_id=req['client_id']):
#         #         client_id = req['client_id']
#         #     else:
#         #         request.response.status_code = HTTPBadRequest
#         #         return {'error': 'client_id from another user'}
#         # translationgist = TranslationGist(client_id=client_id,object_id=object_id, type=type)
#         # DBSession.add(translationgist)
#         # DBSession.flush()
#         # basegroups = list()
#         # basegroups.append(DBSession.query(BaseGroup).filter_by(name="Can delete translationgist").first())
#         # if not object_id:
#         #     groups = []
#         #     for base in basegroups:
#         #         group = Group(subject_client_id=translationgist.client_id, subject_object_id=translationgist.object_id, parent=base)
#         #         groups += [group]
#         #     for group in groups:
#         #         add_user_to_group(user, group)
#         # request.response.status = HTTPOk.code
#         # return {'object_id': translationgist.object_id,
#         #         'client_id': translationgist.client_id}
#     except KeyError as e:
#         request.response.status = HTTPBadRequest.code
#         return {'error': str(e)}
#
#     except IntegrityError as e:
#         request.response.status = HTTPInternalServerError.code
#         return {'error': str(e)}
#
#     except CommonException as e:
#         request.response.status = HTTPConflict.code
#         return {'error': str(e)}
