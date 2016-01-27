import unittest
import transaction

from pyramid import testing
from lingvodoc.models import DBSession

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
from pyramid.paster import (
    get_appsettings,
    setup_logging,
    )

from subprocess import PIPE, Popen
inifile = 'andrey.ini'
alembicini = 'alembictests.ini'
dbname = 'postgresql+psycopg2://postgres@/lingvodoc_testing'  # TODO: read from alembicini

from lingvodoc.scripts.initializedb import data_init

print_deb = False

def new_dict(d, key_set):
    new_d = dict()
    for key in d:
        el = d[key]
        empty_lst = [None, {}, [], ()]
        empty_lst += [str(o) for o in empty_lst]
        if el not in empty_lst:
            new_d[key] = el
            key_set.add(key)
    return new_d


def is_equal(el1, el2):
    t1, t2 = type(el1), type(el2)
    # print('elems', el1, el2)
    if t1 != t2:
        # print('type false')
        return False
    if t1 == dict:
        if not dict_diff(el1,el2):
            # print('dict false')
            return False
    elif t1 == list:
        if not list_diff(el1,el2):
                return False
    elif el1 != el2:
        # print('simple false')
        return False
    return True


def list_diff(l1, l2):
    for i in range(len(l1)):
        if not is_equal(l1[i], l2[i]):
            # print('list false')
            return False
    return True


def dict_diff(d1,d2):
    keyset = set()
    nd1 = new_dict(d1, keyset)
    nd2 = new_dict(d2, keyset)
    # print(nd1, nd2)
    # print(keyset)
    for key in keyset:
        el1, el2 = nd1.get(key), nd2.get(key)
        # print('key', key)
        if not is_equal(el1, el2):
            # print('elems in dict false')
            return False
    return True


def commonSetUp(self):
    import os
    self.config = testing.setUp()
    import webtest
    from pyramid import paster
    from sqlalchemy import create_engine
    engine = create_engine(dbname)
    myapp = paster.get_app(inifile)
    self.app = webtest.TestApp(myapp)
    DBSession.remove()
    DBSession.configure(bind=engine)
    bashcommand = "alembic -c %s upgrade head" % alembicini
    args = bashcommand.split()
    pathdir = os.path.dirname(os.path.realpath(__file__))
    pathdir = pathdir[:(len(pathdir) - 6)]
    my_env = os.environ
    proc = Popen(args, cwd=pathdir, env=my_env)
    proc.communicate()
    accounts = get_appsettings(inifile, 'accounts')
    data_init(transaction.manager, accounts)


def commonTearDown(self):
    import os
    DBSession.remove()
    bashcommand = "alembic -c %s downgrade base" % alembicini
    args = bashcommand.split()
    pathdir = os.path.dirname(os.path.realpath(__file__))
    pathdir = pathdir[:(len(pathdir) - 6)]
    my_env = os.environ
    proc = Popen(args, cwd=pathdir, env=my_env)
    proc.communicate()
    testing.tearDown()


class MyTestCase(unittest.TestCase):

    def setUp(self):
        commonSetUp(self)

    def tearDown(self):
        commonTearDown(self)

    def assertDictEqual(self, d1, d2, msg=None):
        self.assertEqual(dict_diff(d1, d2), True, msg)

    def assertListEqual(self, l1, l2, msg=None):
        self.assertEqual(list_diff(l1, l2), True, msg)

def login_common(self):
    response = self.app.post('/signup', params={'login': 'test',
                                                     'password': 'pass',
                                                     'name': 'test',
                                                     'email': 'test@test.com',
                                                     'day': '1',
                                                     'month': '1',
                                                     'year': '1970'})
    self.assertEqual(response.status_int, HTTPFound.code)
    response = self.app.post('/login', params={'login': 'test',
                                               'password': 'pass'})
    self.assertEqual(response.status_int, HTTPFound.code)


def create_language(self, translation_string):
        response = self.app.post_json('/language', params={'translation_string': translation_string})
        self.assertEqual(response.status_int, HTTPOk.code)
        ids = response.json
        response = self.app.get('/language/%s/%s' % (ids['client_id'], ids['object_id']))
        correct_answer = {'client_id': ids['client_id'], 'object_id': ids['object_id'],
                          'locale_exist': False, 'translation': translation_string,
                          'parent_client_id': None, 'translation_string': translation_string, 'parent_object_id': None}
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertDictEqual(response.json, correct_answer)
        return ids


def create_dictionary(self, translation_string, par_ids):
        response = self.app.post_json('/dictionary', params={'translation_string': translation_string,
                                                           'parent_client_id': par_ids['client_id'],
                                                           'parent_object_id': par_ids['object_id']})
        self.assertEqual(response.status_int, HTTPOk.code)
        ids = response.json
        response = self.app.get('/dictionary/%s/%s' % (ids['client_id'], ids['object_id']))
        correct_answer = {'client_id': ids['client_id'], 'object_id': ids['object_id'],
                          'additional_metadata': None,
                          'parent_client_id':  par_ids['client_id'],
                          'parent_object_id':  par_ids['object_id'],
                          'translation': translation_string,
                          'translation_string': translation_string,
                          'status': 'WiP'}

        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertDictEqual(response.json, correct_answer)
        return ids


def create_perspective(self, translation_string, par_ids):
        response = self.app.post_json('/dictionary/%s/%s/perspective' % (par_ids['client_id'],par_ids['object_id']),
                                      params={'translation_string': translation_string})
        self.assertEqual(response.status_int, HTTPOk.code)
        ids = response.json
        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s' % (par_ids['client_id'],par_ids['object_id'],
                                                                         ids['client_id'], ids['object_id']))
        correct_answer = {'client_id': ids['client_id'], 'object_id': ids['object_id'],
                          'additional_metadata': None,
                          'parent_client_id':  par_ids['client_id'],
                          'parent_object_id':  par_ids['object_id'],
                          'translation': translation_string,
                          'translation_string': translation_string,
                          'is_template': False,
                          'marked_for_deletion': False,
                          'status': 'WiP'}
        first_view = response.json
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertDictEqual(first_view, correct_answer)
        response = self.app.get('/perspective/%s/%s' % (ids['client_id'], ids['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertDictEqual(response.json, correct_answer)
        return ids


class TestSignUp(MyTestCase):

    def one_big_test(self):
        # test impossibility to create language without login
        response = self.app.post_json('/language', params={'translation_string': 'test'},
                                     status=HTTPForbidden.code)
        self.assertEqual(response.status_int, HTTPForbidden.code)
        # test signup & login
        login_common(self)
        # test creating language
        lang_name = 'test_lang'
        par_ids = create_language(self, lang_name)
        # test view all languages

        response = self.app.get('/languages')

        self.assertEqual(response.status_int, HTTPOk.code)
        correct_answer = {'languages':
                              [{'translation': 'Russian language',
                                'client_id': 1, 'translation_string': 'Russian language',
                                'object_id': 1, 'locale_exist': True},
                               {'translation': 'English language', 'client_id': 1,
                                'translation_string': 'English language',
                                'object_id': 2, 'locale_exist': True},
                               {'translation': 'Finnish language', 'client_id': 1,
                                'translation_string': 'Finnish language', 'object_id': 3,
                                'locale_exist': True},
                               {'translation': 'French language', 'client_id': 1,
                                'translation_string': 'French language', 'object_id': 4,
                                'locale_exist': True},
                               {'translation': 'German language', 'client_id': 1,
                                'translation_string': 'German language',
                                'object_id': 5, 'locale_exist': True},
                               {'translation': lang_name, 'client_id': 3,
                                'translation_string': lang_name,
                                'object_id': 1, 'locale_exist': False}]}
        self.assertDictEqual(response.json, correct_answer)

        # test all params when editing language
        response = self.app.put_json('/language/%s/%s' % (par_ids['client_id'], par_ids['object_id']),
                                     params={'translation':'new_translation',
                                             'parent_client_id':1,
                                             'parent_object_id':1})
        self.assertEqual(response.status_int, HTTPOk.code)
        response = self.app.get('/language/%s/%s' % (par_ids['client_id'], par_ids['object_id']))
        correct_answer = {'client_id': par_ids['client_id'], 'object_id': par_ids['object_id'],
                          'locale_exist': False, 'translation': 'new_translation',
                          'parent_client_id': 1, 'translation_string': lang_name, 'parent_object_id': 1}
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertDictEqual(response.json, correct_answer)
        # test all params when creating language
        response = self.app.post_json('/language', params={'translation_string': 'test_child',
                                                           'parent_client_id': par_ids['client_id'],
                                                           'parent_object_id': par_ids['object_id']})
        self.assertEqual(response.status_int, HTTPOk.code)
        ids2 = response.json
        response = self.app.get('/language/%s/%s' % (ids2['client_id'], ids2['object_id']))
        correct_answer = {'client_id': ids2['client_id'], 'object_id': ids2['object_id'],
                          'locale_exist': False, 'translation': 'test_child',
                          'parent_client_id': par_ids['client_id'],
                          'translation_string': 'test_child',
                          'parent_object_id': par_ids['object_id']}
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertDictEqual(response.json, correct_answer)
        # test creating dictionary

        dict_name = 'test_dict'
        dict_ids = create_dictionary(self, dict_name, par_ids)
        # test edit dictionary
        response = self.app.put_json('/dictionary/%s/%s' % (dict_ids['client_id'], dict_ids['object_id']),
                                     params={'translation':'new_translation',
                                             'parent_client_id':1,
                                             'parent_object_id':1})
        self.assertEqual(response.status_int, HTTPOk.code)
        response = self.app.get('/dictionary/%s/%s' % (dict_ids['client_id'], dict_ids['object_id']))
        correct_answer = {'client_id': dict_ids['client_id'], 'object_id': dict_ids['object_id'],
                          'additional_metadata': '[]',
                          'translation': 'new_translation',
                          'parent_client_id': 1, 'translation_string': dict_name, 'parent_object_id': 1,
                          'status': 'WiP'}
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertDictEqual(response.json, correct_answer)


        response = self.app.put_json('/dictionary/%s/%s' % (dict_ids['client_id'], dict_ids['object_id']),
                                     params={'translation':'new_translation',
                                             'parent_client_id':par_ids['client_id'],
                                             'parent_object_id':par_ids['object_id']})
        self.assertEqual(response.status_int, HTTPOk.code)
        response = self.app.get('/dictionary/%s/%s' % (dict_ids['client_id'], dict_ids['object_id']))
        correct_answer = {'client_id': dict_ids['client_id'], 'object_id': dict_ids['object_id'],
                          'additional_metadata': '[]',
                          'translation': 'new_translation',
                          'parent_client_id': par_ids['client_id'], 'translation_string': dict_name,
                          'parent_object_id': par_ids['object_id'],
                          'status': 'WiP'}
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertDictEqual(response.json, correct_answer)

        # test view dictionary state
        response = self.app.get('/dictionary/%s/%s/state' % (dict_ids['client_id'], dict_ids['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertDictEqual(response.json, {'status': 'WiP'})
        # test edit dictionary state
        response = self.app.put_json('/dictionary/%s/%s/state' % (dict_ids['client_id'], dict_ids['object_id']),
                                     params={'status':'test state'})
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertDictEqual(response.json, {'status': 'test state'})

        persp_name = 'test_persp'
        # test creating perspective
        persp_ids = create_perspective(self, persp_name, dict_ids)
        # test perspective edit
        response = self.app.put_json('/dictionary/%s/%s/perspective/%s/%s' % (dict_ids['client_id'],dict_ids['object_id'],
                                                                         persp_ids['client_id'], persp_ids['object_id']),
                                     params={'translation':'new_translation',
                                             'parent_client_id':1,
                                             'parent_object_id':1,
                                             'is_template': True})
        self.assertEqual(response.status_int, HTTPOk.code)
        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s' % (dict_ids['client_id'], dict_ids['object_id'],
                                                                         persp_ids['client_id'], persp_ids['object_id']))
        correct_answer = {'client_id': persp_ids['client_id'], 'object_id': persp_ids['object_id'],
                          'additional__metadata': '[]',
                          'translation': 'new_translation',
                          'parent_client_id': 1, 'translation_string': persp_name,
                          'parent_object_id': 1,
                          'is_template': True,
                          'marked_for_deletion': False,
                          'status': 'WiP'}
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertDictEqual(response.json, correct_answer)
        # return old parent to perspective
        response = self.app.put_json('/dictionary/%s/%s/perspective/%s/%s' % (1,1,
                                                                         persp_ids['client_id'], persp_ids['object_id']),
                                     params={'parent_client_id': dict_ids['client_id'],
                                             'parent_object_id': dict_ids['object_id'],
                                             'is_template': True})
        self.assertEqual(response.status_int, HTTPOk.code)
        # test view perspective state
        response = self.app.get('/dictionary/%s/%s'
                     '/perspective/%s/%s/state' % (dict_ids['client_id'],dict_ids['object_id'],
                                                                         persp_ids['client_id'], persp_ids['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertDictEqual(response.json, {'status': 'WiP'})
        # test edit perspective state
        response = self.app.put_json('/dictionary/%s/%s/perspective/%s/%s/state'
                                     % (dict_ids['client_id'],dict_ids['object_id'],
                                        persp_ids['client_id'], persp_ids['object_id']),
                                     params={'status':'test state'})

        self.assertEqual(response.status_int, HTTPOk.code)

        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s/state' % (dict_ids['client_id'],dict_ids['object_id'],
                                                                         persp_ids['client_id'], persp_ids['object_id']))

        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertDictEqual(response.json, {'status': 'test state'})

        # test view perspective tree
        response = self.app.get('/dictionary/%s/%s'
                     '/perspective/%s/%s/tree' % (dict_ids['client_id'],dict_ids['object_id'],
                                                                         persp_ids['client_id'], persp_ids['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        # correct_answer = [
        #     {'translation': persp_name, 'client_id':  persp_ids['client_id'],
        #      'type': 'perspective', 'object_id':  persp_ids['object_id'],
        #      'is_template': True, 'status': 'test state',
        #      'translation_string': 'new_translation',
        #      'parent_client_id': dict_ids['client_id'], 'parent_object_id': dict_ids['object_id'],
        #      'marked_for_deletion': False},
        #     {'client_id': dict_ids['client_id'], 'translation': 'new_translation',
        #      'type': 'dictionary', 'object_id': dict_ids['object_id'], 'status': 'test state',
        #      'translation_string': dict_name, 'additional_metadata': None,
        #      'parent_client_id': par_ids['client_id'], 'parent_object_id': par_ids['object_id']},
        #     {'client_id': par_ids['client_id'], 'translation': 'new_translation', 'locale_exist': False,
        #      'object_id': par_ids['object_id'], 'type': 'language', 'translation_string': lang_name,
        #      'parent_client_id': 1, 'parent_object_id': 1},
        #     {'parent_object_id': None, 'parent_client_id': None,
        #      'object_id': 1, 'translation_string': 'Russian language',
        #      'client_id': 1, 'locale_exist': True, 'translation': 'Russian language', 'type': 'language'}] #TODO: check diff

        correct_answer = [{'parent_object_id': dict_ids['object_id'], 'parent_client_id': dict_ids['client_id'],
                           'object_id': persp_ids['object_id'], 'client_id': persp_ids['client_id'],
                           'translation_string': persp_name,
                           'is_template': True, 'status': 'test state',
                           'marked_for_deletion': False,
                           'translation': 'new_translation', 'type': 'perspective'},
                          {'additional_metadata': None, 'parent_object_id': par_ids['object_id'],
                           'parent_client_id': par_ids['client_id'], 'client_id': dict_ids['client_id'],
                           'translation_string': dict_name,
                           'object_id': dict_ids['object_id'], 'status': 'test state',
                           'translation': 'new_translation', 'type': 'dictionary'},
                          {'parent_object_id': 1, 'parent_client_id': 1,
                           'locale_exist': False, 'translation_string': lang_name,
                           'object_id': par_ids['object_id'], 'client_id': par_ids['client_id'],
                           'translation': 'new_translation', 'type': 'language'},
                          {'parent_object_id': None, 'parent_client_id': None,
                           'locale_exist': True, 'translation_string': 'Russian language',
                           'object_id': 1, 'client_id': 1, 'translation': 'Russian language',
                           'type': 'language'}]
        first_answ = response.json
        self.assertListEqual(first_answ, correct_answer)
        response = self.app.get('/perspective/%s/%s/tree' % (persp_ids['client_id'], persp_ids['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertListEqual(first_answ, response.json)

        # testing perspective meta
        metadict = {'a':'b', 'c':{'d':'e'}}
        response = self.app.put_json('/dictionary/%s/%s/perspective/%s/%s/meta'
                                     % (dict_ids['client_id'],dict_ids['object_id'],
                                        persp_ids['client_id'], persp_ids['object_id']),
                                     params = metadict)
        self.assertEqual(response.status_int, HTTPOk.code)
        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s/meta'
                                     % (dict_ids['client_id'],dict_ids['object_id'],
                                        persp_ids['client_id'], persp_ids['object_id']),
                                    )
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertDictEqual(response.json, metadict)
        metaupd = {'a':{'f':'g'}, 'h':'i', 'j':['k','l', {'m':'n', 'o':'p'}]}
        response = self.app.put_json('/dictionary/%s/%s/perspective/%s/%s/meta'
                                     % (dict_ids['client_id'],dict_ids['object_id'],
                                        persp_ids['client_id'], persp_ids['object_id']),
                                     params = metaupd)
        self.assertEqual(response.status_int, HTTPOk.code)
        metadict.update(metaupd)
        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s/meta'
                                     % (dict_ids['client_id'],dict_ids['object_id'],
                                        persp_ids['client_id'], persp_ids['object_id']),
                                    )
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertDictEqual(response.json, metadict)
        metadel = ['j', 'c']
        response = self.app.delete_json('/dictionary/%s/%s/perspective/%s/%s/meta'
                                     % (dict_ids['client_id'],dict_ids['object_id'],
                                        persp_ids['client_id'], persp_ids['object_id']),
                                        params = metadel
                                    )
        self.assertEqual(response.status_int, HTTPOk.code)
        for key in metadel:
            del metadict[key]
        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s/meta'
                                     % (dict_ids['client_id'],dict_ids['object_id'],
                                        persp_ids['client_id'], persp_ids['object_id']),
                                    )
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertDictEqual(response.json, metadict)


    #     _________________________________________________________________________
    #     _________________________________________________________________________
    #     Tests on deleting part
    #     _________________________________________________________________________

        lang_ids = create_language(self, 'test_lang_del')
        dict_ids = create_dictionary(self, 'test_dict_del', lang_ids)
        persp_ids = create_perspective(self, 'test_persp_del', dict_ids)

        response = self.app.delete('/dictionary/%s/%s/perspective/%s/%s' %
                                   (dict_ids['client_id'], dict_ids['object_id'],
                                    persp_ids['client_id'], persp_ids['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s' %
                                   (dict_ids['client_id'], dict_ids['object_id'],
                                    persp_ids['client_id'], persp_ids['object_id']),
                                status=HTTPNotFound.code)
        self.assertEqual(response.status_int, HTTPNotFound.code)

        response = self.app.delete('/dictionary/%s/%s' % (dict_ids['client_id'], dict_ids['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        response = self.app.get('/dictionary/%s/%s' % (dict_ids['client_id'], dict_ids['object_id']),
                                status=HTTPNotFound.code)
        self.assertEqual(response.status_int, HTTPNotFound.code)

        response = self.app.delete('/language/%s/%s' % (lang_ids['client_id'], lang_ids['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        response = self.app.get('/language/%s/%s' % (lang_ids['client_id'], lang_ids['object_id']),
                                status=HTTPNotFound.code)
        self.assertEqual(response.status_int, HTTPNotFound.code)

    #     _________________________________________________________________________
        # test logout (TODO: add tests on protections here)
        create_language(self, 'test_logout')
        response = self.app.post('/logout')

        self.assertEqual(response.status_int, HTTPFound.code)
        response = self.app.post_json('/language', params={'translation_string': 'test_logout'},
                                     status=HTTPForbidden.code)
        self.assertEqual(response.status_int, HTTPForbidden.code)

class TestFuncs(unittest.TestCase):

    def test_dict_diff_empty(self):
        d1 = {}
        d2 = {}
        self.assertEqual(dict_diff(d1, d2), True)

    def test_dict_diff_not_eq(self):
        d1 = {'a':'b'}
        d2 = {'b':'a'}
        self.assertNotEqual(dict_diff(d1, d2), True)

    def test_dict_diff_with_dicts_help(self):
        d1 =  {'b':'c','d':'e'}
        d2 = {'d':'e','b':'c'}
        self.assertEqual(dict_diff(d1, d2), True)

    def test_dict_diff_with_dicts(self):
        d1 = {'a': {'b':'c','d':'e'}}
        d2 = {'a':  {'d':'e','b':'c'}}
        self.assertEqual(dict_diff(d1, d2), True)

    def test_dict_diff_with_lists(self):
        d1 = {'a': {'b':'c','d':'e'}, 'f':['g', {'i':'j', 'k':'l', 'm':'n', 'o':'p'}, 'q']}
        d2 = {'a':  {'d':'e','b':'c'}, 'f':['g', {'i':'j', 'o':'p', 'k':'l', 'm':'n'}, 'q']}
        self.assertEqual(dict_diff(d1, d2), True)

    def test_dict_diff_with_lists_not_eq(self):
        d1 = {'a': {'b':'c','d':'e'}, 'f':['q', {'i':'j', 'k':'l', 'm':'n', 'o':'p'}, 'g']}
        d2 = {'a':  {'d':'e','b':'c'}, 'f':['g', {'i':'j', 'o':'p', 'k':'l', 'm':'n'}, 'q']}
        self.assertNotEqual(dict_diff(d1, d2), True)

    def test_dict_diff_not_eq_2(self):
        d1 = {'is_template': True, 'client_id': 3, 'parent_object_id': 1, 'object_id': 1, 'status': 'WiP', 'translation': 'new_translation', 'translation_string': 'test_persp', 'additional_metadata': '{}', 'marked_for_deletion': False, 'parent_client_id': 1}
        d2 = {'client_id': 3, 'object_id': 1,
                          'locale_exist': False, 'translation': 'new_translation',
                          'parent_client_id': 1,
                          'translation_string': 'test_child',
                          'parent_object_id': 1}
        self.assertNotEqual(dict_diff(d1, d2), True)
