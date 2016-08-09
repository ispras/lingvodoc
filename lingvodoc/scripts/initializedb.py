import os
import sys
import transaction

from sqlalchemy import engine_from_config

from pyramid.paster import (
    get_appsettings,
    setup_logging,
    )

from pyramid.scripts.common import parse_vars

from ..models import (
    DBSession,
    Base,
    User,
    Passhash,
    Language,
    Locale,
    BaseGroup,
    Group,
    Dictionary,
    DictionaryPerspective,
    Client,
    Email,
    TranslationGist,
    TranslationAtom,
    Field,
    DictionaryPerspectiveToField
    )

import json

test_init = True


def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: %s <config_uri> [var=value]\n'
          '(example: "%s development.ini")' % (cmd, cmd))
    sys.exit(1)


def create_translation(client_id, contents=list(), gist_type='Service'):
    gist = TranslationGist(client_id=client_id, type=gist_type)
    DBSession.add(gist)
    DBSession.flush()
    for content in contents:
        atom = TranslationAtom(client_id=client_id, content=content[0], locale_id=content[1], parent=gist)
        DBSession.add(atom)
    DBSession.flush()
    return gist


def find_translation(content, locale_id=2):
    atom = DBSession.query(TranslationAtom).filter_by(content=content, locale_id=locale_id).first()
    if atom:
        return atom.parent
    else:
        return None


def data_init(manager, accounts):
    with manager:
        # Creating global administrator
        admin_account = DBSession.query(User).filter_by(login=accounts['administrator_login']).first()
        if admin_account:
        # print("Admin record not found, initializing")
            print("Admin record found", admin_account.id, admin_account.login)
            return
        admin_account = User(login=accounts['administrator_login'],
                             name="Администратор",
                             intl_name="System Administrator",
                             )
        pwd = Passhash(password=accounts['administrator_password'])
        email = Email(email="al@somestuff.ru")
        admin_account.password = pwd
        DBSession.add(pwd)
        DBSession.add(admin_account)
        DBSession.flush()
        client = Client(user_id=admin_account.id, is_browser_client=False)
        email.user = admin_account
        DBSession.add(email)
        DBSession.add(client)

        DBSession.flush()

        # creating base locales
        ru_locale = Locale(shortcut="ru", intl_name="Russian (Русский)")
        en_locale = Locale(shortcut="en", intl_name="English")
        fi_locale = Locale(shortcut="fi", intl_name="Finnish (Suomi)")
        fr_locale = Locale(shortcut="fr", intl_name="French (Français)")
        de_locale = Locale(shortcut="de", intl_name="German (Deutsch)")

        for locale in [ru_locale, en_locale, fi_locale, fr_locale, de_locale]:
            DBSession.add(locale)
        locale_id = en_locale.id

        # Initializing base locales and languages
        russian_gist = TranslationGist(client_id=client.id, type='Service')
        english_gist = TranslationGist(client_id=client.id, type='Service')
        finnish_gist = TranslationGist(client_id=client.id, type='Service')
        french_gist = TranslationGist(client_id=client.id, type='Service')
        german_gist = TranslationGist(client_id=client.id, type='Service')
        for gist in [russian_gist, english_gist, finnish_gist, french_gist, german_gist]:
            DBSession.add(gist)
        russian_atom = TranslationAtom(client_id=client.id,
                                       parent=russian_gist,
                                       locale_id=locale_id,
                                       content="Russian language")
        english_atom = TranslationAtom(client_id=client.id,
                                       parent=english_gist,
                                       locale_id=locale_id,
                                       content="English language")
        finnish_atom = TranslationAtom(client_id=client.id,
                                       parent=finnish_gist,
                                       locale_id=locale_id,
                                       content="Finnish language")
        french_atom = TranslationAtom(client_id=client.id,
                                      parent=french_gist,
                                      locale_id=locale_id,
                                      content="French language")
        german_atom = TranslationAtom(client_id=client.id,
                                      parent=german_gist,
                                      locale_id=locale_id,
                                      content="German language")
        for atom in [russian_atom, english_atom, finnish_atom, french_atom, german_atom]:
            DBSession.add(atom)
        DBSession.flush()
        #
        #
        russian_language = Language(client_id=client.id,
                                    translation_gist_client_id=russian_gist.client_id,
                                    translation_gist_object_id=russian_gist.object_id)
        english_language = Language(client_id=client.id,
                                    translation_gist_client_id=english_gist.client_id,
                                    translation_gist_object_id=english_gist.object_id)
        finnish_language = Language(client_id=client.id,
                                    translation_gist_client_id=finnish_gist.client_id,
                                    translation_gist_object_id=finnish_gist.object_id)
        french_language = Language(client_id=client.id,
                                   translation_gist_client_id=french_gist.client_id,
                                   translation_gist_object_id=french_gist.object_id)
        german_language = Language(client_id=client.id,
                                   translation_gist_client_id=german_gist.client_id,
                                   translation_gist_object_id=german_gist.object_id)
        for lang in [russian_language, english_language, finnish_language, french_language, german_language]:
            DBSession.add(lang)
        DBSession.flush()
        ru_locale.parent = russian_language
        en_locale.parent = english_language
        fi_locale.parent = finnish_language
        fr_locale.parent = french_language
        de_locale.parent = german_language
        DBSession.flush()


        base_groups = []
# everyone
#         base_groups.append(BaseGroup(translation_string="Can view users",
#                                      subject="users",
#                                      action="view"))
#         base_groups.append(BaseGroup(translation_string="Can view organizations",
#                                      subject="dictionary",
#                                      action="view"))
#         base_groups.append(BaseGroup(translation_string="Can get dictionaries list",
#                                      subject="dictionary",
#                                      action="view"))
#         base_groups.append(BaseGroup(translation_string="Can get languages list",
#                                      subject="language",
#                                      action="view"))

# authenticated
        create_gist_from_string = lambda x: create_translation(client_id=client.id,
                                                              contents=[(x, locale_id)],
                                                              gist_type='Service')
        translations = dict()
        try:
            with open('lingvodoc/scripts/translations_base.json', 'r') as json_file:
                translations = json.loads(json_file.read())
        except:
            pass
        for translation_string in translations:
            gist_type = translations[translation_string]['type']
            contents = list()
            for key in translations[translation_string]:
                if key != 'type':
                    contents.append((translations[translation_string][key], key))
            last_gist = create_translation(client_id=client.id, contents=contents, gist_type=gist_type)

        create_gist_from_string("Can create dictionaries")
        base_groups.append(BaseGroup(name="Can create dictionaries",
                                     subject="dictionary",
                                     action="create"))

        create_gist_from_string("Can create languages")
        base_groups.append(BaseGroup(name="Can create languages",
                                     subject="language",
                                     action="create"))

        create_gist_from_string("Can create organizations")
        base_groups.append(BaseGroup(name="Can create organizations",
                                     subject="organization",
                                     action="create"))

        create_gist_from_string("Can create translation strings")
        base_groups.append(BaseGroup(name="Can create translation strings",
                                     subject="translation_string",
                                     action="create"))
# owner

        create_gist_from_string("Can edit languages")
        base_groups.append(BaseGroup(name="Can edit languages",
                                     subject="language",
                                     action="edit"))
        # only if orphaned

        create_gist_from_string("Can delete languages")
        base_groups.append(BaseGroup(name="Can delete languages",
                                     subject="language",
                                     action="delete"))

        create_gist_from_string("Can delete dictionary")
        base_groups.append(BaseGroup(name="Can delete dictionary",  # not really sure if it is needed
                                     subject="dictionary",
                                     action="delete",
                                     dictionary_default=True))

        create_gist_from_string("Can delete perspective")
        base_groups.append(BaseGroup(name="Can delete perspective",  # not really sure if it is needed
                                     subject="perspective",
                                     action="delete",
                                     perspective_default=True))

        create_gist_from_string("Can edit user")
        base_groups.append(BaseGroup(name="Can edit user",
                                     subject="edit_user",
                                     action="edit"))

        create_gist_from_string("Can edit dictionary options")
        base_groups.append(BaseGroup(name="Can edit dictionary options",
                                     subject="dictionary",
                                     action="edit",
                                     dictionary_default=True))

# owner + assigned

        create_gist_from_string("Can get dictionary role list")
        base_groups.append(BaseGroup(name="Can get dictionary role list",
                                     subject="dictionary_role",
                                     action="view",
                                     dictionary_default=True))

        create_gist_from_string("Can get perspective role list")
        base_groups.append(BaseGroup(name="Can get perspective role list",
                                     subject="perspective_role",
                                     action="view",
                                     perspective_default=True))

        create_gist_from_string("Can view published lexical entries")
        base_groups.append(BaseGroup(name="Can view published lexical entries",
                                     subject="approve_entities",
                                     action="view",
                                     perspective_default=True))

        create_gist_from_string("Can create dictionary roles and assign collaborators")
        base_groups.append(BaseGroup(name="Can create dictionary roles and assign collaborators",
                                     subject="dictionary_role",
                                     action="create",
                                     dictionary_default=True))

        create_gist_from_string("Can create perspective roles and assign collaborators")
        base_groups.append(BaseGroup(name="Can create perspective roles and assign collaborators",
                                     subject="perspective_role",
                                     action="create",
                                     perspective_default=True))

        create_gist_from_string("Can resign users from dictionary editors")
        base_groups.append(BaseGroup(name="Can resign users from dictionary editors",
                                     subject="dictionary_role",
                                     action="delete",
                                     dictionary_default=True))

        create_gist_from_string("Can resign users from perspective editors")
        base_groups.append(BaseGroup(name="Can resign users from perspective editors",
                                     subject="perspective_role",
                                     action="delete",
                                     perspective_default=True))

        create_gist_from_string("Can edit organization")
        base_groups.append(BaseGroup(name="Can edit organization",
                                     subject="organization",
                                     action="edit"))

        create_gist_from_string("Can create perspectives")
        base_groups.append(BaseGroup(name="Can create perspectives",
                                     subject="perspective",
                                     action="create",
                                     dictionary_default=True))

        create_gist_from_string("Can edit perspective")
        base_groups.append(BaseGroup(name="Can edit perspective",
                                     subject="perspective",
                                     action="edit",
                                     perspective_default=True))

        create_gist_from_string("Can create lexical entries")
        base_groups.append(BaseGroup(name="Can create lexical entries",
                                     subject="lexical_entries_and_entities",
                                     action="create",
                                     perspective_default=True))

        create_gist_from_string("Can delete lexical entries")
        base_groups.append(BaseGroup(name="Can delete lexical entries",
                                     subject="lexical_entries_and_entities",
                                     action="delete",
                                     perspective_default=True))

        # create_gist_from_string("Can delete lexical entries")
        # base_groups.append(BaseGroup(name="Can delete lexical entries",
        #                              subject="lexical_entries_and_entities",
        #                              action="delete",
        #                              perspective_default=True))

        create_gist_from_string("Can view unpublished lexical entries")
        base_groups.append(BaseGroup(name="Can view unpublished lexical entries",
                                     subject="lexical_entries_and_entities",
                                     action="view",
                                     perspective_default=True))

        create_gist_from_string("Can approve lexical entries and publish")
        base_groups.append(BaseGroup(name="Can approve lexical entries and publish",
                                     subject="approve_entities",
                                     action="create",
                                     perspective_default=True))

        create_gist_from_string("Can deactivate lexical entries")
        base_groups.append(BaseGroup(name="Can deactivate lexical entries",
                                     subject="approve_entities",
                                     action="delete",
                                     perspective_default=True))

        create_gist_from_string("Can merge dictionaries and perspectives")
        base_groups.append(BaseGroup(name="Can merge dictionaries and perspectives",
                                     subject="merge",
                                     action="create",
                                     dictionary_default=True))

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

        DBSession.flush()

        # admin groups with overrides
        adm_group_list = []
        for base_group in base_groups:
            adm_group_list.append(Group(base_group_id=base_group.id, subject_override=True))
            for adm_group in adm_group_list:
                DBSession.add(adm_group)
                if not adm_group in admin_account.groups:
                    admin_account.groups.append(adm_group)
        DBSession.flush()



        if test_init:
            try:
                test_account = User(login="Test",
                                     name="Test",
                                     intl_name="Test"
                                     )
                test_pwd = Passhash(password="123456")
                test_email = Email(email="test@test.ru")
                test_account.password = test_pwd
                DBSession.add(test_pwd)
                DBSession.add(test_account)
                DBSession.flush()
                test_client = Client(user_id=test_account.id)
                test_email.user = test_account
                DBSession.add(test_email)
                DBSession.add(test_client)
                basegroups = []
                basegroups += [DBSession.query(BaseGroup).filter_by(name="Can create dictionaries").first()]
                basegroups += [DBSession.query(BaseGroup).filter_by(name="Can create languages").first()]
                basegroups += [DBSession.query(BaseGroup).filter_by(name="Can create organizations").first()]
                basegroups += [DBSession.query(BaseGroup).filter_by(name="Can create translation strings").first()]
                groups = []
                for base in basegroups:
                    groups += [DBSession.query(Group).filter_by(subject_override=True, base_group_id=base.id).first()]
                for group in groups:
                    if group not in test_account.groups:
                        test_account.groups.append(group)
                DBSession.flush()


                translationatom = DBSession.query(TranslationAtom)\
                    .join(TranslationGist).\
                    filter(TranslationAtom.content == "WiP",
                           TranslationAtom.locale_id == 2,
                           TranslationGist.type == 'Service')\
                    .one()
                state_gist = translationatom.parent
                dict_name_gist = find_translation('Dictionary of Middle-Ob dialect Mansi')
                persp_name_gist = find_translation('Lingvodoc 0.98 etymology dictionary')
                text_type_gist = find_translation('text')
                sound_type_gist = find_translation('sound')
                link_type_gist = find_translation('link')
                word_gist = find_translation('Word')
                transcription_gist = find_translation('Transcription')
                sound_gist = find_translation('Sound')
                paradigm_gist = find_translation('Paradigmatic forms')
                test_dict = Dictionary(client_id=test_client.id,
                                       translation_gist_client_id=dict_name_gist.client_id,
                                       translation_gist_object_id=dict_name_gist.object_id,
                                       parent_client_id=russian_language.client_id,
                                       parent_object_id=russian_language.object_id,
                                       state_translation_gist_client_id=state_gist.client_id,
                                       state_translation_gist_object_id=state_gist.object_id)
                DBSession.add(test_dict)
                DBSession.flush()

                test_persp = DictionaryPerspective(client_id=test_client.id,
                                                   translation_gist_client_id=persp_name_gist.client_id,
                                                   translation_gist_object_id=persp_name_gist.object_id,
                                                   parent_client_id=test_dict.client_id,
                                                   parent_object_id=test_dict.object_id,
                                                   state_translation_gist_client_id=state_gist.client_id,
                                                   state_translation_gist_object_id=state_gist.object_id)
                DBSession.add(test_persp)
                DBSession.flush()

                test_persp_link = DictionaryPerspective(client_id=test_client.id,
                                                   translation_gist_client_id=persp_name_gist.client_id,
                                                   translation_gist_object_id=persp_name_gist.object_id,
                                                   parent_client_id=test_dict.client_id,
                                                   parent_object_id=test_dict.object_id,
                                                   state_translation_gist_client_id=state_gist.client_id,
                                                   state_translation_gist_object_id=state_gist.object_id)
                DBSession.add(test_persp_link)
                DBSession.flush()

                word_field = Field(client_id=test_client.id,
                                   translation_gist_client_id=word_gist.client_id,
                                   translation_gist_object_id=word_gist.object_id,
                                   data_type_translation_gist_client_id=text_type_gist.client_id,
                                   data_type_translation_gist_object_id=text_type_gist.object_id)
                DBSession.add(word_field)

                sound_field = Field(client_id=test_client.id,
                                   translation_gist_client_id=sound_gist.client_id,
                                   translation_gist_object_id=sound_gist.object_id,
                                   data_type_translation_gist_client_id=sound_type_gist.client_id,
                                   data_type_translation_gist_object_id=sound_type_gist.object_id)
                DBSession.add(sound_field)

                transcription_field = Field(client_id=test_client.id,
                                   translation_gist_client_id=transcription_gist.client_id,
                                   translation_gist_object_id=transcription_gist.object_id,
                                   data_type_translation_gist_client_id=text_type_gist.client_id,
                                   data_type_translation_gist_object_id=text_type_gist.object_id)
                DBSession.add(transcription_field)

                paradigm_field = Field(client_id=test_client.id,
                                   translation_gist_client_id=paradigm_gist.client_id,
                                   translation_gist_object_id=paradigm_gist.object_id,
                                   data_type_translation_gist_client_id=link_type_gist.client_id,
                                   data_type_translation_gist_object_id=link_type_gist.object_id)
                DBSession.add(paradigm_field)

                field_1 = DictionaryPerspectiveToField(client_id=test_client.id,
                                                       perspective=test_persp,
                                                       field=word_field,
                                                       position=1
                                                       )
                field_2 = DictionaryPerspectiveToField(client_id=test_client.id,
                                                       perspective=test_persp,
                                                       field=sound_field,
                                                       position=2
                                                       )
                field_3 = DictionaryPerspectiveToField(client_id=test_client.id,
                                                       perspective=test_persp,
                                                       field=transcription_field,
                                                       upper_level=field_2,
                                                       position=3
                                                       )
                field_4 = DictionaryPerspectiveToField(client_id=test_client.id,
                                                       perspective=test_persp,
                                                       field=paradigm_field,
                                                       link=test_persp_link,
                                                       position=4
                                                       )
                for field in [field_1,field_2, field_3, field_4]:
                    DBSession.add(field)

                field_1 = DictionaryPerspectiveToField(client_id=test_client.id,
                                                       perspective=test_persp_link,
                                                       field=word_field,
                                                       position=1
                                                       )
                field_2 = DictionaryPerspectiveToField(client_id=test_client.id,
                                                       perspective=test_persp_link,
                                                       field=transcription_field,
                                                       position=2
                                                       )
                field_3 = DictionaryPerspectiveToField(client_id=test_client.id,
                                                       perspective=test_persp_link,
                                                       field=sound_field,
                                                       position=3
                                                       )
                for field in [field_1,field_2, field_3]:
                    DBSession.add(field)

            except Exception as e:
                import traceback
                print('couldn\'t create all test data')
                print(e.args)
                traceback.print_exc()
                pass


        # fake_dictionary = Dictionary(client_id=client.id,
        #                              #object_id=1,
        #                              translation_string="Fake dictionary",
        #                              state="Service")
        # DBSession.add(fake_dictionary)
        # DBSession.flush()
        #
        # dialeqt_template = DictionaryPerspective(client_id=client.id,
        #                                          #object_id=1,
        #                                          parent_client_id=fake_dictionary.client_id,
        #                                          parent_object_id=fake_dictionary.object_id,
        #                                          is_template=True,
        #                                          state="Service",
        #                                          translation_string="Lingvodoc desktop version")
        # DBSession.add(dialeqt_template)
        # DBSession.flush()
        #
        # word_ld = DictionaryPerspectiveField(parent_object_id=dialeqt_template.object_id, parent_client_id=dialeqt_template.client_id,
        #                                      #object_id=1,
        #                                      client_id=client.id,
        #                                      entity_type="Word", data_type="text", level="leveloneentity", position=1,
        #                                      state="enabled")
        # transcription_ld = DictionaryPerspectiveField(parent_object_id=dialeqt_template.object_id, parent_client_id=dialeqt_template.client_id,
        #                                               #object_id=2,
        #                                               client_id=client.id,
        #                                               entity_type="Transcription", data_type="text",
        #                                               level="leveloneentity", position=2,
        #                                               state="enabled")
        # translation_ld = DictionaryPerspectiveField(parent_object_id=dialeqt_template.object_id, parent_client_id=dialeqt_template.client_id,
        #                                             #object_id=3,
        #                                             client_id=client.id,
        #                                             entity_type="Translation",
        #                                             data_type="text", level="leveloneentity", position=3,
        #                                             state="enabled")
        # sound_ld = DictionaryPerspectiveField(parent_object_id=dialeqt_template.object_id, parent_client_id=dialeqt_template.client_id,
        #                                       #object_id=4,
        #                                       client_id=client.id,
        #                                       entity_type="Sound", data_type="sound", level="leveloneentity", position=4,
        #                                       state="enabled")
        # for field in [word_ld, transcription_ld, translation_ld, sound_ld]:
        #     DBSession.add(field)
        # DBSession.flush()
        # praat_ld = DictionaryPerspectiveField(parent_object_id=dialeqt_template.object_id, parent_client_id=dialeqt_template.client_id,
        #                                       entity_object_id=sound_ld.object_id, entity_client_id=sound_ld.client_id,
        #                                       #object_id=5,
        #                                       client_id=client.id,
        #                                       entity_type="Praat markup", data_type="markup", level="leveltwoentity", position=5,
        #                                       state="enabled")
        # paradigm_word_ld = DictionaryPerspectiveField(parent_object_id=dialeqt_template.object_id, parent_client_id=dialeqt_template.client_id,
        #                                               #object_id=6,
        #                                               client_id=client.id,
        #                                               entity_type="Paradigm word", data_type="text", level="leveloneentity",
        #                                               group="Paradigm", position=6,
        #                                               state="enabled")
        # paradigm_transcription_ld = DictionaryPerspectiveField(parent_object_id=dialeqt_template.object_id, parent_client_id=dialeqt_template.client_id,
        #                                                        #object_id=7,
        #                                                        client_id=client.id,
        #                                                        entity_type="Paradigm transcription", data_type="text",
        #                                                        level="leveloneentity",
        #                                                        group="Paradigm",
        #                                                        position=7,
        #                                                        state="enabled")
        # paradigm_translation_ld = DictionaryPerspectiveField(parent_object_id=dialeqt_template.object_id, parent_client_id=dialeqt_template.client_id,
        #                                                      #object_id=8,
        #                                                      client_id=client.id,
        #                                                      entity_type="Paradigm translation", data_type="text",
        #                                                      group="Paradigm",
        #                                                      level="leveloneentity", position=8,
        #                                                      state="enabled")
        # paradigm_sound_ld = DictionaryPerspectiveField(parent_object_id=dialeqt_template.object_id, parent_client_id=dialeqt_template.client_id,
        #                                                #object_id=9,
        #                                                client_id=client.id,
        #                                                group="Paradigm",
        #                                                entity_type="Paradigm sound", data_type="sound", level="leveloneentity",
        #                                                position=9,
        #                                                state="enabled")
        # for field in [praat_ld, paradigm_word_ld, paradigm_transcription_ld,
        #               paradigm_translation_ld, paradigm_sound_ld]:
        #     DBSession.add(field)
        # DBSession.flush()
        # paradigm_praat_ld = DictionaryPerspectiveField(parent_object_id=dialeqt_template.object_id, parent_client_id=dialeqt_template.client_id,
        #                                                entity_object_id=paradigm_sound_ld.object_id, entity_client_id=paradigm_sound_ld.client_id,
        #                                                #object_id=10,
        #                                                client_id=client.id,
        #                                                group="Paradigm",
        #                                                entity_type="Paradigm Praat markup", data_type="markup",
        #                                                level="leveltwoentity", position=10,
        #                                                state="enabled")
        # etymology_ld = DictionaryPerspectiveField(parent_object_id=dialeqt_template.object_id, parent_client_id=dialeqt_template.client_id,
        #                                           #object_id=11,
        #                                           client_id=client.id,
        #                                           entity_type="Etymology", data_type="grouping_tag", level="groupingentity",
        #                                           position=11,
        #                                           state="enabled")
        # for field in [paradigm_praat_ld, etymology_ld]:
        #     DBSession.add(field)
        #
        # regular_dictionary_template = DictionaryPerspective(client_id=client.id,
        #                                                     #object_id=1,
        #                                                     parent_client_id=fake_dictionary.client_id,
        #                                                     parent_object_id=fake_dictionary.object_id,
        #                                                     is_template=True,
        #                                                     state="Service",
        #                                                     translation_string="Regular dictionary")
        # DBSession.add(regular_dictionary_template)
        # DBSession.flush()
        #
        # protoform_ordinary = DictionaryPerspectiveField(parent_client_id=regular_dictionary_template.client_id,
        #                                                 parent_object_id=regular_dictionary_template.object_id,
        #                                                 client_id=client.id,
        #                                                 data_type="text",
        #                                                 level='leveloneentity',
        #                                                 state="enabled",
        #                                                 position=1,
        #                                                 entity_type="Protoform"
        #                                                 )
        # word_ordinary = DictionaryPerspectiveField(parent_client_id=regular_dictionary_template.client_id,
        #                                            parent_object_id=regular_dictionary_template.object_id,
        #                                            client_id=client.id,
        #                                            data_type="text",
        #                                            level='leveloneentity',
        #                                            state="enabled",
        #                                            position=2,
        #                                            entity_type="Word"
        #                                            )
        # transcription_ordinary = DictionaryPerspectiveField(parent_client_id=regular_dictionary_template.client_id,
        #                                                     parent_object_id=regular_dictionary_template.object_id,
        #                                                     client_id=client.id,
        #                                                     data_type="text",
        #                                                     level='leveloneentity',
        #                                                     state="enabled",
        #                                                     position=3,
        #                                                     entity_type="Transcription"
        #                                                     )
        # duration_1_vowel_ordinary = DictionaryPerspectiveField(parent_client_id=regular_dictionary_template.client_id,
        #                                                        parent_object_id=regular_dictionary_template.object_id,
        #                                                        client_id=client.id,
        #                                                        data_type="text",
        #                                                        level='leveloneentity',
        #                                                        state="enabled",
        #                                                        position=4,
        #                                                        entity_type="Duration 1 vowel"
        #                                                        )
        #
        # intensity_1_vowel_ordinary = DictionaryPerspectiveField(parent_client_id=regular_dictionary_template.client_id,
        #                                                         parent_object_id=regular_dictionary_template.object_id,
        #                                                         client_id=client.id,
        #                                                         data_type="text",
        #                                                         level='leveloneentity',
        #                                                         state="enabled",
        #                                                         position=5,
        #                                                         entity_type="Intensity 1 vowel"
        #                                                         )
        # native_speaker_ordinary = DictionaryPerspectiveField(parent_client_id=regular_dictionary_template.client_id,
        #                                                      parent_object_id=regular_dictionary_template.object_id,
        #                                                      client_id=client.id,
        #                                                      data_type="text",
        #                                                      level='leveloneentity',
        #                                                      state="enabled",
        #                                                      position=6,
        #                                                      entity_type="Native speaker"
        #                                                      )
        # dialect_ordinary = DictionaryPerspectiveField(parent_client_id=regular_dictionary_template.client_id,
        #                                               parent_object_id=regular_dictionary_template.object_id,
        #                                               client_id=client.id,
        #                                               data_type="text",
        #                                               level='leveloneentity',
        #                                               state="enabled",
        #                                               position=1,
        #                                               entity_type="Dialect"
        #                                               )
        # translation_ld_ordinary = DictionaryPerspectiveField(parent_client_id=regular_dictionary_template.client_id,
        #                                                      parent_object_id=regular_dictionary_template.object_id,
        #                                                      client_id=client.id,
        #                                                      data_type="text",
        #                                                      level='leveloneentity',
        #                                                      state="enabled",
        #                                                      position=7,
        #                                                      entity_type="Translation"
        #                                                      )
        # grammatical_form_ordinary = DictionaryPerspectiveField(parent_client_id=regular_dictionary_template.client_id,
        #                                                        parent_object_id=regular_dictionary_template.object_id,
        #                                                        client_id=client.id,
        #                                                        data_type="text",
        #                                                        level='leveloneentity',
        #                                                        state="enabled",
        #                                                        position=8,
        #                                                        entity_type="Grammatical form"
        #                                                        )
        # it_is_formed_from_ordinary = DictionaryPerspectiveField(parent_client_id=regular_dictionary_template.client_id,
        #                                                         parent_object_id=regular_dictionary_template.object_id,
        #                                                         client_id=client.id,
        #                                                         data_type="text",
        #                                                         level='leveloneentity',
        #                                                         state="enabled",
        #                                                         position=9,
        #                                                         entity_type="It is formed from"
        #                                                         )
        # similarity_ordinary = DictionaryPerspectiveField(parent_client_id=regular_dictionary_template.client_id,
        #                                                  parent_object_id=regular_dictionary_template.object_id,
        #                                                  client_id=client.id,
        #                                                  data_type="text",
        #                                                  level='leveloneentity',
        #                                                  state="enabled",
        #                                                  position=10,
        #                                                  entity_type="Similarity"
        #                                                  )
        # the_page_ordinary = DictionaryPerspectiveField(parent_client_id=regular_dictionary_template.client_id,
        #                                                parent_object_id=regular_dictionary_template.object_id,
        #                                                client_id=client.id,
        #                                                data_type="text",
        #                                                level='leveloneentity',
        #                                                state="enabled",
        #                                                position=11,
        #                                                entity_type="the Page"
        #                                                )
        # the_line_ordinary = DictionaryPerspectiveField(parent_client_id=regular_dictionary_template.client_id,
        #                                                parent_object_id=regular_dictionary_template.object_id,
        #                                                client_id=client.id,
        #                                                data_type="text",
        #                                                level='leveloneentity',
        #                                                state="enabled",
        #                                                position=12,
        #                                                entity_type="the Line"
        #                                                )
        # the_head_ordinary = DictionaryPerspectiveField(parent_client_id=regular_dictionary_template.client_id,
        #                                                parent_object_id=regular_dictionary_template.object_id,
        #                                                client_id=client.id,
        #                                                data_type="text",
        #                                                level='leveloneentity',
        #                                                state="enabled",
        #                                                position=13,
        #                                                entity_type="the Head"
        #                                                )
        # the_verse_ordinary = DictionaryPerspectiveField(parent_client_id=regular_dictionary_template.client_id,
        #                                                 parent_object_id=regular_dictionary_template.object_id,
        #                                                 client_id=client.id,
        #                                                 data_type="text",
        #                                                 level='leveloneentity',
        #                                                 state="enabled",
        #                                                 position=14,
        #                                                 entity_type="the Verse"
        #                                                 )
        # notes_ordinary = DictionaryPerspectiveField(parent_client_id=regular_dictionary_template.client_id,
        #                                             parent_object_id=regular_dictionary_template.object_id,
        #                                             client_id=client.id,
        #                                             data_type="text",
        #                                             level='leveloneentity',
        #                                             state="enabled",
        #                                             position=15,
        #                                             entity_type="Notes"
        #                                             )
        # for field in [protoform_ordinary, word_ordinary, transcription_ordinary, duration_1_vowel_ordinary, intensity_1_vowel_ordinary,
        #               native_speaker_ordinary, dialect_ordinary, translation_ld_ordinary, grammatical_form_ordinary,
        #               it_is_formed_from_ordinary, similarity_ordinary, the_page_ordinary, the_line_ordinary,
        #               the_head_ordinary, the_verse_ordinary, notes_ordinary]:
        #     DBSession.add(field)
        #
        #
        # morphodict = DictionaryPerspective(client_id=client.id,
        #                                    parent_client_id=fake_dictionary.client_id,
        #                                    parent_object_id=fake_dictionary.object_id,
        #                                    is_template=True,
        #                                    state="Service",
        #                                    translation_string="Morhological dictionary")
        # DBSession.add(morphodict)
        # DBSession.flush()
        #
        # morph_cate = DictionaryPerspectiveField(parent_client_id=morphodict.client_id,
        #                                         parent_object_id=morphodict.object_id,
        #                                         client_id=client.id,
        #                                         data_type="text", level="leveloneentity",
        #                                         state='enabled',
        #                                         position=0,
        #                                         entity_type="Grammatical category")
        #
        # form_morph = DictionaryPerspectiveField(parent_client_id=morphodict.client_id,
        #                                         parent_object_id=morphodict.object_id,
        #                                         client_id=client.id,
        #                                         data_type="text", level="leveloneentity",
        #                                         state='enabled',
        #                                         position=1,
        #                                         entity_type="Form")
        # transcription_morph = DictionaryPerspectiveField(parent_client_id=morphodict.client_id,
        #                                                  parent_object_id=morphodict.object_id,
        #                                                  client_id=client.id,
        #                                                  data_type="text", level="leveloneentity",
        #                                                  state='enabled',
        #                                                  position=2,
        #                                                  entity_type="Transcription")
        # variants_morph = DictionaryPerspectiveField(parent_client_id=morphodict.client_id,
        #                                             parent_object_id=morphodict.object_id,
        #                                             client_id=client.id,
        #                                             data_type="text", level="leveloneentity",
        #                                             state='enabled',
        #                                             position=3,
        #                                             entity_type="Variants")
        # native_speaker_morph = DictionaryPerspectiveField(parent_client_id=morphodict.client_id,
        #                                                   parent_object_id=morphodict.object_id,
        #                                                   client_id=client.id,
        #                                                   data_type="text", level="leveloneentity",
        #                                                   state='enabled',
        #                                                   position=4,
        #                                                   entity_type="Native speaker")
        # text_morph = DictionaryPerspectiveField(parent_client_id=morphodict.client_id,
        #                                         parent_object_id=morphodict.object_id,
        #                                         client_id=client.id,
        #                                         data_type="text", level="leveloneentity",
        #                                         state='enabled',
        #                                         position=5,
        #                                         entity_type="Text")
        # dialect_morph = DictionaryPerspectiveField(parent_client_id=morphodict.client_id,
        #                                            parent_object_id=morphodict.object_id,
        #                                            client_id=client.id,
        #                                            data_type="text", level="leveloneentity",
        #                                            state='enabled',
        #                                            position=6,
        #                                            entity_type="Dialect")
        # in_combination_with_cat_morph = DictionaryPerspectiveField(parent_client_id=morphodict.client_id,
        #                                                            parent_object_id=morphodict.object_id,
        #                                                            client_id=client.id,
        #                                                            data_type="text", level="leveloneentity",
        #                                                            state='enabled',
        #                                                            position=7,
        #                                                            entity_type="in combination with categories")
        # frequency_morph = DictionaryPerspectiveField(parent_client_id=morphodict.client_id,
        #                                              parent_object_id=morphodict.object_id,
        #                                              client_id=client.id,
        #                                              data_type="text", level="leveloneentity",
        #                                              state='enabled',
        #                                              position=8,
        #                                              entity_type="Frequency")
        # number_of_an_affix_morph = DictionaryPerspectiveField(parent_client_id=morphodict.client_id,
        #                                                       parent_object_id=morphodict.object_id,
        #                                                       client_id=client.id,
        #                                                       data_type="text", level="leveloneentity",
        #                                                       state='enabled',
        #                                                       position=9,
        #                                                       entity_type="Number of an affix")
        # the_page_morph = DictionaryPerspectiveField(parent_client_id=morphodict.client_id,
        #                                             parent_object_id=morphodict.object_id,
        #                                             client_id=client.id,
        #                                             data_type="text", level="leveloneentity",
        #                                             state='enabled',
        #                                             position=10,
        #                                             entity_type="the Page")
        # the_line_morph = DictionaryPerspectiveField(parent_client_id=morphodict.client_id,
        #                                             parent_object_id=morphodict.object_id,
        #                                             client_id=client.id,
        #                                             data_type="text", level="leveloneentity",
        #                                             state='enabled',
        #                                             position=11,
        #                                             entity_type="the Line")
        # notes_morph = DictionaryPerspectiveField(parent_client_id=morphodict.client_id,
        #                                          parent_object_id=morphodict.object_id,
        #                                          client_id=client.id,
        #                                          data_type="text", level="leveloneentity",
        #                                          state='enabled',
        #                                          position=12,
        #                                          entity_type="Notes")
        #
        # for field in [morph_cate, form_morph, transcription_morph, variants_morph, native_speaker_morph, text_morph,
        #               dialect_morph, in_combination_with_cat_morph, frequency_morph, number_of_an_affix_morph,
        #               the_page_morph, the_line_morph, notes_morph]:
        #     DBSession.add(field)


def main(argv=sys.argv):
    if len(argv) < 2:
        usage(argv)
    config_uri = argv[1]
    options = parse_vars(argv[2:])
    setup_logging(config_uri)
    settings = get_appsettings(config_uri, options=options)
    accounts = get_appsettings(config_uri, 'accounts')
    engine = engine_from_config(settings, 'sqlalchemy.')

    DBSession.configure(bind=engine)
    # Base.metadata.create_all(engine)
    # with transaction.manager:
    data_init(transaction.manager, accounts)
