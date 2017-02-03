from pyramid.request import Request
from pyramid.security import (
    authenticated_userid,
)
from pyramid.view import view_config


# @view_config(route_name='perspective_stats', renderer='json', request_method='GET')
# def perspective_stats(request):
