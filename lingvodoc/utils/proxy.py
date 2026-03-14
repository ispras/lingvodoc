__author__ = 'student'
import requests
import json
from distutils.util import strtobool
from pdb import set_trace as A


class ProxyPass(Exception):
    def __init__(self, request, sync_between=('isp', 'xal'), message=None):
        settings = request.registry.settings
        local = settings['proxy']['local']
        remote = sync_between[not sync_between.index(local)]  # 0'th or 1'st

        if remote_server := settings['proxy'].get(f'{remote}_server'):
            path = remote_server + 'api' + request.path
        else:
            raise NotImplementedError

        if message is None:
            message = f"It's not an error, just request was redirected to {remote_server=}"

        super().__init__(message)
        self.message = str(message)

        server_cookies = request.cookies.get('server_cookies')
        if server_cookies:
            cookies = json.loads(request.cookies.get('server_cookies'))
        else:
            cookies = None
        session = requests.Session()
        #session.headers.update(**request.headers)
        session.headers.update({'Connection': 'Keep-Alive'})
        session.headers.update({'Content-type': 'application/json'})
        if cookies:
            session.headers.update(
                {
                    "Cookie": "auth_tkt=%s; locale_id=%s; client_id=%s" % (cookies["auth_tkt"],
                                                                           cookies["locale_id"],
                                                                           cookies["client_id"])
                })
        adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
        session.mount('http://', adapter)
        # session.cookies.set(cookies)

        #session.cookies.clear()
        if cookies:
            session.cookies.set("auth_tkt", cookies["auth_tkt"])
            session.cookies.set("locale_id", str(cookies["locale_id"]))
            session.cookies.set("client_id", str(cookies["client_id"]))
        #session.cookies.set("server_cookies", request.cookies.get('server_cookies'))
        # for key in cookies:
        #     session.cookies.set(key, cookies[key])

        # Changing proxy flag to false
        json_data = {
            **request.json_body,
            'variables': {
                **(request.json_body.get('variables', {})),
                'cross_request': True
            }
        }

        status = session.post(path, json=json_data, headers=session.headers, cookies=cookies)
        #print(status.request)

        self.response_body = status.content
        self.response_json = status.json()


def try_proxy(*args):
    raise ProxyPass(*args)
