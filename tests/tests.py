import unittest
import transaction

from pyramid import testing

from lingvodoc.models import DBSession
from pyramid.httpexceptions import HTTPNotFound, HTTPOk, HTTPBadRequest, HTTPConflict, HTTPInternalServerError


class TestDictionariesListSuccessCondition(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        from lingvodoc.models import (
            Base,
            Dictionary
            )
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        with transaction.manager:
            new_dict=Dictionary(client_id=1, object_id=1, name='test')
            DBSession.add(new_dict)
            new_dict=Dictionary(client_id=1, object_id=2, name='test2')
            DBSession.add(new_dict)

    def tearDown(self):
        from lingvodoc.models import (
            Base,
            Dictionary
            )
        from sqlalchemy import create_engine
        DBSession.remove()
        testing.tearDown()

    def test_passing_view(self):
        from lingvodoc.views import dictionaries_list
        request = testing.DummyRequest()
        request.json_body={}
        response = dictionaries_list(request)

        self.assertEqual(response['status'], HTTPOk.code)
        self.assertEqual(response['dictionaries'], [{'object_id': 1, 'client_id': 1}, {'object_id':2,'client_id':1}])


class TestViewPerspectiveFieldsSuccessCondition(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        import webtest
        from pyramid import paster
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        myapp = paster.get_app('testing.ini')
        self.app = webtest.TestApp(myapp)
        from lingvodoc.models import (
            Base,
            DictionaryPerspectiveField,
            DictionaryPerspective,
            Dictionary,
            User,
            Locale,
            Passhash,
            Client,
            UserEntitiesTranslationString
            )
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        with transaction.manager:
            ru_locale = Locale(id=1, shortcut="ru", intl_name="Русский")
            DBSession.add(ru_locale)
            en_locale = Locale(id=2, shortcut="en", intl_name="English")
            DBSession.add(en_locale)
            DBSession.flush()
            new_user = User(id=1, login='test', default_locale_id = 1)
            new_pass = Passhash(password='pass')
            DBSession.add(new_pass)
            new_user.password = new_pass
            DBSession.add(new_user)
            new_client = Client(id=1, user=new_user)
            DBSession.add(new_client)
            DBSession.flush()
            persp = DictionaryPerspective(client_id=1, object_id=1, name='test',
                                             parent_client_id=1, parent_object_id=1)
            DBSession.add(persp)
            new_dict = Dictionary(client_id=1, object_id=1, name='test', state='WiP')
            DBSession.add(new_dict)
            field=DictionaryPerspectiveField(parent = persp, client_id=1,object_id=1,entity_type='protoform',data_type='text', level = 'L1E', state = 'enabled')
            DBSession.add(field)
            field1=DictionaryPerspectiveField(parent = persp, client_id=1, object_id=2,entity_type='sound', data_type='sound', level = 'L1E', state = 'enabled')
            field2=DictionaryPerspectiveField(parent_entity= field1, parent = persp, client_id=1, object_id=3, entity_type='praat', level = 'L2E', data_type='markup', state = 'enabled' )
            DBSession.add(field1)
            DBSession.add(field2)
            fieldgroup=DictionaryPerspectiveField(parent = persp, client_id=1,object_id=4,entity_type='protoform',data_type='text', level = 'L1E', group='testgroup', state = 'enabled')
            DBSession.add(fieldgroup)
            grouping = DictionaryPerspectiveField(parent = persp, client_id=1,object_id=5,entity_type='etymology',data_type='grouping_tag', level = 'GE', state = 'enabled')
            DBSession.add(grouping)
            new_uets = UserEntitiesTranslationString(object_id=1, client_id = 1,
                                                     locale_id=1, translation_string='protoform',
                                                     translation='protoform')
            DBSession.add(new_uets)
            new_uets = UserEntitiesTranslationString(object_id=2, client_id = 1,
                                                     locale_id=1, translation_string='sound',
                                                     translation='sound')
            DBSession.add(new_uets)
            new_uets = UserEntitiesTranslationString(object_id=3, client_id = 1,
                                                     locale_id=1, translation_string='protoform',
                                                     translation='protoform')
            DBSession.add(new_uets)
            new_uets = UserEntitiesTranslationString(object_id=4, client_id = 1,
                                                     locale_id=1, translation_string='etymology',
                                                     translation='etymology')
            DBSession.add(new_uets)
            new_uets = UserEntitiesTranslationString(object_id=5, client_id = 1,
                                                     locale_id=1, translation_string='grouping_tag',
                                                     translation='grouping_tag')
            DBSession.add(new_uets)
            new_uets = UserEntitiesTranslationString(object_id=6, client_id = 1,
                                                     locale_id=1, translation_string='testgroup',
                                                     translation='testgroup')
            DBSession.add(new_uets)

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_view_perspective_fields(self):
        response = self.app.post_json('/signin', params={'login': 'test', 'password': 'pass'})
        response = self.app.get('/dictionary/1/1/perspective/1/1/fields')
        self.assertEqual(response.status_int, HTTPOk.code)
        print('HEY LISTEN!', response.body)
        # self.assertEqual(response.body,
        #                  [
        #                      {'entity_type': 'protoform', 'data_type': 'text', 'state': 'enabled'},
        #                      {'entity_type': 'sound', 'data_type': 'sound', 'state': 'enabled'
        #                       , 'contains': [{'entity_type': 'praat',
        #                                       'data_type': 'markup',
        #                                       'state': 'enabled'}]},
        #                      {'entity_type': 'protoform', 'data_type': 'text', 'state': 'enabled', 'group':'testgroup'},
        #                      {'entity_type': 'etymology', 'data_type': 'grouping_tag', 'state': 'enabled'}
        #                  ])
