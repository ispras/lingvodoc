import os
import sys
from configparser import ConfigParser

import transaction

from sqlalchemy import engine_from_config

from lingvodoc.utils.creation import (create_perspective,
                                      create_dbdictionary,
                                      create_dictionary_persp_to_field,
                                      edit_role,
                                      create_lexicalentry
                                      )
from lingvodoc.utils.starling_converter import create_entity

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
from sqlalchemy import create_engine
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


def find_service_translation(content, locale_id=2):
    atom = DBSession.query(TranslationAtom).join(TranslationGist)\
        .filter(TranslationAtom.content==content,
                TranslationAtom.locale_id==locale_id,
                TranslationGist.type=='Service').first()
    if atom:
        return atom.parent
    else:
        return None


def find_translation(content, locale_id=2):
    atom = DBSession.query(TranslationAtom).filter_by(content=content, locale_id=locale_id).order_by(TranslationAtom.client_id).first()
    if atom:
        return atom.parent
    else:
        return None


def data_init(manager, accounts, dbname):


    engine = create_engine(dbname)
    DBSession.configure(bind=engine)
    with manager:

        # creating base locales
        ru_locale = Locale(shortcut="ru", intl_name="Russian (Русский)")
        en_locale = Locale(shortcut="en", intl_name="English")
        fi_locale = Locale(shortcut="fi", intl_name="Finnish (Suomi)")
        fr_locale = Locale(shortcut="fr", intl_name="French (Français)")
        de_locale = Locale(shortcut="de", intl_name="German (Deutsch)")

        for locale in [ru_locale, en_locale, fi_locale, fr_locale, de_locale]:
            DBSession.add(locale)
        DBSession.flush()

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
            with open(os.path.dirname(__file__) + '/translations_base.json', 'r') as json_file:
                translations = json.loads(json_file.read())
        except Exception as e:
            import traceback
            print('couldn\'t read json file with translations')
            print(e.args)
            traceback.print_exc()
            pass

        for translation_string in sorted(translations):
            gist_type = translations[translation_string]['type']
            contents = list()
            for key in translations[translation_string]:
                if key != 'type' :
                    contents.append((translations[translation_string][key], key))
            create_translation(client_id=client.id, contents=contents, gist_type=gist_type)

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

        create_gist_from_string("Can delete lexical entries and entities")
        base_groups.append(BaseGroup(name="Can delete lexical entries and entities",
                                     subject="lexical_entries_and_entities",
                                     action="delete",
                                     perspective_default=True))

        create_gist_from_string("Can edit translationatom")
        base_groups.append(BaseGroup(name="Can edit translationatom",
                                     subject="translations",
                                     action="edit"))

        create_gist_from_string("Can delete translationgist")
        base_groups.append(BaseGroup(name="Can delete translationgist",
                                     subject="translations",
                                     action="delete"))

        create_gist_from_string("Can create grants")
        base_groups.append(BaseGroup(name="Can create grants ",
                                     subject="grant",
                                     action="create"))

        create_gist_from_string("Can approve grants")
        base_groups.append(BaseGroup(name="Can approve grants",
                                     subject="grant",
                                     action="approve"))

        create_gist_from_string("Can approve organizations")
        base_groups.append(BaseGroup(name="Can approve organizations",
                                     subject="organization",
                                     action="approve"))

        create_gist_from_string("Can edit dictionary status")
        base_groups.append(BaseGroup(name="Can edit dictionary status",
                                     subject="dictionary_status",
                                     action="edit",
                                     dictionary_default=True))

        create_gist_from_string("Can edit perspective status")
        base_groups.append(BaseGroup(name="Can edit perspective status",
                                     subject="perspective_status",
                                     action="edit",
                                     perspective_default=True))


        # create_gist_from_string("Can delete lexical entries")
        # base_groups.append(BaseGroup(name="Can delete lexical entries",
        #                              subject="lexical_entries_and_entities",
        #                              action="delete",
        #                              perspective_default=True))





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
                test_pwd = Passhash(password="12345")
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
                le_persp_name_gist = find_translation('Lexical Entries')
                par_persp_name_gist = find_translation('Paradigms')
                text_type_gist = find_service_translation('Text')
                sound_type_gist = find_service_translation('Sound')
                link_type_gist = find_service_translation('Link')
                image_type_gist = find_service_translation('Image')
                elan_type_gist = find_service_translation('ELAN markup')
                praat_type_gist = find_service_translation('Praat markup')
                word_gist = find_translation('Word')
                transcription_gist = find_translation('Transcription')
                sound_gist = find_translation('Sound')
                paradigm_gist = find_translation('Paradigmatic forms')
                #praat_gist = find_translation('Spectrogram')
                image_gist = find_translation('Image')
                elan_gist = find_translation('ELAN markup')
                test_dict = Dictionary(client_id=test_client.id,
                                       translation_gist_client_id=dict_name_gist.client_id,
                                       translation_gist_object_id=dict_name_gist.object_id,
                                       parent_client_id=russian_language.client_id,
                                       parent_object_id=russian_language.object_id,
                                       state_translation_gist_client_id=state_gist.client_id,
                                       state_translation_gist_object_id=state_gist.object_id)
                for base in DBSession.query(BaseGroup).filter_by(dictionary_default=True):
                    new_group = Group(parent=base,
                                      subject_object_id=test_dict.object_id,
                                      subject_client_id=test_dict.client_id)
                    DBSession.add(new_group)
                    DBSession.flush()
                DBSession.add(test_dict)
                DBSession.flush()

                test_persp = DictionaryPerspective(client_id=test_client.id,
                                                   translation_gist_client_id=le_persp_name_gist.client_id,
                                                   translation_gist_object_id=le_persp_name_gist.object_id,
                                                   parent_client_id=test_dict.client_id,
                                                   parent_object_id=test_dict.object_id,
                                                   state_translation_gist_client_id=state_gist.client_id,
                                                   state_translation_gist_object_id=state_gist.object_id)
                for base in DBSession.query(BaseGroup).filter_by(perspective_default=True):
                    new_group = Group(parent=base,
                                      subject_object_id=test_persp.object_id,
                                      subject_client_id=test_persp.client_id)
                    DBSession.add(new_group)
                    DBSession.flush()
                DBSession.add(test_persp)
                DBSession.flush()

                test_persp_link = DictionaryPerspective(client_id=test_client.id,
                                                   translation_gist_client_id=par_persp_name_gist.client_id,
                                                   translation_gist_object_id=par_persp_name_gist.object_id,
                                                   parent_client_id=test_dict.client_id,
                                                   parent_object_id=test_dict.object_id,
                                                   state_translation_gist_client_id=state_gist.client_id,
                                                   state_translation_gist_object_id=state_gist.object_id)
                for base in DBSession.query(BaseGroup).filter_by(perspective_default=True):
                    new_group = Group(parent=base,
                                      subject_object_id=test_persp_link.object_id,
                                      subject_client_id=test_persp_link.client_id)
                    DBSession.add(new_group)
                    DBSession.flush()
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


                image_field = Field(client_id=test_client.id,
                                   translation_gist_client_id=image_gist.client_id,
                                   translation_gist_object_id=image_gist.object_id,
                                   data_type_translation_gist_client_id=image_type_gist.client_id,
                                   data_type_translation_gist_object_id=image_type_gist.object_id)
                DBSession.add(image_field)


                elan_field = Field(client_id=test_client.id,
                                   translation_gist_client_id=elan_gist.client_id,
                                   translation_gist_object_id=elan_gist.object_id,
                                   data_type_translation_gist_client_id=elan_type_gist.client_id,
                                   data_type_translation_gist_object_id=elan_type_gist.object_id)
                DBSession.add(elan_field)

                #
                # praat_field = Field(client_id=test_client.id,
                #                    translation_gist_client_id=praat_gist.client_id,
                #                    translation_gist_object_id=praat_gist.object_id,
                #                    data_type_translation_gist_client_id=praat_type_gist.client_id,
                #                    data_type_translation_gist_object_id=praat_type_gist.object_id)
                # DBSession.add(praat_field)

                field_1 = DictionaryPerspectiveToField(client_id=test_client.id,
                                                       parent=test_persp,
                                                       field=word_field,
                                                       position=1
                                                       )
                field_2 = DictionaryPerspectiveToField(client_id=test_client.id,
                                                       parent=test_persp,
                                                       field=sound_field,
                                                       position=2
                                                       )
                field_3 = DictionaryPerspectiveToField(client_id=test_client.id,
                                                       parent=test_persp,
                                                       field=transcription_field,
                                                       upper_level=field_2,
                                                       position=3
                                                       )
                field_4 = DictionaryPerspectiveToField(client_id=test_client.id,
                                                       parent=test_persp,
                                                       field=paradigm_field,
                                                       link=test_persp_link,
                                                       position=4
                                                       )
                for field in [field_1,field_2, field_3, field_4]:
                    DBSession.add(field)

                field_1 = DictionaryPerspectiveToField(client_id=test_client.id,
                                                       parent=test_persp_link,
                                                       field=word_field,
                                                       position=1
                                                       )
                field_2 = DictionaryPerspectiveToField(client_id=test_client.id,
                                                       parent=test_persp_link,
                                                       field=transcription_field,
                                                       position=2
                                                       )
                field_3 = DictionaryPerspectiveToField(client_id=test_client.id,
                                                       parent=test_persp_link,
                                                       field=sound_field,
                                                       position=3
                                                       )
                for field in [field_1,field_2, field_3]:
                    DBSession.add(field)

                for group in base_groups:
                    if group.name == "Can edit dictionary status":
                        test_group = group
                edit_role(test_dict, test_account.id, test_group.id, admin_account.id, dictionary_default=True)

                lex_entry_1 = create_lexicalentry([test_client.id, None], [test_persp.client_id, test_persp.object_id],
                                                                             save_object=True)
                lex_entry_2 = create_lexicalentry([test_client.id, None], [test_persp.client_id, test_persp.object_id],
                                                                             save_object=True)
                link_lex_entry_1 = create_lexicalentry([test_client.id, None], [test_persp_link.client_id,
                                                                                test_persp_link.object_id],
                                                                            save_object=True)
                link_lex_entry_2 = create_lexicalentry([test_client.id, None], [test_persp_link.client_id,
                                                                                test_persp_link.object_id],
                                                                            save_object=True)
                lex_entity_1 = create_entity(id=[test_client.id, None], parent_id=[lex_entry_1.client_id,
                                                                                    lex_entry_1.object_id],
                                             additional_metadata=None, field_id=[word_field.client_id,
                                                                                 word_field.object_id],
                                             self_id=None, link_id=None,
                                             locale_id= locale_id, filename=None, content="lex entity 1",
                                             registry=None, request=None, save_object=False)

                lex_entity_2 = create_entity(id=[test_client.id, None], parent_id=[lex_entry_2.client_id,
                                                                                   lex_entry_2.object_id],
                                             additional_metadata=None, field_id=[word_field.client_id,
                                                                                 word_field.object_id],
                                             self_id=None, link_id=None,
                                             locale_id=locale_id, filename=None, content="lex entity 2",
                                             registry=None, request=None, save_object=False)

                link_lex_entity_1 = create_entity(id=[test_client.id, None], parent_id=[link_lex_entry_1.client_id,
                                                                                   link_lex_entry_1.object_id],
                                             additional_metadata=None, field_id=[word_field.client_id,
                                                                                 word_field.object_id],
                                             self_id=None, link_id=None,
                                             locale_id=locale_id, filename=None, content="link lex entity 1",
                                             registry=None, request=None, save_object=False)

                link_lex_entity_2 = create_entity(id=[test_client.id, None], parent_id=[link_lex_entry_2.client_id,
                                                                                   link_lex_entry_2.object_id],
                                             additional_metadata=None, field_id=[word_field.client_id,
                                                                                 word_field.object_id],
                                             self_id=None, link_id=None,
                                             locale_id=locale_id, filename=None, content="link lex entity 2",
                                             registry=None, request=None, save_object=False)

                '''
                with open(os.path.dirname(__file__)  + '/test_ids.txt', 'w', encoding='utf-8') as file:
                   file.write("Test ids: \n")
                   file.write("lex_entry 1: [%s, %s] \n" % (lex_entry_1.client_id, lex_entry_1.object_id))
                   file.write("lex_entry 2: [%s, %s] \n" % (lex_entry_2.client_id, lex_entry_2.object_id))
                   file.write("lex_link_entry 1: [%s, %s] \n" % (link_lex_entry_1.client_id, link_lex_entry_1.object_id))
                   file.write("lex_link_entry 2: [%s, %s] \n" % (link_lex_entry_2.client_id, link_lex_entry_2.object_id))
                   file.write("\n")
                   file.write("lex_entity_1: [%s, %s] \n" % (lex_entity_1.client_id, lex_entity_1.object_id))
                   file.write("lex_entity_2: [%s, %s] \n" % (lex_entity_2.client_id, lex_entity_2.object_id))
                   file.write("link_lex_entity_1: [%s, %s] \n" % (link_lex_entity_1.client_id, link_lex_entity_1.object_id))
                   file.write("link_lex_entity_2: [%s, %s] \n" % (link_lex_entity_2.client_id, link_lex_entity_2.object_id))
                   file.write("\n Field ids: \n")
                   file.write("Field: [%s, %s] \n" % (word_field.client_id, word_field.object_id))
                   file.write("\n")
                   file.write("Test_dict: [%s, %s] \n" % (test_dict.client_id, test_dict.object_id))
                   file.write("Test_persp: [%s, %s] \n" % (test_persp.client_id, test_persp.object_id))
                   file.write("Test_persp_link: [%s, %s] \n" % (test_persp_link.client_id, test_persp_link.object_id))
                   file.write("\n")
                   file.write("Word gist: [%s, %s] \n" % (word_gist.client_id, word_gist.object_id))
                   file.write("\n")
                   file.write("Test gist: [%s, %s] \n" % (dict_name_gist.client_id, dict_name_gist.object_id))
                   file.write("\n")
                   file.write("English atom: [%s, %s] \n" % (english_atom.client_id, english_atom.object_id))
                '''

            except Exception as e:
                import traceback
                print('couldn\'t create all test data')
                print(e.args)
                traceback.print_exc()
                pass




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
    # alembic_ini_path = os.path.join(
    #     os.path.dirname(__file__), 'alembic.ini')
    # parser = ConfigParser()
    # parser.read(alembic_ini_path)
    # alembic_conf = dict()
    # for k, v in parser.items('alembic'):
    #     alembic_conf[k] = v
    #dbname = alembic_conf['sqlalchemy.url']
    dbname = 'postgresql+psycopg2://postgres:@/test_base_1'
    data_init(transaction.manager, accounts, dbname)
