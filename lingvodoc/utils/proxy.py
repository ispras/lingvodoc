__author__ = 'student'
import requests
import json

class ProxyPass(Exception):
    def __init__(self, message, request):
        super().__init__(message)
        self.message = str(message)
        settings = request.registry.settings
        path = settings['desktop']['central_server'] + request.path[1:]
        server_cookies = request.cookies.get('server_cookies')
        if server_cookies:
            cookies = json.loads(request.cookies.get('server_cookies'))
        else:
            cookies = None
        session = requests.Session()
        session.headers.update({'Connection': 'Keep-Alive'})
        adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
        session.mount('http://', adapter)
        status = session.post(path, data=request.body, cookies=cookies, headers=request.headers)
        self.response_body = status.content


def try_proxy(request):
    settings = request.registry.settings
    if settings.get('desktop'):
        raise ProxyPass(message="", request=request)