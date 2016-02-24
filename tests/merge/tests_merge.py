from tests.tests import MyTestCase
from tests.common import initValuesFactory
from tests.common import load_correct_answers

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

class MergeTest(MyTestCase):

    def _create_sample_dict(self, language):
        dict = self.create_dictionary('user1_dict1', language)
        persp_1 = self.create_perspective('translation_string1', dict, "Published", False)
        persp_2 = self.create_perspective('translation_string2', dict, "Published", False)
        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s/fields'
                                % (1, 1, 1, 1))
        fields = response.json

        words_1 = ["uyzrljiirs", "kxmzpclrns"]
        translation_1 = ["kgrrdjafqz", "jdavwdmuqe"]
        transcription_1 = ["zlswwsfjrc", "bkrmwpshnh"]
        words_2 = ["cpnltteyzj", "iyornljisb"]
        translation_2 = ["ozidqyatiz", "hxjzmtthxp"]
        transcription_2 = ["jlsodufkah", "wiymxkmzhs"]
        content = ({ "content": list(zip(words_1, transcription_1, translation_1)), "persp": persp_1},
                   { "content": list(zip(words_2, transcription_2, translation_2)), "persp": persp_2})
        for c in content:
            response = self.app.post_json('/dictionary/%s/%s/perspective/%s/%s/fields'
                                      % (dict['client_id'], dict['object_id'],
                                         c['persp']['client_id'], c['persp']['object_id']),
                                      params=fields)
            response = self.app.post_json('/dictionary/%s/%s/perspective/%s/%s/lexical_entries' %
                                      (dict['client_id'], dict['object_id'],
                                       c['persp']['client_id'], c['persp']['object_id']),
                                      params={'count': len(c['content'][0])})
            lex_entries = list(zip(response.json, c['content']))
            for lex, val in lex_entries:
                self.add_l1e(dict, c['persp'], lex, val[0], 'Word')
                self.add_l1e(dict, c['persp'], lex, val[1], 'Translation')
                self.add_l1e(dict, c['persp'], lex, val[2], 'Transcription')
        # response = self.app.get('/dictionary/%s/%s/perspective/%s/%s/all' %
        #                               (dict['client_id'], dict['object_id'],
        #                                persp_1['client_id'], persp_1['object_id']))
        # print(response)
        # print("aaa")
        # response = self.app.get('/dictionary/%s/%s/perspective/%s/%s/all' %
        #                               (dict['client_id'], dict['object_id'],
        #                                persp_2['client_id'], persp_2['object_id']))
        # print(response)
        return dict, persp_1, persp_2

    def setUp(self):
        super(MergeTest, self).setUp()
        self.id_tester = self.signup_common()
        self.id_l1 = self.create_language('language1')
        self.dict_unit_1 = self._create_sample_dict(self.id_l1)
        self.dict_unit_2 = self._create_sample_dict(self.id_l1)
        print("aaa")

    def testTest(self):
        print(0)
        # import pdb
        # pdb.set_trace()
        dict_id, persp_id = self.dict_convert("/home/alexander/sources/lingvodoc/tests/databases/merge_2.sqlite", self.id_tester)
        print(111)
