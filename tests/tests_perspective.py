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

class PerspectiveTest(MyTestCase):

    def _build_ordered_lists(self, correct_answer, response):
        answer = sorted(correct_answer, key=lambda x: (x['client_id'], x['object_id']))
        response = response.json
        result = list()
        for i in response['perspectives']:
            self.assertIn('client_id', i)
            self.assertIn('object_id', i)
            result.append(dict(client_id = i['client_id'], object_id = i['object_id']))
        result = sorted(result, key=lambda x: (x['client_id'], x['object_id']))
        return (result, answer)

    def testAllPerspectives(self):
        id_tester = self.signup_common()
        id_u1 = self.signup_common('user1', 'user1')
        id_l1 = self.create_language('language1')
        dict_1 = self.create_dictionary('user1_dict1', id_l1)
        default_persp = [
            {"object_id": 1, "client_id": 1},
            {"object_id": 1, "client_id": 2},
            {"object_id": 1, "client_id": 3}
        ]
        response = self.app.get('/perspectives',
                                params = {'is_template': "true"})
        persp_1 = self.create_perspective('translation_string1', dict_1, "Published")


        # print(response)
        # self.assertEqual(response.status_int, HTTPOk.code)
        # result, answer = self._build_ordered_lists(default_persp, response)
        # self.assertFalse(result)
        #
        # response = self.app.get('/perspectives',
        #                               params = {'is_template': False})
        # self.assertEqual(response.status_int, HTTPOk.code)
        # result, answer = self._build_ordered_lists([], response)
        # print(result, answer)
