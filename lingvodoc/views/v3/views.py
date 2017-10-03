# from lingvodoc.views.v2.utils import (
#     get_user_by_client_id,
#     view_field_from_object,
#     check_client_id
# )
# from sqlalchemy.exc import IntegrityError
#
# from pyramid.response import Response
# from pyramid.view import view_config
# from lingvodoc.models import (
#     DBSession,
#     Locale,
#     TranslationAtom,
#     TranslationGist,
#     BaseGroup,
#     User,
#     DictionaryPerspective,
#     DictionaryPerspectiveToField,
#     Field,
#     Client,
#     Group,
#     UserBlobs,
#     Language,
#     ObjectTOC,
#     LexicalEntry,
#     Dictionary,
#     Entity
# )
#
# from sqlalchemy import (
#     func,
#     or_,
#     and_,
#     tuple_
# )
# from pyramid.httpexceptions import (
#     HTTPBadRequest,
#     HTTPConflict,
#     HTTPFound,
#     HTTPInternalServerError,
#     HTTPNotFound,
#     HTTPOk
# )
# from pyramid.security import authenticated_userid
# # from pyramid.chameleon_zpt import render_template_to_response
# from pyramid.renderers import render_to_response
# from lingvodoc.exceptions import CommonException
#
# import sys
# import multiprocessing
#
# if sys.platform == 'darwin':
#     multiprocessing.set_start_method('spawn')
#
# import logging
# log = logging.getLogger(__name__)
# import json
# import requests
# from pyramid.request import Request
# from time import time
# from lingvodoc.scheme import schema
#
# # def version_decorator(func):
# #     def inner(**kwargs):
# #         kwargs['route_name'] = 'v3/' + kwargs['route_name']
# #         return func(**kwargs)
# #     return inner
# #
# #
# # @version_decorator
# # def view_config(**kwargs):
# #     return pyramid_view_config(**kwargs)
# #
# #
# # # @view_config(route_name='v2/testing_decorator', renderer='json')
# # @view_config(route_name='testing_decorator', renderer='json')
# # def testing_decorator(request):
# #     return {'42': 'v3'}
# #
# #
# #
# # def testing_add_view(request):
# #     return {'answer': 'v3'}
#
# #
# # @view_config(route_name='v3/testing_scan', renderer='json')
# # def testing_scan(request):
# #     return {"version": 3}
#
#
#
#
# @view_config(route_name='v3/testing_graphene', renderer='json')
# def testing_graphene(request):
#     published = request.params.get('published')
#     if published is None:
#         published = False
#
#     # result = schema.execute('query  dictionary{ client dictionaries(published: %s){translation status} dictionary(id: [70,4]){id translation}}' % str(published).lower(),
#     #                         context_value={'client': get_user_by_client_id(authenticated_userid(request)).name,
#     #                                        'locale_id': 1,
#     #                                        'request': request})
#
#     # result = schema.execute(
#     #     'query  perspective{  perspective(id: [630])'
#     #     '{id translation tree{id translation dataType}'
#     #     'fields{id translation}'
#     #     'lexicalEntries{id entities{id content fieldType}}'
#     #     '}}',
#     #     context_value={'client': get_user_by_client_id(authenticated_userid(request)).name,
#     #                    'locale_id': 2,
#     #                    'request': request})
#
#
#     result = schema.execute(
#         'query  entity{  entity(id: [70, 773])'
#         '{ id content fieldType}}',
#         context_value={'client': get_user_by_client_id(authenticated_userid(request)).name,
#                        'locale_id': 2,
#                        'request': request})
#
#     # result = schema.execute(
#     #     'query  perspective{  perspective(id: [70,5])'
#     #     '{id translation '
#     #     'lexicalEntries{id entities{id content fieldType}}'
#     #     '}}',
#     #     context_value={'client': get_user_by_client_id(authenticated_userid(request)).name,
#     #                    'locale_id': 2,
#     #                    'request': request})
#
#     if result.invalid:
#         return {'errors': [str(e) for e in result.errors]}
#     return result.data
