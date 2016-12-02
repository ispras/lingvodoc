from models import DBSession
from old_models import old_DBSession
from sqlalchemy import func
import json
from models import (
    Locale,
    User,
    Client,
    UserBlobs,
    BaseGroup,
    Group,
    Language,
    Dictionary,
    DictionaryPerspective,
    TranslationGist,
    TranslationAtom,
    Email,
    Passhash,
    Field,
    DictionaryPerspectiveToField,
    LexicalEntry,
    Entity,
    PublishingEntity
)
from old_models import (
    Locale as old_Locale,
    User as old_User,
    Client as old_Client,
    UserBlobs as old_UserBlobs,
    BaseGroup as old_BaseGroup,
    Group as old_Group,
    Language as old_Language,
    Dictionary as old_Dictionary,
    DictionaryPerspective as old_DictionaryPerspective,
    DictionaryPerspectiveField as old_Field,
    UserEntitiesTranslationString,
    UITranslationString,
    Email as old_Email,
    Passhash as old_Passhash,
    LexicalEntry as old_LexicalEntry,
    LevelOneEntity as old_l1entity,
    LevelTwoEntity as old_l2entity,
    GroupingEntity as old_grentity,
    PublishLevelOneEntity as old_publ1entity,
    PublishLevelTwoEntity as old_publ2entity,
    PublishGroupingEntity as old_pubgrentity
)
import json
for locale in old_DBSession.query(old_Locale).all():
    new_locale = Locale(id=locale.id,
                        shortcut=locale.shortcut,
                        intl_name=locale.intl_name)
    DBSession.add(new_locale)
DBSession.flush()
for user in old_DBSession.query(old_User).all():
    new_user = User(id=user.id, login=user.login, name=user.name, intl_name=user.intl_name, birthday=user.birthday,
                    created_at=user.signup_date,
                    is_active=user.is_active)
    if user.default_locale_id:
        new_user.default_locale_id = user.default_locale_id
    DBSession.add(new_user)
DBSession.flush()
for client in old_DBSession.query(old_Client).all():
    new_client = Client(id=client.id, user_id=client.user_id, created_at=client.creation_time,
                        is_browser_client=client.is_browser_client)
    DBSession.add(new_client)
DBSession.flush()
for email in old_DBSession.query(old_Email).all():
    new_email = Email(id=email.id, user_id=email.user_id, email=email.email)
    DBSession.add(new_email)
DBSession.flush()
for passhash in old_DBSession.query(old_Passhash).all():
    new_passhash = Passhash(id=passhash.id, user_id=passhash.user_id, hash=passhash.hash)
    DBSession.add(new_passhash)
DBSession.flush()
for userblob in old_DBSession.query(old_UserBlobs).all():
    new_userblob = UserBlobs(client_id=userblob.client_id, created_at=userblob.created_at,
                             name=userblob.name, content=userblob.content,
                             real_storage_path=userblob.real_storage_path, data_type=userblob.data_type,
                             marked_for_deletion=userblob.marked_for_deletion, user_id=userblob.user_id)
    if userblob.additional_metadata:
        new_userblob.additional_metadata = json.loads(userblob.additional_metadata)
    DBSession.add(new_userblob)
DBSession.flush()
for basegroup in old_DBSession.query(old_BaseGroup).all():
    new_basegroup = BaseGroup(id=basegroup.id, name=basegroup.translation_string, subject=basegroup.subject,
                              action=basegroup.action, dictionary_default=basegroup.dictionary_default,
                              perspective_default=basegroup.perspective_default)
    DBSession.add(new_basegroup)
DBSession.flush()
group_ids = dict()
for group in old_DBSession.query(old_Group).filter_by(
        subject_override=True).all():
    new_group = Group(id=group.id, base_group_id=group.base_group_id, subject_override=group.subject_override)
    DBSession.add(new_group)
DBSession.flush()
translation_strings = dict()
for language in old_DBSession.query(old_Language).all():
    translation_strings[language.translation_string] = {'type': 'Language', 'client_id': language.client_id}
for dictionary in old_DBSession.query(old_Dictionary).all():
    translation_strings[dictionary.translation_string] = {'type': 'Dictionary', 'client_id': dictionary.client_id}
for perspective in old_DBSession.query(old_DictionaryPerspective).all():
    translation_strings[perspective.translation_string] = {'type': 'Perspective', 'client_id': perspective.client_id}
for field in old_DBSession.query(old_Field).all():
    translation_strings[field.entity_type] = {'type': 'Field', 'client_id': field.client_id}
for field in old_DBSession.query(old_Field).all():
    translation_strings[field.data_type] = {'type': 'Service', 'client_id': field.client_id}

for translation_string in old_DBSession.query(UITranslationString):
    if not translation_strings.get(translation_string.translation_string):
        translation_strings[translation_string.translation_string] = {'type': 'Service', 'client_id': 1,
                                                                      translation_string.locale_id:
                                                                          {'content': translation_string.translation,
                                                                           'client_id': 1}}
    else:
        translation_strings[translation_string.translation_string][translation_string.locale_id] = {
            'content': translation_string.translation,
            'client_id': 1}

for translation_string in old_DBSession.query(UserEntitiesTranslationString):
    if not translation_strings.get(translation_string.translation_string):
        translation_strings[translation_string.translation_string] = {'type': 'Service', 'client_id': 1,
                                                                      translation_string.locale_id:
                                                                          {'content': translation_string.translation,
                                                                           'client_id': translation_string.client_id}}
    else:
        translation_strings[translation_string.translation_string][translation_string.locale_id] = {
            'content': translation_string.translation,
            'client_id': translation_string.client_id}
translation_strings['WiP'] = {'type': 'Service', 2: {'content': 'WiP', 'client_id': 1},
                              3: {'content': 'WiP', 'client_id': 1}, 1: {'content': 'WiP', 'client_id': 1},
                              'client_id': 1}
translation_strings['Published'] = {'type': 'Service', 2: {'content': 'Published', 'client_id': 1},
                                    3: {'content': 'Published', 'client_id': 1},
                                    1: {'content': 'Published', 'client_id': 1},
                                    'client_id': 1}
translation_strings['Limited access'] = {'type': 'Service', 2: {'content': 'Limited access', 'client_id': 1},
                                         3: {'content': 'Limited access', 'client_id': 1},
                                         1: {'content': 'Limited access', 'client_id': 1},
                                         'client_id': 1}
translation_strings['Service'] = {'type': 'Service', 2: {'content': 'Service', 'client_id': 1},
                                  3: {'content': 'Service', 'client_id': 1},
                                  1: {'content': 'Service', 'client_id': 1},
                                  'client_id': 1}
translation_strings['Hidden'] = {'type': 'Service', 2: {'content': 'Hidden', 'client_id': 1},
                                 3: {'content': 'Hidden', 'client_id': 1},
                                 1: {'content': 'Hidden', 'client_id': 1},
                                 'client_id': 1}
translation_strings['Converting 80%'] = {'type': 'Service', 2: {'content': 'Converting 80%', 'client_id': 1},
                                         3: {'content': 'Converting 80%', 'client_id': 1},
                                         1: {'content': 'Converting 80%', 'client_id': 1},
                                         'client_id': 1}
translation_strings['Converting'] = {'type': 'Service', 2: {'content': 'Converting', 'client_id': 1},
                                     3: {'content': 'Converting', 'client_id': 1},
                                     1: {'content': 'Converting', 'client_id': 1},
                                     'client_id': 1}
translation_strings['sound'] = {'type': 'Service', 2: {'content': 'Sound', 'client_id': 1},
                                3: {'content': 'Audio', 'client_id': 1},
                                1: {'content': 'Звук', 'client_id': 1},
                                'client_id': 1}
translation_strings['text'] = {'type': 'Service', 2: {'content': 'Text', 'client_id': 1},
                               3: {'content': 'Text', 'client_id': 1},
                               1: {'content': 'Текст', 'client_id': 1},
                               'client_id': 1}
translation_strings['markup'] = {'type': 'Service', 2: {'content': 'Praat markup', 'client_id': 1},
                                 3: {'content': 'Praat markup', 'client_id': 1},
                                 1: {'content': 'Praat разметка', 'client_id': 1},
                                 'client_id': 1}
translation_strings['grouping_tag'] = {'type': 'Service', 2: {'content': 'Grouping Tag', 'client_id': 1},
                                       3: {'content': 'Grouping Tag', 'client_id': 1},
                                       1: {'content': 'Группировочный тэг', 'client_id': 1},
                                       'client_id': 1}
translation_strings['image'] = {'type': 'Service', 2: {'content': 'Image', 'client_id': 1},
                                3: {'content': 'Image', 'client_id': 1},
                                1: {'content': 'Изображение', 'client_id': 1},
                                'client_id': 1}
translation_strings['link'] = {'type': 'Service', 2: {'content': 'Link', 'client_id': 1},
                               3: {'content': 'Link', 'client_id': 1},
                               1: {'content': 'Ссылка', 'client_id': 1},
                               'client_id': 1}
translation_strings['Link'] = {'type': 'Field', 2: {'content': 'Paradigmatic forms', 'client_id': 1},
                               3: {'content': 'Paradigmatic forms', 'client_id': 1},
                               1: {'content': 'Парадигма', 'client_id': 1},
                               'client_id': 1}
translation_strings['Backlink'] = {'type': 'Field', 2: {'content': 'Backref', 'client_id': 1},
                                   3: {'content': 'Backref', 'client_id': 1},
                                   1: {'content': 'Backref', 'client_id': 1},
                                   'client_id': 1}
translation_strings['elan'] = {'type': 'Service', 2: {'content': 'ELAN markup', 'client_id': 1},
                               3: {'content': 'ELAN markup', 'client_id': 1},
                               1: {'content': 'ELAN разметка', 'client_id': 1},
                               'client_id': 1}
translation_strings['Lingvodoc 0.98 etymology dictionary'] = {'type': 'Field',
                                                              2: {'content': 'Lexical Entries', 'client_id': 1},
                                                              3: {'content': 'Lexical Entries', 'client_id': 1},
                                                              1: {'content': 'Лексические входы', 'client_id': 1},
                                                              'client_id': 1}
translation_strings['Paradigms'] = {'type': 'Field', 2: {'content': 'Paradigms', 'client_id': 1},
                                    3: {'content': 'Paradigms', 'client_id': 1},
                                    1: {'content': 'Парадигмы', 'client_id': 1},
                                    'client_id': 1}
translation_strings['Praat markup'] = {'type': 'Field', 2: {'content': 'Markup', 'client_id': 1},
                                       3: {'content': 'Markup', 'client_id': 1},
                                       1: {'content': 'Разметка', 'client_id': 1},
                                       'client_id': 1}
translation_strings['Paradigm Praat markup'] = {'type': 'Field', 2: {'content': 'Paradigm Markup', 'client_id': 1},
                                                3: {'content': 'Paradigm Markup', 'client_id': 1},
                                                1: {'content': 'Разметка парадигмы', 'client_id': 1},
                                                'client_id': 1}
for trstring in translation_strings:  # todo: add permissions
    translation_string = translation_strings[trstring]
    translationgist = TranslationGist(client_id=translation_string['client_id'], type=translation_string['type'])
    DBSession.add(translationgist)
    DBSession.flush()
    translation_string['ids'] = {'client_id': translationgist.client_id, 'object_id': translationgist.object_id}
    for key in translation_string:
        if type(key) == int:
            translationatom = TranslationAtom(client_id=translation_string[key]['client_id'],
                                              parent=translationgist,
                                              content=translation_string[key]['content'],
                                              locale_id=key)
            DBSession.add(translationatom)

DBSession.flush()
DBSession.commit()

language_ids = dict()
for language in old_DBSession.query(old_Language).all():
    new_language = Language(client_id=language.client_id,
                            # parent_client_id=language.parent_client_id,
                            # parent_object_id=language.parent_object_id,
                            translation_gist_client_id=translation_strings[language.translation_string]['ids'][
                                'client_id'],
                            translation_gist_object_id=translation_strings[language.translation_string]['ids'][
                                'object_id'],
                            marked_for_deletion=language.marked_for_deletion
                            )
    DBSession.add(new_language)
    for group in old_DBSession.query(old_Group).join(old_BaseGroup).filter(
                    old_Group.subject_client_id == language.client_id,
                    old_Group.subject_object_id == language.object_id,
                    old_BaseGroup.subject == 'language').all():
        new_group = Group(id=group.id, base_group_id=group.base_group_id,
                          subject_client_id=new_language.client_id,
                          subject_object_id=new_language.object_id)
        DBSession.add(new_group)
    language_ids[str(language.client_id) + '_' + str(language.object_id)] = {'client_id': new_language.client_id,
                                                                             'object_id': new_language.object_id}
DBSession.flush()
for language in old_DBSession.query(old_Language).all():
    if not language.parent:
        continue
    ids = language_ids[str(language.client_id) + '_' + str(language.object_id)]
    new_language = DBSession.query(Language).filter_by(client_id=ids['client_id'], object_id=ids['object_id']
                                                       # parent_client_id=language.parent_client_id,
                                                       # parent_object_id=language.parent_object_id
                                                       ).first()
    parent_ids = language_ids[str(language.parent_client_id) + '_' + str(language.parent_object_id)]
    new_language.parent_client_id = parent_ids['client_id']
    new_language.parent_object_id = parent_ids['object_id']
DBSession.flush()
dictionary_ids = dict()
for dictionary in old_DBSession.query(old_Dictionary).all():
    if dictionary.parent_client_id and dictionary.parent_object_id:
        parent_ids = language_ids[str(dictionary.parent_client_id) + '_' + str(dictionary.parent_object_id)]
    else:
        parent_ids = {'client_id': None, 'object_id': None}
        continue
    new_dictionary = Dictionary(client_id=dictionary.client_id,
                                parent_client_id=parent_ids['client_id'],
                                parent_object_id=parent_ids['object_id'],
                                translation_gist_client_id=translation_strings[dictionary.translation_string]['ids'][
                                    'client_id'],
                                translation_gist_object_id=translation_strings[dictionary.translation_string]['ids'][
                                    'object_id'],
                                marked_for_deletion=dictionary.marked_for_deletion
                                )
    if dictionary.additional_metadata:
        new_dictionary.additional_metadata = json.loads(dictionary.additional_metadata)
    state_ids = translation_strings[dictionary.state]['ids']
    new_dictionary.state_translation_gist_object_id = state_ids['object_id']
    new_dictionary.state_translation_gist_client_id = state_ids['client_id']
    DBSession.add(new_dictionary)
    for group in old_DBSession.query(old_Group).join(old_BaseGroup).filter(
                    old_Group.subject_client_id == dictionary.client_id,
                    old_Group.subject_object_id == dictionary.object_id,
                    old_BaseGroup.dictionary_default == True).all():
        # print(group.id)
        new_group = Group(id=group.id, base_group_id=group.base_group_id,
                          subject_client_id=new_dictionary.client_id,
                          subject_object_id=new_dictionary.object_id)
        DBSession.add(new_group)
    dictionary_ids[str(dictionary.client_id) + '_' + str(dictionary.object_id)] = {
        'client_id': new_dictionary.client_id,
        'object_id': new_dictionary.object_id}
DBSession.flush()

perspective_ids = dict()
for perspective in old_DBSession.query(old_DictionaryPerspective).all():
    if perspective.parent_client_id and perspective.parent_object_id:
        if perspective.parent_client_id == 1 and perspective.parent_object_id == 1:
            continue
        parent_ids = dictionary_ids[str(perspective.parent_client_id) + '_' + str(perspective.parent_object_id)]
    else:
        parent_ids = {'client_id': None, 'object_id': None}
        continue
    new_perspective = DictionaryPerspective(client_id=perspective.client_id,
                                            parent_client_id=parent_ids['client_id'],
                                            parent_object_id=parent_ids['object_id'],
                                            translation_gist_client_id=
                                            translation_strings[perspective.translation_string]['ids']['client_id'],
                                            translation_gist_object_id=
                                            translation_strings[perspective.translation_string]['ids']['object_id'],
                                            marked_for_deletion=perspective.marked_for_deletion,
                                            is_template=perspective.is_template,
                                            import_source=perspective.import_source,
                                            import_hash=perspective.import_hash
                                            )
    if perspective.additional_metadata:
        new_perspective.additional_metadata = json.loads(perspective.additional_metadata)
    state_ids = translation_strings[perspective.state]['ids']
    new_perspective.state_translation_gist_object_id = state_ids['object_id']
    new_perspective.state_translation_gist_client_id = state_ids['client_id']
    DBSession.add(new_perspective)
    for group in old_DBSession.query(old_Group).join(old_BaseGroup).filter(
                    old_Group.subject_client_id == perspective.client_id,
                    old_Group.subject_object_id == perspective.object_id,
                    old_BaseGroup.perspective_default == True).all():
        # print(group.id)
        new_group = Group(id=group.id, base_group_id=group.base_group_id,
                          subject_client_id=new_perspective.client_id,
                          subject_object_id=new_perspective.object_id)
        DBSession.add(new_group)
    perspective_ids[str(perspective.client_id) + '_' + str(perspective.object_id)] = {
        'client_id': new_perspective.client_id,
        'object_id': new_perspective.object_id}
DBSession.flush()

old_fields_ids = dict()
fields = dict()
paradigm_persp = dict()
group_to_group = dict()
for table in [Group]:
    DBSession.execute(
        'select setval (\'%s_id_seq\', %s);' % (
            table.__tablename__, DBSession.query(func.max(table.id).label("id")).one().id + 1))
for field in old_DBSession.query(old_Field).filter_by(marked_for_deletion=False).all():
    parent_ids = perspective_ids.get(str(field.parent_client_id) + '_' + str(field.parent_object_id), None)
    if not parent_ids:
        parent_ids = {'client_id': None, 'object_id': None}
        continue
    new_field = fields.get(field.entity_type, None)
    if not new_field:
        new_field = Field(client_id=field.client_id,
                          translation_gist_client_id=translation_strings[field.entity_type]['ids']['client_id'],
                          translation_gist_object_id=translation_strings[field.entity_type]['ids']['object_id'],
                          data_type_translation_gist_client_id=translation_strings[field.data_type]['ids']['client_id'],
                          data_type_translation_gist_object_id=translation_strings[field.data_type]['ids']['object_id'])
        if 'translation' in field.entity_type.lower() or field.entity_type.lower() == 'text':  # todo: looks too bad
            new_field.is_translatable = True
        DBSession.add(new_field)
        DBSession.flush()
        fields[field.entity_type] = {'client_id': new_field.client_id,
                                     'object_id': new_field.object_id}
    else:
        new_field = DBSession.query(Field).filter_by(client_id=new_field['client_id'],
                                                     object_id=new_field['object_id']).first()

    if 'aradigm' in field.entity_type:
        parent_ids = paradigm_persp.get(str(field.parent_client_id) + '_' + str(field.parent_object_id), None)
        if not parent_ids:
            perspective = field.parent
            if perspective.parent_client_id and perspective.parent_object_id:
                if perspective.parent_client_id == 1 and perspective.parent_object_id == 1:
                    continue
                parent_ids = dictionary_ids[str(perspective.parent_client_id) + '_' + str(perspective.parent_object_id)]
            else:
                parent_ids = {'client_id': None, 'object_id': None}
                print(perspective.client_id, perspective.object_id)
                continue
            new_perspective = DictionaryPerspective(client_id=perspective.client_id,
                                                    parent_client_id=parent_ids['client_id'],
                                                    parent_object_id=parent_ids['object_id'],
                                                    translation_gist_client_id=
                                                    translation_strings['Paradigms']['ids'][
                                                        'client_id'],
                                                    translation_gist_object_id=
                                                    translation_strings['Paradigms']['ids'][
                                                        'object_id'],
                                                    marked_for_deletion=perspective.marked_for_deletion,
                                                    is_template=perspective.is_template,
                                                    import_source=perspective.import_source,
                                                    import_hash=perspective.import_hash
                                                    )
            if perspective.additional_metadata:
                new_perspective.additional_metadata = json.loads(perspective.additional_metadata)
            state_ids = translation_strings[perspective.state]['ids']
            new_perspective.state_translation_gist_object_id = state_ids['object_id']
            new_perspective.state_translation_gist_client_id = state_ids['client_id']
            DBSession.add(new_perspective)
            for group in old_DBSession.query(old_Group).join(old_BaseGroup).filter(
                            old_Group.subject_client_id == perspective.client_id,
                            old_Group.subject_object_id == perspective.object_id,
                            old_BaseGroup.perspective_default == True).all():
                # print(group.id)

                new_group = Group(base_group_id=group.base_group_id,
                                  subject_client_id=new_dictionary.client_id,
                                  subject_object_id=new_dictionary.object_id)  # todo: id
                DBSession.add(new_group)
                DBSession.flush()
                if group.id not in group_to_group:
                    group_to_group[group.id] = list()
                group_to_group[group.id].append(new_group.id)
            paradigm_persp[str(perspective.client_id) + '_' + str(perspective.object_id)] = {
                'client_id': new_perspective.client_id,
                'object_id': new_perspective.object_id}
            parent_ids = {
                'client_id': new_perspective.client_id,
                'object_id': new_perspective.object_id}
    persp_to_field = DictionaryPerspectiveToField(client_id=field.client_id,
                                                  parent_client_id=parent_ids['client_id'],
                                                  parent_object_id=parent_ids['object_id'],
                                                  position=field.position,
                                                  field_client_id=new_field.client_id,
                                                  field_object_id=new_field.object_id
                                                  )
    DBSession.add(persp_to_field)
    old_fields_ids[str(field.client_id) + '_' + str(field.object_id)] = {
        'client_id': persp_to_field.client_id,
        'object_id': persp_to_field.object_id}
DBSession.flush()
# print(old_fields_ids)
for field in old_DBSession.query(old_Field).filter_by(marked_for_deletion=False).all():
    if field.entity_client_id and field.entity_object_id:
        field_ids = old_fields_ids.get(str(field.client_id) + '_' + str(field.object_id), None)
        if not field_ids:
            continue
        new_persp_to_field = DBSession.query(DictionaryPerspectiveToField).filter_by(client_id=field_ids['client_id'],
                                                                                     object_id=field_ids[
                                                                                         'object_id']).first()
        parent_ids = old_fields_ids[str(field.entity_client_id) + '_' + str(field.entity_object_id)]
        new_persp_to_field.self_client_id = parent_ids['client_id']
        new_persp_to_field.self_object_id = parent_ids['object_id']

# DBSession.flush()
DBSession.commit()

lex_ids = dict()
for lex in old_DBSession.query(old_LexicalEntry).all():
    parent_ids = perspective_ids.get(str(lex.parent_client_id) + '_' + str(lex.parent_object_id), None)
    if not parent_ids:
        print(lex.client_id, lex.object_id)
        continue
    new_lex = LexicalEntry(client_id=lex.client_id,
                           marked_for_deletion=lex.marked_for_deletion,
                           parent_client_id=parent_ids['client_id'],
                           parent_object_id=parent_ids['object_id']
                           )
    DBSession.add(new_lex)
    lex_ids[str(lex.client_id) + '_' + str(lex.object_id)] = {'client_id': new_lex.client_id,
                                                              'object_id': new_lex.object_id}
DBSession.flush()
for lex in old_DBSession.query(old_LexicalEntry).all():
    if not lex.moved_to:
        continue
    ids = lex_ids[str(lex.client_id) + '_' + str(lex.object_id)]
    new_lex = DBSession.query(LexicalEntry).filter_by(client_id=ids['client_id'], object_id=ids['object_id']).first()
    moved_to_ids = language_ids[str(language.parent_client_id) + '_' + str(language.parent_object_id)]
    new_lex.moved_to = str(moved_to_ids['client_id']) + '_' + str(moved_to_ids['object_id'])
DBSession.flush()

DBSession.commit()
print(fields)
l1entity_ids = dict()
paradigm_lexes = dict()
link_ids = list()
for entity in old_DBSession.query(old_l1entity).all():
    parent_ids = lex_ids.get(str(entity.parent_client_id) + '_' + str(entity.parent_object_id), None)
    if not parent_ids:
        print('l1e', entity.client_id, entity.object_id)
        continue

    if 'aradigm' in entity.entity_type:
        old_parent_ids = parent_ids
        parent_ids = paradigm_lexes.get(
            str(entity.parent_client_id) + '_' + str(entity.parent_object_id) + '_' + str(
                json.loads(entity.additional_metadata)['row_id']), None)
        if not parent_ids:
            lex = entity.parent

            parent_ids = paradigm_persp.get(str(lex.parent_client_id) + '_' + str(lex.parent_object_id), None)
            if not parent_ids:
                print(lex.client_id, lex.object_id)
                continue
            new_lex = LexicalEntry(client_id=json.loads(entity.additional_metadata)['client_id'],
                                   marked_for_deletion=lex.marked_for_deletion,
                                   parent_client_id=parent_ids['client_id'],
                                   parent_object_id=parent_ids['object_id']
                                   )
            DBSession.add(new_lex)
            paradigm_lexes[str(entity.parent_client_id) + '_' + str(entity.parent_object_id) + '_' + str(
                json.loads(entity.additional_metadata)['row_id'])] = {'client_id': new_lex.client_id,
                                                                      'object_id': new_lex.object_id}
            link_ids.append((old_parent_ids,
                             {'client_id': new_lex.client_id,
                              'object_id': new_lex.object_id}))
            parent_ids = {
                'client_id': new_lex.client_id,
                'object_id': new_lex.object_id}

    new_entity = Entity(client_id=entity.client_id,
                        content=entity.content,
                        locale_id=entity.locale_id,
                        marked_for_deletion=entity.marked_for_deletion,
                        field_client_id=fields[entity.entity_type]['client_id'],
                        field_object_id=fields[entity.entity_type]['object_id'],
                        parent_client_id=parent_ids['client_id'],
                        parent_object_id=parent_ids['object_id'],
                        created_at=entity.created_at
                        )
    if entity.additional_metadata:
        new_entity.additional_metadata = json.loads(entity.additional_metadata)

    DBSession.add(new_entity)
    l1entity_ids[str(entity.client_id) + '_' + str(entity.object_id)] = {
        'client_id': new_entity.client_id,
        'object_id': new_entity.object_id}
    pub_ent = old_DBSession.query(old_publ1entity).filter_by(entity=entity).first()
    if pub_ent and not pub_ent.marked_for_deletion:
        new_entity.publishingentity.published = True
DBSession.flush()

grentity_ids = dict()
for entity in old_DBSession.query(old_grentity).all():
    parent_ids = lex_ids.get(str(entity.parent_client_id) + '_' + str(entity.parent_object_id), None)
    if not parent_ids:
        print('gre', entity.client_id, entity.object_id)
        continue
    new_entity = Entity(client_id=entity.client_id,
                        content=entity.content,
                        locale_id=entity.locale_id,
                        marked_for_deletion=entity.marked_for_deletion,
                        field_client_id=fields[entity.entity_type]['client_id'],
                        field_object_id=fields[entity.entity_type]['object_id'],
                        parent_client_id=parent_ids['client_id'],
                        parent_object_id=parent_ids['object_id'],
                        created_at=entity.created_at
                        )
    if entity.additional_metadata:
        new_entity.additional_metadata = json.loads(entity.additional_metadata)

    DBSession.add(new_entity)
    l1entity_ids[str(entity.client_id) + '_' + str(entity.object_id)] = {'client_id': new_entity.client_id,
                                                                         'object_id': new_entity.object_id}
    pub_ent = old_DBSession.query(old_pubgrentity).filter_by(entity=entity).first()
    if pub_ent and not pub_ent.marked_for_deletion:
        new_entity.publishingentity.published = True
DBSession.flush()

l2entity_ids = dict()
for entity in old_DBSession.query(old_l2entity).all():
    self_ids = l1entity_ids.get(str(entity.parent_client_id) + '_' + str(entity.parent_object_id), None)
    parent_entity = old_DBSession.query(old_l1entity).filter_by(client_id=entity.parent_client_id,
                                                                object_id=entity.parent_object_id).first()
    parent_ids = lex_ids.get(str(parent_entity.parent_client_id) + '_' + str(parent_entity.parent_object_id), None)
    if not parent_entity or not parent_ids:
        print('l2e', entity.client_id, entity.object_id)
        continue

    if 'aradigm' in entity.entity_type:
        if not json.loads(parent_entity.additional_metadata).get('row_id', None):
            import pdb

            # pdb.set_trace()
            print('paradigm exists but no row id')
            continue
        old_parent_ids = parent_ids
        parent_ids = paradigm_lexes.get(
            str(parent_entity.parent_client_id) + '_' + str(parent_entity.parent_object_id) + '_' + str(
                json.loads(parent_entity.additional_metadata)['row_id']), None)
        if not parent_ids:
            import pdb

            pdb.set_trace()
            print('l2e exist, but l1e don\'t')
            lex = entity.parent

            parent_ids = paradigm_persp.get(str(lex.parent_client_id) + '_' + str(lex.parent_object_id), None)
            if not parent_ids:
                print(lex.client_id, lex.object_id)
                continue
            new_lex = LexicalEntry(client_id=lex.client_id,
                                   marked_for_deletion=lex.marked_for_deletion,
                                   parent_client_id=parent_ids['client_id'],
                                   parent_object_id=parent_ids['object_id']
                                   )
            DBSession.add(new_lex)
            paradigm_lexes[str(parent_entity.parent_client_id) + '_' + str(parent_entity.parent_object_id) + '_' + str(
                json.loads(parent_entity.additional_metadata)['row_id'])] = {'client_id': new_lex.client_id,
                                                                             'object_id': new_lex.object_id}
            link_ids[str(old_parent_ids['client_id']) + '_' + str(old_parent_ids['object_id'])] = {
                'client_id': new_lex.client_id,
                'object_id': new_lex.object_id}
            parent_ids = {
                'client_id': new_lex.client_id,
                'object_id': new_lex.object_id}
    new_entity = Entity(client_id=entity.client_id,
                        # content=entity.content,
                        locale_id=entity.locale_id,
                        marked_for_deletion=entity.marked_for_deletion,
                        field_client_id=fields[entity.entity_type]['client_id'],
                        field_object_id=fields[entity.entity_type]['object_id'],
                        parent_client_id=parent_ids['client_id'],
                        parent_object_id=parent_ids['object_id'],
                        self_client_id=self_ids['client_id'],
                        self_object_id=self_ids['object_id'],
                        created_at=entity.created_at
                        )
    if entity.additional_metadata:
        new_entity.additional_metadata = json.loads(entity.additional_metadata)
        new_entity.additional_metadata['data_type'] = 'praat markup'
    if entity.content:
        new_entity.content = entity.content
    else:
        import pdb

        pdb.set_trace()
        print('no content')

    DBSession.add(new_entity)
    l2entity_ids[str(entity.client_id) + '_' + str(entity.object_id)] = {'client_id': new_entity.client_id,
                                                                         'object_id': new_entity.object_id}
    pub_ent = old_DBSession.query(old_publ2entity).filter_by(entity=entity).first()
    if pub_ent and not pub_ent.marked_for_deletion:
        new_entity.publishingentity.published = True
DBSession.flush()
DBSession.commit()

contents = dict()
for entity in DBSession.query(Entity).filter(Entity.content.like('%http%')).all():
    old_content_list = entity.content.split('/')
    content_len = len(old_content_list)

    new_content = 'http://lingvodoc.ispras.ru/objects/entity/%s/%s/%s/%s' % (old_content_list[content_len - 4],
                                                                             entity.client_id, entity.object_id,
                                                                             old_content_list[content_len - 1])
    contents[entity.content] = new_content
    # entity.content = new_content

DBSession.flush()

for userblob in DBSession.query(UserBlobs).all():
    old_path_list = userblob.real_storage_path.split('/')
    path_len = len(old_path_list)
    old_path_list[path_len - 3] = str(userblob.client_id)
    old_path_list[path_len - 2] = str(userblob.object_id)
    contents[userblob.real_storage_path] = '/'.join(old_path_list)
    # userblob.real_storage_path = '/'.join(old_path_list)

    old_content_list = userblob.content.split('/')
    content_len = len(old_content_list)
    old_content_list[content_len - 3] = str(userblob.client_id)
    old_content_list[content_len - 2] = str(userblob.object_id)
    contents[userblob.content] = '/'.join(old_content_list)
    # userblob.content = '/'.join(old_content_list)

DBSession.flush()
DBSession.commit()

contents_json = "old_to_new_contents.jsn"
with open(contents_json, 'w') as json_file:
    json_file.write(json.dumps(contents))
contents_json = "link_ids.jsn"
with open(contents_json, 'w') as json_file:
    json_file.write(json.dumps(link_ids))
contents_json = "translation_strings.jsn"
with open(contents_json, 'w') as json_file:
    json_file.write(json.dumps(translation_strings))

for group in old_DBSession.query(old_Group).all():
    new_group = DBSession.query(Group).filter_by(id=group.id).first()
    if new_group:
        if group_to_group.get(group.id):
            for gr_id in group_to_group[group.id]:
                second_group = DBSession.query(Group).filter_by(id=gr_id).first()
                for user in group.users:
                    new_user = DBSession.query(User).filter_by(id=user.id).first()
                    if new_user not in second_group.users:
                        second_group.users.append(new_user)
        for user in group.users:
            new_user = DBSession.query(User).filter_by(id=user.id).first()
            if new_user not in new_group.users:
                new_group.users.append(new_user)

DBSession.flush()
DBSession.commit()

contents_json = "old_to_new_contents.jsn"
with open(contents_json, 'r') as json_file:
    contents = json.loads(json_file.read())
contents_json = "link_ids.jsn"
with open(contents_json, 'r') as json_file:
    link_ids = json.loads(json_file.read())
contents_json = "translation_strings.jsn"
with open(contents_json, 'r') as json_file:
    translation_strings = json.loads(json_file.read())

for table in [User, Email, Client, Locale, BaseGroup, Group, Passhash]:
    DBSession.execute(
        'select setval (\'%s_id_seq\', %s);' % (
            table.__tablename__, DBSession.query(func.max(table.id).label("id")).one().id + 1))


# # # for table in [TranslationGist, TranslationAtom, Language, Dictionary, DictionaryPerspective,
# # #               DictionaryPerspectiveToField, Field, LexicalEntry, Entity, UserBlobs]:
# # #     DBSession.execute(
# # #         'select setval (\'%s_object_id_seq\', %s);' % (
# # #             table.__tablename__, DBSession.query(func.max(table.object_id).label("id")).one().id + 1))
# # #


def create_translation(client_id, contents=list(), gist_type='Service'):
    gist = TranslationGist(client_id=client_id, type=gist_type)
    DBSession.add(gist)
    DBSession.flush()
    for content in contents:
        atom = TranslationAtom(client_id=client_id, content=content[0], locale_id=content[1], parent=gist)
        DBSession.add(atom)
    DBSession.flush()
    return gist


create_gist_from_string = lambda x: create_translation(client_id=1,
                                                       contents=[(x, 2)],
                                                       gist_type='Service')

base_groups = list()
create_gist_from_string("Can edit translationatom")
base_groups.append(BaseGroup(name="Can edit translationatom",
                             subject="translations",
                             action="edit"))

create_gist_from_string("Can delete translationgist")
base_groups.append(BaseGroup(name="Can delete translationgist",
                             subject="translations",
                             action="delete"))

for base_group in base_groups:
    DBSession.add(base_group)

link_field = Field(client_id=1,
                   translation_gist_client_id=translation_strings['Link']['ids']['client_id'],
                   translation_gist_object_id=translation_strings['Link']['ids']['object_id'],
                   data_type_translation_gist_client_id=translation_strings['link']['ids']['client_id'],
                   data_type_translation_gist_object_id=translation_strings['link']['ids']['object_id'])
DBSession.add(link_field)
DBSession.flush()

backlink_field = Field(client_id=1,
                       translation_gist_client_id=translation_strings['Backlink']['ids']['client_id'],
                       translation_gist_object_id=translation_strings['Backlink']['ids']['object_id'],
                       data_type_translation_gist_client_id=translation_strings['link']['ids']['client_id'],
                       data_type_translation_gist_object_id=translation_strings['link']['ids']['object_id'])
DBSession.add(backlink_field)
DBSession.flush()
DBSession.commit()

DBSession.flush()
persp_links = dict()
for link in link_ids:
    word = link[0]
    paradigm = link[1]
    first_lex = DBSession.query(LexicalEntry).filter_by(client_id=word['client_id'], object_id=word['object_id']).one()
    first_perspective = first_lex.parent
    second_lex = DBSession.query(LexicalEntry).filter_by(client_id=paradigm['client_id'],
                                                         object_id=paradigm['object_id']).one()
    DBSession.flush()
    second_perspective = second_lex.parent
    if not persp_links.get(first_perspective, None):
        persp_links[first_perspective] = second_perspective

        position = DBSession.query(func.max(DictionaryPerspectiveToField.position)).filter_by(
            parent_client_id=first_perspective.client_id,
            parent_object_id=first_perspective.object_id).scalar() + 1

        persp_to_field = DictionaryPerspectiveToField(client_id=first_perspective.client_id,
                                                      parent_client_id=first_perspective.client_id,
                                                      parent_object_id=first_perspective.object_id,
                                                      position=position,  # todo: check
                                                      field_client_id=link_field.client_id,
                                                      field_object_id=link_field.object_id,
                                                      link_client_id=second_perspective.client_id,
                                                      link_object_id=second_perspective.object_id
                                                      )
        DBSession.add(persp_to_field)
        DBSession.flush()

        position = DBSession.query(func.max(DictionaryPerspectiveToField.position)).filter_by(
            parent_client_id=second_perspective.client_id,
            parent_object_id=second_perspective.object_id).scalar() + 1

        persp_to_field_2 = DictionaryPerspectiveToField(client_id=second_perspective.client_id,
                                                        parent_client_id=second_perspective.client_id,
                                                        parent_object_id=second_perspective.object_id,
                                                        position=position,  # todo: check
                                                        field_client_id=backlink_field.client_id,
                                                        field_object_id=backlink_field.object_id,
                                                        link_client_id=first_perspective.client_id,
                                                        link_object_id=first_perspective.object_id
                                                        )
        DBSession.add(persp_to_field_2)
        DBSession.flush()

    new_entity = Entity(client_id=first_lex.client_id,
                        parent_client_id=first_lex.client_id,
                        parent_object_id=first_lex.object_id,
                        field_client_id=link_field.client_id,
                        field_object_id=link_field.object_id,
                        link_client_id=second_lex.client_id,
                        link_object_id=second_lex.object_id
                        )
    DBSession.add(new_entity)
    new_entity.publishingentity.published = True
    DBSession.flush()

    new_entity = Entity(client_id=second_lex.client_id,
                        parent_client_id=second_lex.client_id,
                        parent_object_id=second_lex.object_id,
                        field_client_id=backlink_field.client_id,
                        field_object_id=backlink_field.object_id,
                        link_client_id=first_lex.client_id,
                        link_object_id=first_lex.object_id
                        )
    DBSession.add(new_entity)
    new_entity.publishingentity.published = True
    DBSession.flush()

DBSession.flush()
DBSession.commit()

for basegroup in old_DBSession.query(old_BaseGroup).all():
    new_basegroup = DBSession.query(BaseGroup).filter_by(id=basegroup.id).one()
    new_basegroup.action = basegroup.action
DBSession.flush()
DBSession.commit()

translation_gists = DBSession.query(TranslationGist).all()
gist_base = DBSession.query(BaseGroup).filter_by(action="delete",
                                                 subject="translations").one()
for tr_gist in translation_gists:
    client = DBSession.query(Client).filter_by(id=tr_gist.client_id).one()
    user = DBSession.query(User).filter_by(id=client.user_id).one()
    new_group = Group(parent=gist_base, subject_client_id=tr_gist.client_id,
                      subject_object_id=tr_gist.object_id)
    user.groups.append(new_group)

translation_atoms = DBSession.query(TranslationAtom).all()
atom_base = DBSession.query(BaseGroup).filter_by(action="edit",
                                                 subject="translations").one()
for tr_atom in translation_atoms:
    client = DBSession.query(Client).filter_by(id=tr_atom.client_id).one()
    user = DBSession.query(User).filter_by(id=client.user_id).one()
    new_group = Group(parent=atom_base, subject_client_id=tr_atom.client_id,
                      subject_object_id=tr_atom.object_id)
    user.groups.append(new_group)
admin = DBSession.query(User).filter_by(id=1).one()
gist_group = Group(parent=gist_base, subject_override=True)
admin.groups.append(gist_group)
atom_group = Group(parent=atom_base, subject_override=True)
admin.groups.append(atom_group)
DBSession.flush()
DBSession.commit()

for entity in DBSession.query(Entity).all():
    entity.publishingentity.accepted = True

DBSession.flush()
DBSession.commit()
with open('group_to_group', 'w') as gr_fi:
    gr_fi.write(json.dumps(group_to_group))
non_existing_groups = list()
for perspective in DBSession.query(DictionaryPerspective).all():
    groups = DBSession.query(Group).filter_by(subject_client_id=perspective.client_id,
                                              subject_object_id=perspective.object_id).all()
    if not groups:
        non_existing_groups.append((perspective.client_id, perspective.object_id))
        # for persp in perspective.parent.dictionaryperspective:
        #     groups = DBSession.query(Group).filter_by(subject_client_id=persp.client_id,
        #                                               subject_object_id=persp.object_id).all()
        #     if groups:
        #         for group in groups:
        #             new_group = Group(base_group_id=group.base_group_id,
        #                               subject_client_id=perspective.client_id,
        #                               subject_object_id=perspective.object_id)  # todo: id
        #             for user in group.users:
        #                 new_group.users.append(user)
        #             DBSession.add(new_group)
with open('non_existing_groups', 'w') as ne_fi:
    ne_fi.write(json.dumps(non_existing_groups))

DBSession.flush()
DBSession.commit()
