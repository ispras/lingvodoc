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
            new_dict=Dictionary(client_id=1,object_id=1,name='test')
            DBSession.add(new_dict)
            new_dict=Dictionary(client_id=1,object_id=2,name='test2')
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
        response = dictionaries_list(request)
        self.assertEqual(response['status'], HTTPOk.code)
        self.assertEqual(response['dictionaries'], [{'object_id': 1, 'client_id': 1}, {'object_id':2,'client_id':1}])


class TestViewPerspectiveFieldsFailureCondition(unittest.TestCase):

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

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_view_perspective_fields(self):
        from lingvodoc.views import view_perspective_fields
        request = testing.DummyRequest()
        request.matchdict['perspective_client_id'] = 42
        request.matchdict['perspective_object_id'] = 'a'
        response = view_perspective_fields(request)
        self.assertEqual(response['status'], HTTPNotFound.code)


class TestViewPerspectiveFieldsSuccessCondition(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        from lingvodoc.models import (
            Base,
            DictionaryPerspectiveField,
            DictionaryPerspective
            )
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        with transaction.manager:
            persp = DictionaryPerspective(client_id=1,object_id=1)
            DBSession.add(persp)
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

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_view_perspective_fields(self):
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        from lingvodoc.models import (
            Base,
            DictionaryPerspectiveField,
            DictionaryPerspective
            )
        DBSession.configure(bind=engine)
        from lingvodoc.views import view_perspective_fields
        request = testing.DummyRequest()
        request.matchdict['perspective_client_id'] = 1
        request.matchdict['perspective_object_id'] = 1
        response = view_perspective_fields(request)
        self.maxDiff = None
        self.assertEqual(response['status'], HTTPOk.code)
        self.assertEqual(response['fields'],
                         [
                             {'entity_type': 'protoform', 'data_type': 'text', 'state': 'enabled'},
                             {'entity_type': 'sound', 'data_type': 'sound', 'state': 'enabled'
                              , 'contains': [{'entity_type': 'praat',
                                              'data_type': 'markup',
                                              'state': 'enabled'}]},
                             {'entity_type': 'protoform', 'data_type': 'text', 'state': 'enabled', 'group':'testgroup'},
                             {'entity_type': 'etymology', 'data_type': 'grouping_tag', 'state': 'enabled'}
                         ])