from lingvodoc.models import (
    Client,
    DBSession,
    Dictionary,
    DictionaryPerspective,
    DictionaryPerspectiveToField,
    Field,
    LexicalEntry,
    Entity,
    Language,
    Organization,
    User,
    UserBlobs,
    TranslationAtom,
    TranslationGist,
    categories,
    ObjectTOC
)

from sqlalchemy import and_

from pyramid.request import Request

from sqlalchemy.inspection import inspect
from sqlalchemy.orm import joinedload

import datetime
import base64
import json
import os
import shutil
from pathvalidate import sanitize_filename
from collections import deque

from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPNotFound,
    HTTPOk,
    HTTPInternalServerError,
    HTTPConflict
)
from lingvodoc.exceptions import CommonException
from sqlalchemy.exc import IntegrityError

# todo: all of this should be in models


def real_delete_object(obj):
    DBSession.delete(DBSession.query(ObjectTOC).filter_by(client_id=obj.client_id, object_id=obj.object_id).first())
    DBSession.delete(obj)


def real_delete_language(language, settings):
    for child in language.language:
        real_delete_language(child, settings)
    for dictionary in language.dictionary:
        real_delete_dictionary(dictionary, settings)
    real_delete_object(language)


def real_delete_dictionary(dictionary, settings):
    for perspective in dictionary.perspectives:
        real_delete_perspective(perspective, settings)
    real_delete_object(dictionary)


def real_delete_perspective(perspective, settings):
    for field in perspective.dictionaryperspectivetofield:
        real_delete_object(field)
    for lex in perspective.lexicalentry:
        real_delete_lexical_entry(lex, settings)
    real_delete_object(perspective)


def real_delete_lexical_entry(lexical_entry, settings):
    for entity in lexical_entry.entity:
        if not entity.upper_level:
            real_delete_entity(entity, settings)
    real_delete_object(lexical_entry)


def real_delete_entity(entity, settings):
    for child in entity.entity:
        real_delete_entity(child, settings)
    if entity.additional_metadata and 'data_type' in entity.additional_metadata:
        try:
            path = entity.content
            base_path = settings['storage']['path']
            storage_dir = os.path.join(base_path, 'entity', entity.additional_metadata['data_type'],
                                       str(entity.client_id), str(entity.object_id))
            split_path = path.split('/')
            path = os.path.join(storage_dir, split_path[len(split_path) - 1])
            # todo: make path in windows
            os.remove(path)
        except:
            print('fail with entity', entity.client_id, entity.object_id)
    real_delete_object(entity)


def real_delete_translation_gist(translation_gist, settings):
    for translation_atom in translation_gist.translationatom:
        real_delete_object(translation_atom)
    real_delete_object(translation_gist)