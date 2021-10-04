import logging
import os
import shutil
from pathvalidate import sanitize_filename
import graphene
from sqlalchemy import and_, BigInteger, cast, func, or_, tuple_
from lingvodoc.schema.gql_holders import (
    fetch_object,
    ObjectVal,
    Upload)
from lingvodoc.models import (
    Entity as dbEntity,
    Client,
    User as dbUser,
    DBSession,
    Dictionary as dbDictionary,
    Language as dbLanguage,
    LexicalEntry as dbLexicalEntry,
    TranslationAtom as dbTranslationAtom,
    TranslationGist as dbTranslationGist,
    Field as dbField,
    Group as dbGroup,
    BaseGroup as dbBaseGroup,
    PublishingEntity as dbPublishingEntity,
    DictionaryPerspective as dbDictionaryPerspective

)
from lingvodoc.schema.gql_holders import (
    LingvodocObjectType,
    CompositeIdHolder,
    CreatedAt,
    DeletedAt,
    Relationship,
    SelfHolder,
    FieldHolder,
    ParentLink,
    MarkedForDeletion,
    AdditionalMetadata,
    LocaleId,
    Content,
    del_object,
    ResponseError,
    client_id_check,
    Published,
    Accepted,
    LingvodocID

)
from sqlalchemy import (
    and_,
)

# from lingvodoc.views.v2.utils import (
#     create_object
# )

import base64
import hashlib

import dateutil.parser

from lingvodoc.models import DictionaryPerspective as dbPerspective
from lingvodoc.utils.creation import create_entity
from lingvodoc.utils.deletion import real_delete_entity

from lingvodoc.utils.verification import check_lingvodoc_id, check_client_id

from lingvodoc.utils.elan_functions import eaf_wordlist


# Setting up logging.
log = logging.getLogger(__name__)


def object_file_path(obj, base_path, folder_name, filename, create_dir=False):
    filename = sanitize_filename(filename)
    storage_dir = os.path.join(base_path, obj.__tablename__, folder_name, str(obj.client_id), str(obj.object_id))
    if create_dir:
        os.makedirs(storage_dir, exist_ok=True)
    storage_path = os.path.join(storage_dir, filename)
    return storage_path, filename


def create_object(content, obj, data_type, filename, folder_name, storage, json_input=True):
    import errno
    storage_path, filename = object_file_path(obj, storage["path"], folder_name, filename, True)
    directory = os.path.dirname(storage_path)  # TODO: find out, why object_file_path were not creating dir
    try:
        os.makedirs(directory)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise
    with open(str(storage_path), 'wb+') as f:
        if json_input:
            f.write(content)
        else:
            shutil.copyfileobj(content, f)

    real_location = storage_path
    url = "".join((storage["prefix"],
                   storage["static_route"],
                   obj.__tablename__,
                   '/',
                   folder_name,
                   '/',
                   str(obj.client_id), '/',
                   str(obj.object_id), '/',
                   filename))
    return real_location, url


# Read
class Entity(LingvodocObjectType):
    """
        query myQuery {
      entity(id: [66, 298] ){
				id
				created_at
			}

		}
    """
    # TODO: Accepted, entity_type
    content = graphene.String()
    data_type = graphene.String()
    dbType = dbEntity
    publishingentity = None
    is_subject_for_parsing = graphene.Boolean()

    @fetch_object('is_subject_for_parsing')
    def resolve_is_subject_for_parsing(self, info):
        supported_extensions = (".odt", ".doc", ".docx")
        if self.dbObject.content:
            extension = self.dbObject.content[self.dbObject.content.rfind('.'):]
            if extension in supported_extensions:
                return True
        return False

    class Meta:
        interfaces = (CompositeIdHolder,
                      AdditionalMetadata,
                      CreatedAt,
                      DeletedAt,
                      MarkedForDeletion,
                      Relationship,
                      SelfHolder,
                      FieldHolder,
                      ParentLink,
                      Content,
                      # TranslationHolder,
                      LocaleId,
                      Published,
                      Accepted
                      )

    @fetch_object('data_type')
    def resolve_data_type(self, info):
        return self.dbObject.field.data_type


# Create
class CreateEntity(graphene.Mutation):
    class Arguments:
        """
        input values from request. Look at "LD methods" exel table
        """
        id = LingvodocID()
        parent_id = LingvodocID(required=True)
        additional_metadata = ObjectVal()
        field_id = LingvodocID(required=True)
        self_id = LingvodocID()
        link_id = LingvodocID()
        link_perspective_id = LingvodocID()

        locale_id = graphene.Int()
        filename = graphene.String(

        )
        content = graphene.String()
        registry = ObjectVal()
        file_content = Upload()

    # Result object

    entity = graphene.Field(Entity)

    """
    example:
    curl -i -X POST  -H "Cookie: auth_tkt="
    -H "Content-Type: multipart/form-data" -F "blob=@белка.wav" -F 'query=mutation {
            create_entity(parent_id: [66, 69],  field_id:  [66,12] ) {entity{id, parent_id} triumph}}' http://localhost:6543/graphql

    or
    mutation  {
    create_entity(parent_id: [66, 69], field_id: [66, 6], content: "test") {
        entity {
            created_at,
	content
        }

    triumph
    }
    }
    """
    # Used for convenience

    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):
        id = args.get('id')
        client_id = id[0] if id else info.context["client_id"]
        object_id = id[1] if id else None
        lexical_entry_id = args.get('parent_id')
        locale_id = args.get('locale_id')
        if not locale_id:
            locale_id=2
        if not lexical_entry_id:
            raise ResponseError(message="Lexical entry not found")
        parent_client_id, parent_object_id = lexical_entry_id
        client = DBSession.query(Client).filter_by(id=client_id).first()
        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        if not user:
            raise ResponseError(message="This client id is orphaned. Try to logout and then login once more.")

        parent = DBSession.query(dbLexicalEntry).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
        if not parent:
            raise ResponseError(message="No such lexical entry in the system")

        info.context.acl_check('create', 'lexical_entries_and_entities',
            (parent.parent_client_id, parent.parent_object_id))

        additional_metadata = args.get('additional_metadata')
        upper_level = None

        field_client_id, field_object_id = args.get('field_id')
        tr_atom = DBSession.query(dbTranslationAtom).join(dbTranslationGist, and_(
            dbTranslationAtom.locale_id == 2,
            dbTranslationAtom.parent_client_id == dbTranslationGist.client_id,
            dbTranslationAtom.parent_object_id == dbTranslationGist.object_id)).join(dbField, and_(
            dbTranslationGist.client_id == dbField.data_type_translation_gist_client_id,
            dbTranslationGist.object_id == dbField.data_type_translation_gist_object_id)).filter(
            dbField.client_id == field_client_id, dbField.object_id == field_object_id).first()
        if not tr_atom:
             raise ResponseError(message="No such field in the system")
        data_type = tr_atom.content.lower()

        if args.get('self_id'):
            self_client_id, self_object_id = args.get('self_id')
            upper_level = DBSession.query(dbEntity).filter_by(client_id=self_client_id,
                                                            object_id=self_object_id).first()
            if not upper_level:
                raise ResponseError(message="No such upper level in the system")
        dbentity = dbEntity(client_id=client_id,
                        object_id=object_id,
                        field_client_id=field_client_id,
                        field_object_id=field_object_id,
                        locale_id=locale_id,
                        additional_metadata=additional_metadata,
                        parent=parent)

        # Acception permission check.
        # Admin is assumed to have all permissions.

        create_flag = (user.id == 1)

        if not create_flag:

            group = DBSession.query(dbGroup).join(dbBaseGroup).filter(
                dbBaseGroup.subject == 'lexical_entries_and_entities',
                dbGroup.subject_client_id == parent.parent_client_id,
                dbGroup.subject_object_id == parent.parent_object_id,
                dbBaseGroup.action == 'create').one()

            create_flag = (
                user.is_active and user in group.users)

        if not create_flag:

            override_group = DBSession.query(dbGroup).join(dbBaseGroup).filter(
                dbBaseGroup.subject == 'lexical_entries_and_entities',
                dbGroup.subject_override == True,
                dbBaseGroup.action == 'create').one()

            create_flag = (
                user.is_active and user in override_group.users)

        if create_flag:
            dbentity.publishingentity.accepted = True

        if upper_level:
            dbentity.upper_level = upper_level

        # If the entity is being created by the admin, we automatically publish it.

        if user.id == 1:
            dbentity.publishingentity.published = True

        filename = args.get('filename')
        real_location = None
        url = None
        if data_type == 'image' or data_type == 'sound' or 'markup' in data_type:
            blob = info.context.request.POST.pop("0")
            filename=blob.filename
            content = blob.file.read()
            #filename=
            real_location, url = create_object(content, dbentity, data_type, filename, "graphql_files", info.context.request.registry.settings["storage"])
            dbentity.content = url
            old_meta = dbentity.additional_metadata
            need_hash = True
            if old_meta:
                if old_meta.get('hash'):
                    need_hash = False
            if need_hash:
                hash = hashlib.sha224(content).hexdigest()
                hash_dict = {'hash': hash}
                if old_meta:
                    old_meta.update(hash_dict)
                else:
                    old_meta = hash_dict
                dbentity.additional_metadata = old_meta
            if 'markup' in data_type:
                name = filename.split('.')
                ext = name[len(name) - 1]
                if ext.lower() == 'textgrid':
                    data_type = 'praat markup'

                elif ext.lower() == 'eaf':
                    data_type = 'elan markup'

            dbentity.additional_metadata['data_type'] = data_type

            if 'elan' in data_type:
                bag_of_words = list(eaf_wordlist(dbentity))
                dbentity.additional_metadata['bag_of_words'] = bag_of_words
        elif data_type == 'link':
            if args.get('link_id'):
                link_client_id, link_object_id = args.get('link_id')
                dbentity.link_client_id = link_client_id
                dbentity.link_object_id = link_object_id
            else:
                raise ResponseError(
                    message="The field is of link type. You should provide client_id and object id in the content")
        elif data_type == 'directed link':
            if args.get('link_id'):
                link_client_id, link_object_id = args.get('link_id') # TODO: le check
                dbentity.link_client_id = link_client_id
                dbentity.link_object_id = link_object_id
            else:
                raise ResponseError(
                    message="The field is of link type. You should provide client_id and object id in the content")
            if args.get("link_perspective_id"):
                link_persp_client_id, link_persp_object_id = args.get('link_perspective_id')
                if not DBSession.query(dbPerspective)\
                        .filter_by(client_id=link_persp_client_id, object_id=link_persp_object_id).first():
                    raise ResponseError(message="link_perspective not found")
                dbentity.additional_metadata['link_perspective_id'] = [link_persp_client_id, link_persp_object_id]

            else:
                raise ResponseError(
                    message="The field is of link type. You should provide link_perspective_id id in the content")

        else:
            content = args.get("content")
            dbentity.content = content

            # if args.get('is_translatable', None): # TODO: fix it
            #     field.is_translatable = bool(args['is_translatable'])
        DBSession.add(dbentity)
        DBSession.flush()
        entity = Entity(id = [dbentity.client_id, dbentity.object_id])
        entity.dbObject = dbentity
        return CreateEntity(entity=entity, triumph=True)

        # if not perm_check(client_id, "field"):
        #    return ResponseError(message = "Permission Denied (Entity)")


    # Update
    """
    example #1:
    mutation  {
        update_entity(id: [ 742, 5494], additional_metadata: {hash:"1234567"} ) {
            entity {
                created_at,
                additional_metadata{
                hash
                }
            }

        status
        }
    }
    example #2:
    mutation  {
        update_entity(id: [ 742, 5494], additional_metadata: {hash:"12345"} ){status}
    }
    resolve:
    {
        "update_entity": {
            "status": true
        }
    }
    """
    # Delete
    """
    query:
    mutation  {
        delete_entity(id: [879, 8]) {
        entity{id, content, created_at}
        status
        }
    }
    response:
    {
        "delete_entity": {
            "entity": {
                "id": [
                    879,
                    8
                ],
                "content": "123",
                "created_at": "2017-06-27T09:49:24"
            },
            "status": true
        }
    }
    or
    {
        "errors": [
            "No such entity in the system"
        ]
    }
    """


class UpdateEntity(graphene.Mutation):
    """
    mutation Mu{
	update_entity_content(id:[1995,2017], published: true){
		entity{
			created_at
		}
	}
    }
    """
    class Arguments:
        id = LingvodocID(required=True)
        published = graphene.Boolean()
        accepted = graphene.Boolean()

    entity = graphene.Field(Entity)
    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):
        client_id, object_id = args.get('id')
        dbpublishingentity = DBSession.query(dbPublishingEntity).filter_by(client_id=client_id,
                                                                           object_id=object_id).first()
        if not dbpublishingentity:
            raise ResponseError(message="No such entity in the system")
        # lexical_entry = dbpublishingentity.parent.parent
        lexical_entry = DBSession.query(dbLexicalEntry).join(dbLexicalEntry.entity).join(
            dbEntity.publishingentity).filter(dbPublishingEntity.client_id == client_id,
                                              dbPublishingEntity.object_id == object_id).one()
        if not lexical_entry:
            raise ResponseError(message="No such lexical_entry in the system")
        published = args.get('published')
        accepted = args.get('accepted')
        if published is not None and not dbpublishingentity.published:
            info.context.acl_check('create', 'approve_entities',
                                   (lexical_entry.parent_client_id, lexical_entry.parent_object_id))

        if published is not None and not published and dbpublishingentity.published:
            info.context.acl_check('delete', 'approve_entities',
                                   (lexical_entry.parent_client_id, lexical_entry.parent_object_id))

        if accepted is not None and not dbpublishingentity.accepted:
            info.context.acl_check('create', 'lexical_entries_and_entities',
                                   (lexical_entry.parent_client_id, lexical_entry.parent_object_id))

        if accepted is not None and not accepted and dbpublishingentity.accepted:
            raise ResponseError(message="Not allowed action")

        if published is not None:
            dbpublishingentity.published = published
        if accepted is not None:
            dbpublishingentity.accepted = accepted

        dbentity = DBSession.query(dbEntity).filter_by(client_id=client_id, object_id=object_id).first()
        entity = Entity(id=[dbentity.client_id, dbentity.object_id])
        entity.dbObject = dbentity
        return UpdateEntity(entity=entity, triumph=True)


class ApproveAllForUser(graphene.Mutation):
    """
    mutation Mu{
	update_entity_content(id:[1995,2017], published: true){
		entity{
			created_at
		}
	}
    }
    """
    class Arguments:
        user_id = graphene.Int()
        published = graphene.Boolean()
        accepted = graphene.Boolean()
        field_ids = graphene.List(LingvodocID)
        skip_deleted_entities = graphene.Boolean()
        perspective_id = LingvodocID()
        language_id = LingvodocID()
        language_recursive = graphene.Boolean()
        language_all = graphene.Boolean()
        time_from = graphene.String()

    #entity = graphene.Field(Entity)
    triumph = graphene.Boolean()
    update_count = graphene.Int()

    @staticmethod
    def mutate(root, info, **args):

        user_id = args.get('user_id')

        published = args.get('published', False)
        accepted = args.get('accepted', False)

        field_ids = args.get('field_ids')
        skip_deleted_entities = args.get('skip_deleted_entities', True)

        perspective_id = args.get('perspective_id')

        language_id = args.get('language_id')
        language_recursive = args.get('language_recursive', False)
        language_all = args.get('language_all', False)

        time_from = args.get('time_from')

        # We have a starting time specification, trying to parse it.

        if time_from is not None:
            time_from = dateutil.parser.parse(time_from)

        log.debug(
            '\napprove_all_for_user'
            '\n  args: {0}'
            '\napprove_all_for_user'
            '\n  user_id: {1}'
            '\n  published: {2}'
            '\n  accepted: {3}'
            '\n  field_ids: {4}'
            '\n  skip_deleted_entities: {5}'
            '\n  perspective_id: {6}'
            '\n  language_id: {7}'
            '\n  language_recursive: {8}'
            '\n  language_all: {9}'
            '\n  time_from: {10}'.format(
            args,
            user_id,
            published,
            accepted,
            field_ids,
            skip_deleted_entities,
            perspective_id,
            language_id,
            language_recursive,
            language_all,
            time_from))

        request_client_id = info.context.request.authenticated_userid
        request_user = Client.get_user_by_client_id(request_client_id)

        if (not perspective_id and
            not language_id and
            not language_all):

            raise ResponseError(
                'Please specify either a perspective, a language or the flag for all languages.')

        if ((language_id or language_all) and
            request_user.id != 1):

            raise ResponseError(
                'Only administrator can perform bulk approve for languages.')

        if (user_id is None and
            request_user.id != 1):

            raise ResponseError(
                'Only administrator can perform bulk approve for all users.')

        # Entity selection condition.

        if published and accepted:

            entity_select_condition = or_(
                dbPublishingEntity.published == False,
                dbPublishingEntity.accepted == False)

        elif published:
            entity_select_condition = dbPublishingEntity.published == False

        elif accepted:
            entity_select_condition = dbPublishingEntity.accepted == False

        else:
            raise ResponseError('Neither publish nor accept action is specified.')

        # Filtering by user id, if required.

        if user_id is not None:

            client_id_query = (
                DBSession.query(Client.id).filter_by(user_id = user_id))

            entity_select_condition = (

                and_(
                    entity_select_condition,

                    func.coalesce(
                        cast(dbEntity.additional_metadata[
                            ('merge', 'original_client_id')].astext, BigInteger),
                        dbEntity.client_id)

                        .in_(client_id_query)))

        # If have any specified fields, checking their info and updating selection condition.

        list_of_fields = list()

        if field_ids:

            for field_id in field_ids:
                field = DBSession.query(dbField).filter_by(client_id=field_id[0], object_id=field_id[1]).first()
                if not field:
                    raise ResponseError("field not found")
                list_of_fields.append((field.client_id, field.object_id))

        field_id_list = tuple(list_of_fields)

        if field_ids is not None:

            entity_select_condition = and_(
                entity_select_condition,
                tuple_(dbEntity.field_client_id, dbEntity.field_object_id).in_(field_id_list))

        # Checking if we should or should not update status of deleted entities.

        if skip_deleted_entities:

            entity_select_condition = and_(
                entity_select_condition,
                dbEntity.marked_for_deletion == False)

        # Checking if we should filter entities based on creation datetime.

        if time_from:

            entity_select_condition = and_(
                entity_select_condition,
                dbEntity.created_at >= time_from)

        # Bulk approve for a single perspective.

        if perspective_id:

            given_perspective = DBSession.query(dbDictionaryPerspective).filter_by(marked_for_deletion=False,
                                                                                   client_id = perspective_id[0],
                                                                                   object_id = perspective_id[1]).first()
            if not given_perspective:
                raise ResponseError("Perspective not found")

            # Currently bulk approve can only give published/accepted status and can't remove it, so we
            # don't check for 'delete' permissions.
            #
            # We also do not check permissions if the request is from the administrator.

            if published is not None and request_user.id != 1:

                info.context.acl_check('create', 'approve_entities',
                                       (perspective_id[0], perspective_id[1]))

            if accepted is not None and request_user.id != 1:

                info.context.acl_check('create', 'lexical_entries_and_entities',
                                       (perspective_id[0], perspective_id[1]))

            # Performing bulk approve.

            update_dict = {}

            if published:
                update_dict['published'] = True

            if accepted:
                update_dict['accepted'] = True

            update_count = (

                DBSession

                    .query(
                        dbPublishingEntity)

                    .filter(
                        dbLexicalEntry.parent_client_id == perspective_id[0],
                        dbLexicalEntry.parent_object_id == perspective_id[1],
                        dbLexicalEntry.marked_for_deletion == False,
                        dbEntity.parent_client_id == dbLexicalEntry.client_id,
                        dbEntity.parent_object_id == dbLexicalEntry.object_id,
                        dbPublishingEntity.client_id == dbEntity.client_id,
                        dbPublishingEntity.object_id == dbEntity.object_id,
                        entity_select_condition)

                    .update(
                        values = update_dict,
                        synchronize_session = False))

            log.debug(
                'approve_all_for_user (perspective {0}/{1}): updated {2} entit{3}'.format(
                perspective_id[0], perspective_id[1],
                update_count,
                'y' if update_count == 1 else 'ies'))

        # Bulk approve for a language, possibly recursive, or all undeleted languages with transitively
        # undeleted parents.

        if language_id or language_all:

            if language_id:

                # A single specified language.

                marked_for_deletion = (
                        
                    DBSession
                    
                        .query(
                            dbLanguage.marked_for_deletion)
                    
                        .filter_by(
                            client_id = language_id[0],
                            object_id = language_id[1])
                        
                        .scalar())

                if marked_for_deletion is None:
                    raise ResponseError('Language {0}/{1} not found'.format(*language_id))

                elif marked_for_deletion is True:
                    raise ResponseError('Language {0}/{1} is deleted'.format(*language_id))

                language_id_list = [
                    (language_id[0], language_id[1])]

                language_str = (

                    'language {0}/{1}{2}'.format(
                        language_id[0],
                        language_id[1],
                        ', recursive' if language_recursive else ''))

            else:

                # All undeleted languages with transitively undeleted parents.

                language_id_query = (

                    DBSession

                        .query(
                            dbLanguage.client_id,
                            dbLanguage.object_id)

                        .filter_by(
                            marked_for_deletion = False,
                            parent_client_id = None,
                            parent_object_id = None))

                language_id_list = [

                    (client_id, object_id)
                    for client_id, object_id in language_id_query.all()]

                language_str = 'all languages'

            # Getting all child languages, if required.

            if language_recursive or language_all:

                parent_id_list = language_id_list

                while parent_id_list:

                    language_list = DBSession.query(dbLanguage).filter(
                        dbLanguage.marked_for_deletion == False,
                        tuple_(dbLanguage.parent_client_id, dbLanguage.parent_object_id).in_(
                            parent_id_list)).all()

                    parent_id_list = [
                        (language.client_id, language.object_id)
                        for language in language_list]

                    language_id_list.extend(parent_id_list)

            log.debug(
                '\napprove_all_for_user ({0}):'
                '\nlanguage_id_list ({1}): {2}'.format(
                language_str,
                len(language_id_list),
                language_id_list))

            # Performing bulk approve of entities for all non-deleted lexical entries from all non-deleted
            # perspectives of all non-deleted dictionaries of specified languages.

            update_dict = {}

            if published:
                update_dict['published'] = True

            if accepted:
                update_dict['accepted'] = True

            update_query = (

                dbPublishingEntity.__table__
                    .update()

                    .where(and_(
                        tuple_(dbDictionary.parent_client_id, dbDictionary.parent_object_id).in_(
                            language_id_list),
                        dbDictionary.marked_for_deletion == False,
                        dbDictionaryPerspective.parent_client_id == dbDictionary.client_id,
                        dbDictionaryPerspective.parent_object_id == dbDictionary.object_id,
                        dbDictionaryPerspective.marked_for_deletion == False,
                        dbLexicalEntry.parent_client_id == dbDictionaryPerspective.client_id,
                        dbLexicalEntry.parent_object_id == dbDictionaryPerspective.object_id,
                        dbLexicalEntry.marked_for_deletion == False,
                        dbEntity.parent_client_id == dbLexicalEntry.client_id,
                        dbEntity.parent_object_id == dbLexicalEntry.object_id,
                        dbPublishingEntity.client_id == dbEntity.client_id,
                        dbPublishingEntity.object_id == dbEntity.object_id,
                        entity_select_condition))

                    .values(**update_dict))

            update_result = update_query.execute()
            update_count = update_result.rowcount

            log.debug(
                'approve_all_for_user ({0}): updated {1} entit{2}'.format(
                language_str,
                update_count,
                'y' if update_count == 1 else 'ies'))

        DBSession.flush()
        return ApproveAllForUser(triumph = True, update_count = update_count)


class DeleteEntity(graphene.Mutation):
    class Arguments:
        id = LingvodocID(required=True)

    triumph = graphene.Boolean()
    entity = graphene.Field(Entity)

    @staticmethod
    def mutate(root, info, **args):
        client_id, object_id = args.get('id')
        dbentity = DBSession.query(dbEntity).filter_by(client_id=client_id, object_id=object_id).first()
        if not dbentity or dbentity.marked_for_deletion:
            raise ResponseError(message="No such entity in the system")
        lexical_entry = dbentity.parent
        info.context.acl_check('delete', 'lexical_entries_and_entities',
                               (lexical_entry.parent_client_id, lexical_entry.parent_object_id))

        settings = info.context["request"].registry.settings
        if 'desktop' in settings:
            real_delete_entity(dbentity, settings)
        else:
            del_object(dbentity, "delete_entity", info.context.get('client_id'))
        entity = Entity(id=[client_id, object_id])
        entity.dbObject = dbentity
        return DeleteEntity(entity=entity, triumph=True)



class BulkCreateEntity(graphene.Mutation):
    """
    mutation {
            bulk_create_entity(entities: [{id: [1199, 4], parent_id: [66, 69],  field_id:  [66, 6]}]) {
                   triumph
        }
    }
    """

    class Arguments:
        entities = graphene.List(ObjectVal)
    entities = graphene.List(Entity)
    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):
        client = DBSession.query(Client).filter_by(id=info.context["client_id"]).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           info.context["client_id"])
        entity_objects = args.get('entities')
        dbentities_list = list()
        request = info.context.request
        entities = list()
        for entity_obj in entity_objects:
            ids = entity_obj.get("id")  # TODO: id check

            if ids is None:
                ids = (info.context["client_id"], None)
            else:
                if not check_lingvodoc_id(ids):
                    raise KeyError("Wrong id")
                if not check_client_id(info.context["client_id"], ids[0]):
                    raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                                   ids[0])
            parent_id = entity_obj.get("parent_id")

            if not parent_id:
                raise ResponseError(message="Bad lexical_entry object")
            if not check_lingvodoc_id(parent_id):
                raise KeyError("Wrong parent_id")
            lexical_entry = DBSession.query(dbLexicalEntry) \
                .filter_by(client_id=parent_id[0], object_id=parent_id[1]).one()
            info.context.acl_check('create', 'lexical_entries_and_entities',
                                   (lexical_entry.parent_client_id, lexical_entry.parent_object_id))

            additional_metadata = None
            if 'additional_metadata' in entity_obj:
                additional_metadata = entity_obj["additional_metadata"]
            field_id = entity_obj.get('field_id')
            if not check_lingvodoc_id(field_id):
                raise ResponseError('no field_id provided')
            self_id = entity_obj.get("self_id")
            if self_id:
                if not check_lingvodoc_id(self_id):
                    raise KeyError("Wrong self_id")
            link_id = entity_obj.get("link_id")
            if link_id:
                if not check_lingvodoc_id(link_id):
                    raise KeyError("Wrong link_id")
            locale_id = entity_obj.get("locale_id", 2)
            filename = entity_obj.get("filename")
            content = entity_obj.get("content")
            registry = entity_obj.get("registry")

            dbentity = create_entity(ids, parent_id, additional_metadata, field_id, self_id, link_id, locale_id,
                                     filename, content, registry, request, True)

            dbentities_list.append(dbentity)

        DBSession.bulk_save_objects(dbentities_list)
        DBSession.flush()
        for dbentity in dbentities_list:
            entity =  Entity(id=[dbentity.client_id, dbentity.object_id])
            entity.dbObject = dbentity
            entities.append(entity)
        return BulkCreateEntity(entities=entities, triumph=True)


class UpdateEntityContent(graphene.Mutation):
    """


		mutation My {
	update_entity_content(id:[1907,10], content: "cat"){
		entity{
			created_at
		}
	}
}
    """

    class Arguments:
        """
        input values from request. Look at "LD methods" exel table
        """
        id = LingvodocID()
        content = graphene.String()


    entity = graphene.Field(Entity)
    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):
        # delete
        old_client_id, object_id = args.get('id')
        client_id = DBSession.query(Client).filter_by(id=info.context["client_id"]).first().id
        content = args.get("content")
        dbentity_old = DBSession.query(dbEntity).filter_by(client_id=old_client_id, object_id=object_id).first()
        if not dbentity_old or dbentity_old.marked_for_deletion:
            raise ResponseError(message="No such entity in the system")
        if dbentity_old.field.data_type != "Text":
            raise ResponseError(message="Can't edit non-text entities")
        lexical_entry = dbentity_old.parent
        info.context.acl_check('delete', 'lexical_entries_and_entities',
                               (lexical_entry.parent_client_id, lexical_entry.parent_object_id))

        settings = info.context["request"].registry.settings
        if 'desktop' in settings:
            real_delete_entity(dbentity_old, settings)
        else:
            del_object(dbentity_old, "update_entity_content",info.context.get('client_id'))
        # create
        client = DBSession.query(Client).filter_by(id=client_id).first()
        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        if not user:
            raise ResponseError(message="This client id is orphaned. Try to logout and then login once more.")

        parent = DBSession.query(dbLexicalEntry).filter_by(client_id=dbentity_old.parent_client_id,
                                                           object_id=dbentity_old.parent_object_id).first()
        if not parent:
            raise ResponseError(message="No such lexical entry in the system")

        info.context.acl_check('create', 'lexical_entries_and_entities',
                               (parent.parent_client_id, parent.parent_object_id))
        dbentity = dbEntity(client_id=client_id,
                        object_id=None,
                        field_client_id=dbentity_old.field_client_id,
                        field_object_id=dbentity_old.field_object_id,
                        locale_id=dbentity_old.locale_id,
                        additional_metadata=dbentity_old.additional_metadata,
                        parent=dbentity_old.parent)

        dbentity.publishingentity.accepted = dbentity_old.publishingentity.accepted
        dbentity.content = content
            # if args.get('is_translatable', None): # TODO: fix it
            #     field.is_translatable = bool(args['is_translatable'])
        DBSession.add(dbentity)
        DBSession.flush()
        entity = Entity(id = [dbentity.client_id, dbentity.object_id])
        entity.dbObject = dbentity
        return UpdateEntityContent(entity=entity, triumph=True)

class BulkUpdateEntityContent(graphene.Mutation):
    """
            mutation My {
        update_entity_content(ids:[[1907,10]], contents: ["cat"]){
            entity{
                created_at
            }
        }
    }
    """
    class Arguments:
        """
        input values from request. Look at "LD methods" exel table
        """
        ids = graphene.List(LingvodocID)
        contents = graphene.List(graphene.String)

    entities = graphene.List(Entity)
    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):

        # delete
        old_ids = args.get('ids')
        contents = args.get('contents')

        if len(old_ids) != len(contents):
            raise ResponseError(message="Length of contents list is not equal to length of entities list")

        client_id = DBSession.query(Client).filter_by(id=info.context["client_id"]).first().id

        dbentities_old = list()

        for old_id in old_ids:
            dbentity_old = DBSession.query(dbEntity).filter_by(client_id=old_id[0], object_id=old_id[1]).first()

            if not dbentity_old or dbentity_old.marked_for_deletion:
                raise ResponseError(message="No entity" + format(old_id) + " in the system")
            if dbentity_old.field.data_type != "Text":
                raise ResponseError(message="Can't edit non-text entity" + format(old_id))

            lexical_entry = dbentity_old.parent
            info.context.acl_check('delete', 'lexical_entries_and_entities',
                                   (lexical_entry.parent_client_id, lexical_entry.parent_object_id))

            settings = info.context["request"].registry.settings
            if 'desktop' in settings:
                real_delete_entity(dbentity_old, settings)
            else:
                del_object(dbentity_old, "update_entity_content", info.context.get('client_id'))
            dbentities_old.append(dbentity_old)

        # create
        dbentities_new = list()
        i = -1
        for content in contents:
            i += 1
            client = DBSession.query(Client).filter_by(id=client_id).first()
            user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
            if not user:
                raise ResponseError(message="This client id is orphaned. Try to logout and then login once more.")

            parent = DBSession.query(dbLexicalEntry).filter_by(client_id=dbentities_old[i].parent_client_id,
                                                               object_id=dbentities_old[i].parent_object_id).first()
            if not parent:
                raise ResponseError(message="No such lexical entry in the system")

            info.context.acl_check('create', 'lexical_entries_and_entities',
                                   (parent.parent_client_id, parent.parent_object_id))
            dbentity = dbEntity(client_id=client_id,
                                object_id=None,
                                field_client_id=dbentities_old[i].field_client_id,
                                field_object_id=dbentities_old[i].field_object_id,
                                locale_id=dbentities_old[i].locale_id,
                                additional_metadata=dbentities_old[i].additional_metadata,
                                parent=dbentities_old[i].parent)

            dbentity.publishingentity.accepted = dbentities_old[i].publishingentity.accepted
            dbentity.content = content
            # if args.get('is_translatable', None): # TODO: fix it
            #     field.is_translatable = bool(args['is_translatable'])
            dbentities_new.append(dbentity)

        DBSession.bulk_save_objects(dbentities_new)
        DBSession.flush()

        entities = list()
        for dbentity in dbentities_new:
            entity = Entity(id=[dbentity.client_id, dbentity.object_id])
            entity.dbObject = dbentity
            entities.append(entity)

        return BulkUpdateEntityContent(entities=entities, triumph=True)
