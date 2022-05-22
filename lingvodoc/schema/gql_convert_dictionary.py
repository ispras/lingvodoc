import graphene

from lingvodoc.schema.gql_holders import (
    client_id_check,
    ResponseError,
    LingvodocID,
    ObjectVal
)

from lingvodoc.models import (
    Client,
    DBSession,
    Dictionary as dbDictionary,
    TranslationGist as dbTranslationGist
)
import logging
from lingvodoc.cache.caching import TaskStatus

from lingvodoc.views.v2.convert_dictionary_dialeqt.core import async_convert_dictionary_new
from lingvodoc.scripts.dictionary_dialeqt_converter import convert_all as dialeqt_convert_all

from lingvodoc.views.v2.utils import anonymous_userid
log = logging.getLogger(__name__)
from lingvodoc.utils.creation import create_gists_with_atoms
from lingvodoc.utils.corpus_converter import convert_all
from lingvodoc.queue.celery import celery
import transaction

from lingvodoc.cache.caching import CACHE

class ConvertDictionary(graphene.Mutation):
    """
    example:
    mutation {
        create_lexicalentry(id: [949,21], perspective_id: [71,5]) {
            field {
                id
            }
            triumph
        }
    }

    (this example works)
    returns:

    {
      "create_lexicalentry": {
        "field": {
          "id": [
            949,
            21
          ]
        },
        "triumph": true
      }
    }
    """

    class Arguments:
        dictionary_id = LingvodocID()
        blob_id = LingvodocID(required=True)
        language_id = LingvodocID()
        translation_gist_id = LingvodocID()
        translation_atoms = graphene.List(ObjectVal)
        license = graphene.String()
        synchronous = graphene.Boolean()

    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):
        request = info.context.request
        locale_id = int(request.cookies.get('locale_id') or 1)
        client_id = request.authenticated_userid
        synchronous = args.get('synchronous', False)
        if not client_id:
            user_id = anonymous_userid(request)
        else:
            user_id = Client.get_user_by_client_id(client_id).id
        cur_args = dict()
        if "dictionary_id" in args:
            cur_args["dictionary_client_id"] = args["dictionary_id"][0]
            cur_args["dictionary_object_id"] = args["dictionary_id"][1]
        else:
            cur_args["dictionary_client_id"] = None
            cur_args["dictionary_object_id"] = None
        cur_args["client_id"] = client_id
        cur_args['blob_client_id'] = args['blob_id'][0]
        cur_args['blob_object_id'] = args['blob_id'][1]
        if "language_id" in args:
            cur_args["language_client_id"] = args['language_id'][0]
            cur_args["language_object_id"] = args['language_id'][1]
        else:
            cur_args["language_client_id"] = None
            cur_args["language_object_id"] = None
        if "translation_gist_id" in args:
            cur_args["gist_client_id"] = args['translation_gist_id'][0]
            cur_args["gist_object_id"] = args['translation_gist_id'][1]
        elif "translation_atoms" in args:
            tr_atoms = args.get("translation_atoms")
            translation_gist_id = args.get('translation_gist_id')
            translation_gist_id = create_gists_with_atoms(tr_atoms, translation_gist_id, [client_id, None], gist_type="Dictionary")

            # We have to commit, because eventually in
            # lingvodoc.scripts.dictionary_dialeqt_converter.convert_db_new
            # we will start a new transaction via 'with transaction.manager' line at
            # dictionary_dialeqt_converter.py:599,
            # and without commit the gist we've just created will be unavailable then.

            transaction.manager.commit()

            cur_args["gist_client_id"] = translation_gist_id[0]
            cur_args["gist_object_id"] = translation_gist_id[1]
        else:
            cur_args["gist_client_id"] = None
            cur_args["gist_object_id"] = None

        cur_args['license'] = args.get('license')

        cur_args["sqlalchemy_url"] = request.registry.settings["sqlalchemy.url"]
        cur_args["storage"] = request.registry.settings["storage"]
        cur_args["locale_id"] = locale_id
        cur_args["cache_kwargs"] = request.registry.settings["cache_kwargs"]
        gist = DBSession.query(dbTranslationGist).filter_by(client_id=cur_args["gist_client_id"],
                                                          object_id=cur_args["gist_object_id"]).first()
        try:
            if gist:
                task = TaskStatus(user_id, "Dialeqt dictionary conversion", gist.get_translation(locale_id), 10)

            else:
                # dictionary_obj = DBSession.query(dbDictionary).filter_by(client_id=args["dictionary_id"][0],
                                                               # object_id=args["dictionary_id"][1]).first()
                dictionary_obj = CACHE.get(objects =
                    {
                        dbDictionary : (args["dictionary_id"], )
                    },
                DBSession=DBSession)
                gist = DBSession.query(dbTranslationGist).\
                    filter_by(client_id=dictionary_obj.translation_gist_client_id,
                              object_id=dictionary_obj.translation_gist_object_id).first()
                task = TaskStatus(user_id, "Dialeqt dictionary conversion", gist.get_translation(locale_id), 10)
        except:
            raise ResponseError(message="wrong parameters")
        cur_args["task_key"] = task.key

        if synchronous:

          convert_f = dialeqt_convert_all
          cur_args['synchronous'] = True

        else:
          convert_f = async_convert_dictionary_new.delay

        res = convert_f(**cur_args)
        return ConvertDictionary(triumph=True)


@celery.task
def async_convert_five_tiers(
    dictionary_id,
    client_id,
    sqlalchemy_url,
    storage,
    markup_id_list,
    locale_id,
    task_key,
    cache_kwargs,
    translation_gist_id = None,
    language_id = None,
    sound_url = None,
    merge_by_meaning = True,
    additional_entries = True,
    additional_entries_all = True,
    no_sound_flag = False,
    debug_flag = False):

    convert_all(
        dictionary_id,
        client_id,
        sqlalchemy_url,
        storage,
        markup_id_list,
        locale_id,
        task_key,
        cache_kwargs,
        translation_gist_id,
        language_id,
        sound_url,
        merge_by_meaning,
        additional_entries,
        additional_entries_all,
        no_sound_flag,
        debug_flag)


class ConvertFiveTiers(graphene.Mutation):
    """
    example:
    mutation {
        create_lexicalentry(id: [949,21], perspective_id: [71,5]) {
            field {
                id
            }
            triumph
        }
    }

    (this example works)
    returns:

    {
      "create_lexicalentry": {
        "field": {
          "id": [
            949,
            21
          ]
        },
        "triumph": true
      }
    }
    """

    class Arguments:

        dictionary_id = LingvodocID()
        markup_id_list = graphene.List(LingvodocID, required = True)
        language_id = LingvodocID()

        translation_gist_id = LingvodocID()
        translation_atoms = graphene.List(ObjectVal)

        merge_by_meaning = graphene.Boolean()
        additional_entries = graphene.Boolean()
        additional_entries_all = graphene.Boolean()

        no_sound_flag = graphene.Boolean()
        debug_flag = graphene.Boolean()
        synchronous = graphene.Boolean()

    dictionary_id = LingvodocID()
    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):
        request = info.context.request
        locale_id = int(request.cookies.get('locale_id') or 1)
        client_id = request.authenticated_userid
        synchronous = args.get('synchronous', False)
        if not client_id:
            user_id = anonymous_userid(request)
        else:
            user_id = Client.get_user_by_client_id(client_id).id

        cur_args = dict()
        cur_args['client_id'] = client_id
        cur_args["dictionary_id"] = args.get("dictionary_id")
        cur_args['markup_id_list'] = args['markup_id_list']
        cur_args["locale_id"] = locale_id
        cur_args['sound_url'] = args.get('sound_url')
        cur_args["sqlalchemy_url"] = request.registry.settings["sqlalchemy.url"]
        cur_args["storage"] = request.registry.settings["storage"]
        cur_args["language_id"] = args.get('language_id')
        cur_args['merge_by_meaning'] = args.get('merge_by_meaning', True)
        cur_args['additional_entries'] = args.get('additional_entries', True)
        cur_args['additional_entries_all'] = args.get('additional_entries_all', True)
        cur_args['no_sound_flag'] = args.get('no_sound_flag', False)
        cur_args['debug_flag'] = args.get('debug_flag', False)

        if not args.get("dictionary_id"):
            if "translation_gist_id" in args:
                cur_args["gist_client_id"] = args['translation_gist_id'][0]
                cur_args["gist_object_id"] = args['translation_gist_id'][1]
                if cur_args["translation_gist_id"]:
                    gist = DBSession.query(dbTranslationGist).filter_by(client_id=cur_args["translation_gist_id"][0],
                                                                      object_id=cur_args["translation_gist_id"][1]).first()
                    task = TaskStatus(user_id, "Corpus conversion", gist.get_translation(locale_id), 10)
                else:
                    gist=None
            elif "translation_atoms" in args:
                tr_atoms = args.get("translation_atoms")
                translation_gist_id = args.get('gist_id')
                translation_gist_id = create_gists_with_atoms(tr_atoms, translation_gist_id, [client_id, None], gist_type="Dictionary")

                # See the same line higher in ConvertDictionary.

                transaction.manager.commit()

                cur_args["translation_gist_id"] = translation_gist_id
                gist = DBSession.query(dbTranslationGist).filter_by(client_id=translation_gist_id[0],
                                                                 object_id=translation_gist_id[1]).first()


                if gist:
                    task = TaskStatus(user_id, "Corpus conversion", gist.get_translation(locale_id), 10)
            else:
                raise ResponseError(message="dictionary_id or translation_atoms missed")

        else:
            # dictionary_obj = DBSession.query(dbDictionary).filter_by(client_id=args["dictionary_id"][0],
            #                                           object_id=args["dictionary_id"][1]).first()
            dictionary_obj = CACHE.get(objects =
                {
                    dbDictionary : (args["dictionary_id"], )
                },
            DBSession=DBSession)
            if not dictionary_obj:
                ResponseError(message="Dictionary not found")
            gist = DBSession.query(dbTranslationGist).filter_by(client_id=dictionary_obj.translation_gist_client_id,
                                                             object_id=dictionary_obj.translation_gist_object_id).first()


            if gist:
                    task = TaskStatus(user_id, "Corpus conversion", gist.get_translation(locale_id), 10)

            else:
                # dictionary_obj = DBSession.query(dbDictionary).filter_by(client_id=args["dictionary_id"][0],
                #                                                object_id=args["dictionary_id"][1]).first()
                dictionary_obj = CACHE.get(objects =
                    {
                        dbDictionary : (args["dictionary_id"], )
                    },
                DBSession=DBSession)

                gist = DBSession.query(dbTranslationGist).\
                    filter_by(client_id=dictionary_obj.translation_gist_client_id,
                              object_id=dictionary_obj.translation_gist_object_id).first()
                task = TaskStatus(user_id, "Corpus conversion", gist.get_translation(locale_id), 10)





        #task = TaskStatus(user_id, "Eaf dictionary conversion", gist.get_translation(locale_id), 10)
        cur_args["task_key"] = task.key
        cur_args["cache_kwargs"] = request.registry.settings["cache_kwargs"]

        if synchronous:

            convert_f = convert_all

            cur_args.setdefault('translation_gist_id')
            cur_args['synchronous'] = True

        else:

            convert_f = async_convert_five_tiers.delay

        res = convert_f(**cur_args)

        return (
            ConvertFiveTiers(
                triumph = True,
                dictionary_id = res))

