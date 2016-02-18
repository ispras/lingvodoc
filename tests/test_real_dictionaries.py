from tests.tests import MyTestCase

from pyramid.httpexceptions import (
    HTTPNotFound,
    HTTPOk,
    HTTPBadRequest,
    HTTPConflict,
    HTTPInternalServerError,
    HTTPUnauthorized,
    HTTPFound,
    HTTPForbidden
)

import threading
from tests.tests import alembicini
from pyramid import paster
from waitress import serve
import json

def pserve():
    myapp = paster.get_app('../' + alembicini)


    def my_serve():
        serve(myapp, host='0.0.0.0', port=6543)


    a = threading.Thread(target=my_serve)
    a.daemon = True
    print('starting server')
    a.run()

    print('server started')


class ConvertTest(MyTestCase):

    def test_dict_convert(self):
        import hashlib
        from time import sleep
        # from werkzeug.utils import secure_filename
        import webtest.http
        import threading
        # self.ws.run()
        # t = threading.Thread(target=self.ws.run)
        # t.daemon = True
        # t.start()
        user_id = self.signup_common()
        self.login_common()
        root_ids = self.create_language('Корень')
        first_hash = hashlib.md5(open("test.sqlite", 'rb').read()).hexdigest()
        response = self.app.post('/blob', params = {'data_type':'dialeqt_dictionary'},
                                 upload_files=([('blob', 'test.sqlite')]))
        self.assertEqual(response.status_int, HTTPOk.code)
        blob_ids = response.json
        response = self.app.get('/blobs/%s/%s' % (blob_ids['client_id'],
                                                          blob_ids['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        file_response = self.app.get(response.json['content'])
        second_hash = hashlib.md5(file_response.body).hexdigest()
        self.assertEqual(first_hash, second_hash)
        response = self.app.post_json('/convert_check', params={'blob_client_id': blob_ids['client_id'],
                                                         'blob_object_id': blob_ids['object_id']})
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, [])
        response = self.app.post_json('/convert', params={'blob_client_id': blob_ids['client_id'],
                                                         'blob_object_id': blob_ids['object_id'],
                                                          'parent_client_id':root_ids['client_id'],
                                                          'parent_object_id':root_ids['object_id']})
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertDictEqual(response.json, {"status": "Your dictionary is being converted."
                      " Wait 5-15 minutes and you will see new dictionary in your dashboard."})
        not_found = True
        for i in range(3):
            response = self.app.post_json('/dictionaries', params={'user_created': [user_id]})
            if response.json['dictionaries']:
                not_found = False
                break
            sleep(10)
        if not_found:
            self.assertEqual('error', 'dictionary was not found')
        dict_ids = response.json['dictionaries'][0]
        for i in range(20):
            response = self.app.get('/dictionary/%s/%s/state' % (dict_ids['client_id'], dict_ids['object_id']))
            if response.json['status'].lower() == 'published':
                break
            sleep(60)
        response = self.app.get('/dictionary/%s/%s/perspectives' % (dict_ids['client_id'], dict_ids['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        persp_ids = response.json['perspectives'][0]
        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s/all'
                                % (dict_ids['client_id'],
                                   dict_ids['object_id'],
                                   persp_ids['client_id'],
                                   persp_ids['object_id']))
        # json_file = open('test_dict_convert.json', 'w')
        # json_file.write(json.dumps(response.json))
        # json_file.close()
        json_file = open('test_dict_convert.json', 'r')
        correct_answer = json.loads(json_file.read())
        self.assertDictEqual(response.json, correct_answer, stop_words=['client_id',
                                                                        'object_id',
                                                                        'parent_client_id',
                                                                        'parent_object_id'], set_like= True)
