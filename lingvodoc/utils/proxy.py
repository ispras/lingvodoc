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
        status = session.post(path, data=request.body, headers=session.headers, cookies=cookies)
        #print(status.request)

        self.response_body = status.content


def try_proxy(request):
    settings = request.registry.settings
    if settings.get('desktop'):
        raise ProxyPass(message="", request=request)