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
    def _build_ordered_lists(self, response, correct_answer):
        self.assertEqual(response.status_int, HTTPOk.code)
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
            {"object_id": 2, "client_id": 1},
            {"object_id": 3, "client_id": 1}
        ]

        response = self.app.get('/perspectives',
                                params = {'is_template': False})
        result, answer = self._build_ordered_lists(response, [])
        self.assertFalse(result)

        persp_1 = self.create_perspective('translation_string1', dict_1, "Published", False)
        persp_2 = self.create_perspective('translation_string2', dict_1, "Published", True)
        persp_3 = self.create_perspective('translation_string3', dict_1, "Marked", False)
        persp_4 = self.create_perspective('translation_string4', dict_1, "Marked", True)

        response = self.app.get('/perspectives',
                                params = {'is_template': True})
        result, answer = self._build_ordered_lists(response, default_persp + [persp_2, persp_4])
        self.assertEqual(result, answer)

        response = self.app.get('/perspectives',
                                params = {'is_template': False})
        result, answer = self._build_ordered_lists(response, [persp_1, persp_3])
        self.assertEqual(result, answer)

        response = self.app.get('/perspectives',
                                params = {'state': "Published"})
        result, answer = self._build_ordered_lists(response, [persp_1, persp_2])
        self.assertEqual(result, answer)

        response = self.app.get('/perspectives',
                                params = {'state': "Marked", 'is_template': False})
        result, answer = self._build_ordered_lists(response, [persp_3])
        self.assertEqual(result, answer)

        response = self.app.get('/perspectives',
                                params = {'state': "NoState"})
        result, answer = self._build_ordered_lists(response, [])
        self.assertFalse(result)

        response = self.app.get('/perspectives')
        result, answer = self._build_ordered_lists(
            response, default_persp + [persp_1, persp_2, persp_3, persp_4])
        self.assertEqual(result, answer)

    def testPerspectives(self):
        id_tester = self.signup_common()
        id_u1 = self.signup_common('user1', 'user1')
        id_l1 = self.create_language('language1')
        dict_1 = self.create_dictionary('user1_dict1', id_l1)
        dict_2 = self.create_dictionary('user1_dict2', id_l1)
        unexisting_dict = {"object_id": 4, "client_id": 4}
        persp_1 = self.create_perspective('translation_string1', dict_1, "Published", False)
        persp_2 = self.create_perspective('translation_string1', dict_1, "Marked", True)

        response = self.app.get('/dictionary/%(client_id)s/%(object_id)s/perspectives' % dict_1)
        result, answer = self._build_ordered_lists(response, [persp_1, persp_2])
        self.assertEqual(result, answer)

        response = self.app.get('/dictionary/%(client_id)s/%(object_id)s/perspectives' % dict_2)
        result, answer = self._build_ordered_lists(response, [])
        self.assertFalse(result)

        #TODO: catch bad response exception and check it
        # try:
        #     response = self.app.get('/dictionary/%(client_id)s/%(object_id)s/perspectives' % unexisting_dict)
        # except AppError as app_error:
        #
        # self.assertEqual(response.status_int, HTTPNotFound.code)

