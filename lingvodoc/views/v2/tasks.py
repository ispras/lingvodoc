from lingvodoc.cache.caching import TaskStatus
from lingvodoc.models import Client
from pyramid.response import Response
from pyramid.security import authenticated_userid
from pyramid.view import view_config
from hashlib import sha224
import logging
log = logging.getLogger(__name__)


@view_config(route_name='tasks', renderer='json', request_method='GET')
def get_tasks(request):
    client_id = authenticated_userid(request)
    if not client_id:
        ip = request.client_addr
        useragent = request.headers["User-Agent"]
        unique_string = "unauthenticated_%s_%s" % (ip, useragent)
        user_id = sha224(unique_string.encode('utf-8')).hexdigest()
        tasks = TaskStatus.get_user_tasks(user_id, clear_out=True)
        return tasks
    # if not client_id:
    #     return []
    user = Client.get_user_by_client_id(authenticated_userid(request))
    tasks = TaskStatus.get_user_tasks(user.id, clear_out=True)
    return tasks


@view_config(route_name='delete_task', renderer='json', request_method='DELETE')
def delete_task(request):
    #client_id = authenticated_userid(request)
    # if not client_id:
    #     return {}
    task_id = request.matchdict.get('task_id')
    task_key = "task:" + task_id
    task = TaskStatus.get_from_cache(task_key)
    if task:
        task.delete()
    return {}
