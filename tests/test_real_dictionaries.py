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


class ConvertTest(MyTestCase):

    def setUp(self):
        super().setUp()
        import webtest.http
        myapp = self.myapp
        self.ws = webtest.http.StopableWSGIServer.create(myapp, port=6543, host="0.0.0.0")

    def tearDown(self):
        self.ws.shutdown()
        super().tearDown()

    def test_dict_convert(self):
        import hashlib
        from time import sleep
        import webtest.http
        import threading
        server_started = self.ws.wait()
        self.assertEqual(server_started, True)
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

        print('==== LOOK HERE ====')
        print(response.json)
        not_found = True
        for i in range(3):
            response = self.app.post_json('/dictionaries', params={'user_created': [user_id]})
            if response.json['dictionaries']:
                not_found = False
                break
            sleep(10)
        if not_found:
            self.assertEqual('error', 'dictionary was not found')
        print(response.json['dictionaries'])
