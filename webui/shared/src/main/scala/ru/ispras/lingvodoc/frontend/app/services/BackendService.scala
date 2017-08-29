
package ru.ispras.lingvodoc.frontend.app.services


import com.greencatsoft.angularjs._
import com.greencatsoft.angularjs.core.HttpPromise.promise2future
import com.greencatsoft.angularjs.core._
import org.scalajs.dom
import org.scalajs.dom.console
import org.scalajs.dom.ext.Ajax.InputData
import org.scalajs.dom.{FormData, XMLHttpRequest}
import ru.ispras.lingvodoc.frontend.api.exceptions.BackendException
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.LexicalEntriesType.LexicalEntriesType
import upickle.default._

import scala.concurrent.{Future, Promise}
import scala.scalajs.js
import scala.scalajs.js.Any.fromString
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.URIUtils._
import scala.scalajs.js.typedarray.{ArrayBuffer, Uint8Array}
import scala.scalajs.js.{Dynamic, JSON}
import scala.util.{Failure, Success, Try}


object LexicalEntriesType extends Enumeration {
  type LexicalEntriesType = Value
  val Published = Value("published")
  val All = Value("all")
  val NotAccepted = Value("not_accepted")
}


@injectable("BackendService")
class BackendService($http: HttpService, val timeout: Timeout, val exceptionHandler: ExceptionHandler) extends Service with AngularExecutionContextProvider {

  // TODO: allow user to specify different baseUrl
  private val baseUrl = ""

  private def getMethodUrl(method: String) = {
    if (baseUrl.endsWith("/"))
      baseUrl + method
    else
      baseUrl + "/" + method
  }

  private def addUrlParameter(url: String, key: String, value: String): String = {
    val param = encodeURIComponent(key) + '=' + encodeURIComponent(value)
    if (url.contains("?"))
      url + "&" + param
    else
      url + "?" + param
  }

  /**
    * Get list of perspectives for specified dictionary
    *
    * @param dictionary
    * @return
    */
  def getDictionaryPerspectives(dictionary: Dictionary, onlyPublished: Boolean): Future[Seq[Perspective]] = {
    val p = Promise[Seq[Perspective]]()
    var url = getMethodUrl("dictionary/" + encodeURIComponent(dictionary.clientId.toString) + "/" + encodeURIComponent(dictionary.objectId.toString) + "/perspectives")

    if (onlyPublished) {
      url += "?" + encodeURIComponent("published") + "=" + encodeURIComponent("true")
    }

    $http.get[js.Dynamic](url) onComplete {
      case Success(response) =>
        try {
          val perspectives = read[Seq[Perspective]](js.JSON.stringify(response))
          p.success(perspectives)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed perspectives json.", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed perspectives data. Missing some required fields.", e))
          case e: Throwable => p.failure(BackendException("getDictionaryPerspectives: unexpected exception", e))
        }

      case Failure(e) => p.failure(new BackendException("Failed to get list of perspectives for dictionary " + dictionary.translation + ": " + e.getMessage))
    }
    p.future
  }


  /**
    * Get list of dictionaries
    *
    * @param query
    * @return
    */
  def getDictionaries(query: DictionaryQuery): Future[Seq[Dictionary]] = {
    val p = Promise[Seq[Dictionary]]()

    $http.post[js.Dynamic](getMethodUrl("dictionaries"), write(query)) onComplete {
      case Success(response) =>
        try {
          val dictionaries = read[Seq[Dictionary]](js.JSON.stringify(response.dictionaries))
          p.success(dictionaries)
        } catch {
          case e: upickle.Invalid.Json => p.failure(new BackendException("Malformed dictionary json:" + e.getMessage))
          case e: upickle.Invalid.Data => p.failure(new BackendException("Malformed dictionary data. Missing some " +
            "required fields: " + e.getMessage))
        }
      case Failure(e) => p.failure(new BackendException("Failed to get list of dictionaries: " + e.getMessage))
    }
    p.future
  }

  /**
    * Get list of dictionaries
    *
    * @return
    */
  def getDictionaries(): Future[Seq[Dictionary]] = {
    val p = Promise[Seq[Dictionary]]()

    $http.post[js.Dynamic](getMethodUrl("dictionaries"), "{}") onComplete {
      case Success(response) =>
        try {
          val dictionaries = read[Seq[Dictionary]](js.JSON.stringify(response.dictionaries))
          p.success(dictionaries)
        } catch {
          case e: upickle.Invalid.Json => p.failure(new BackendException("Malformed dictionary json:" + e.getMessage))
          case e: upickle.Invalid.Data => p.failure(new BackendException("Malformed dictionary data. Missing some " +
            "required fields: " + e.getMessage))
        }
      case Failure(e) => p.failure(new BackendException("Failed to get list of dictionaries: " + e.getMessage))
    }
    p.future
  }

  /**
    * Get list of dictionaries with perspectives
    *
    * @param query
    * @return
    */
  def getDictionariesWithPerspectives(query: DictionaryQuery): Future[Seq[Dictionary]] = {
    val p = Promise[Seq[Dictionary]]()
    getDictionaries(query) onComplete {
      case Success(dictionaries) =>
        perspectives(query.publishedPerspectives) onComplete {
          case Success(perspectives) =>
            perspectives.foreach{perspective =>
              dictionaries.find(dictionary => dictionary.clientId == perspective.parentClientId && dictionary.objectId == perspective.parentObjectId) foreach { dictionary =>
                dictionary.perspectives = dictionary.perspectives :+ perspective
              }
            }
            p.success(dictionaries)
          case Failure(e) => p.failure(BackendException("Failed to get list of dictionaries with perspectives, perspectives list",e))
        }

      case Failure(e) => p.failure(BackendException("Failed to get list of dictionaries with perspectives",e))
    }
    p.future
  }

  def getDictionaryRoles(dictionaryId: CompositeId): Future[DictionaryRoles] = {
    val p = Promise[DictionaryRoles]()
    val url = getMethodUrl("dictionary/" + encodeURIComponent(dictionaryId.clientId.toString) + "/" + encodeURIComponent(dictionaryId.objectId.toString) + "/roles")

    $http.get[js.Dynamic](url) onComplete {
      case Success(response) =>
        try {
          val roles = read[DictionaryRoles](js.JSON.stringify(response))
          p.success(roles)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed dictionary roles json.", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed dictionary roles data. Missing some required fields.", e))
          case e: Throwable => p.failure(BackendException("Failed to get dictionary roles. Unexpected exception", e))
        }

      case Failure(e) => p.failure(BackendException("Failed to get dictionary roles", e))
    }
    p.future
  }


  def setDictionaryRoles(dictionaryId: CompositeId, roles: DictionaryRoles): Future[Unit] = {
    val p = Promise[Unit]()
    val url = getMethodUrl("dictionary/" + encodeURIComponent(dictionaryId.clientId.toString) + "/" + encodeURIComponent(dictionaryId.objectId.toString) + "/roles")

    $http.post[js.Dynamic](url, write(roles)) onComplete {
      case Success(response) =>
        p.success(())
      case Failure(e) => p.failure(BackendException("Failed to update dictionary roles", e))
    }

    p.future
  }



  /**
    * Get language by id
    *
    * @param compositeId
    * @return
    */
  def getLanguage(compositeId: CompositeId): Future[Language] = {
    val p = Promise[Language]()
    val url = "language/" + encodeURIComponent(compositeId.clientId.toString) + "/" + encodeURIComponent(compositeId.objectId.toString)
    $http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        try {
          p.success(read[Language](js.JSON.stringify(response)))
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed language json.", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed language data. Missing some required fields", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to get language.", e))
    }

    p.future
  }

  /**
    * Get language graph
    *
    * @return
    */
  def getLanguages: Future[Seq[Language]] = {
    val p = Promise[Seq[Language]]()
    $http.get[js.Dynamic](getMethodUrl("languages")) onComplete {
      case Success(response) =>
        try {
          val languages = read[Seq[Language]](js.JSON.stringify(response))
          p.success(languages)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed languages json.", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed languages data. Missing some required fields", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to get list of languages.", e))
    }
    p.future
  }

  /**
    * Create language
    *
    * @param names
    * @param parentLanguage
    * @return
    */
  def createLanguage(names: Seq[LocalizedString], parentLanguage: Option[Language]): Future[CompositeId] = {
    val p = Promise[CompositeId]()

    // create translation gist
    createTranslationGist("Language") onComplete {
      case Success(gistId) =>
        // wait until all atoms are created
        Future.sequence(names.map(name => createTranslationAtom(gistId, name))) onComplete {
          case Success(_) =>
            val req = parentLanguage match {
              case Some(lang) =>
                JSON.stringify(js.Dynamic.literal(
                  "translation_gist_client_id" -> gistId.clientId,
                  "translation_gist_object_id" -> gistId.objectId,
                  "parent_client_id" -> lang.clientId,
                  "parent_object_id" -> lang.objectId,
                  "locale_exist" -> false
                ))
              case None =>
                JSON.stringify(js.Dynamic.literal(
                  "translation_gist_client_id" -> gistId.clientId,
                  "translation_gist_object_id" -> gistId.objectId,
                  "locale_exist" -> false
                ))
            }

            $http.post[js.Dynamic](getMethodUrl("language"), req) onComplete {
              case Success(response) => p.success(read[CompositeId](js.JSON.stringify(response)))
              case Failure(e) => p.failure(BackendException("Failed to create language", e))
            }
          case Failure(e) => p.failure(BackendException("Failed to set translations for language", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to create translation for language", e))
    }

    p.future
  }



  def updateLanguage(languageId: CompositeId, parentLanguage: Option[Language], gistId: Option[CompositeId]): Future[Unit] = {

    val p = Promise[Unit]()
    val url = "language/" + encodeURI(languageId.clientId.toString) + "/" + encodeURI(languageId.objectId.toString)
    var req = Map[String, js.Any]()

    parentLanguage foreach { parent =>
      req += ("parent_client_id" -> parent.clientId)
      req += ("parent_object_id" -> parent.objectId)
    }

    gistId foreach { id =>
      req += ("translation_gist_client_id" -> id.clientId)
      req += ("translation_gist_object_id" -> id.objectId)
    }

    $http.put[js.Dynamic](getMethodUrl(url), req.toJSDictionary) onComplete {
      case Success(_) => p.success(())
      case Failure(e) => p.failure(BackendException("Failed to update language", e))
    }

    p.future
  }

  def getDictionary(dictionaryId: CompositeId): Future[Dictionary] = {
    val p = Promise[Dictionary]()
    val url = "dictionary/" + encodeURIComponent(dictionaryId.clientId.toString) + "/" + encodeURIComponent(dictionaryId.objectId.toString)
    $http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        try {
          p.success(read[Dictionary](js.JSON.stringify(response)))
        } catch {
          case e: upickle.Invalid.Json => p.failure(new BackendException("Malformed dictionary json:" + e.getMessage))
          case e: upickle.Invalid.Data => p.failure(new BackendException("Malformed dictionary data. Missing some " +
            "required fields: " + e.getMessage))
        }
      case Failure(e) => p.failure(new BackendException("Failed to get dictionary: " + e.getMessage))
    }
    p.future
  }


  /**
    * Update dictionary properties
    *
    * @param dictionary
    * @return
    */
  def updateDictionary(dictionary: Dictionary): Future[Unit] = {
    val p = Promise[Unit]()
    val url = "dictionary/" + encodeURIComponent(dictionary.clientId.toString) + "/" + encodeURIComponent(dictionary
      .objectId.toString)
    $http.put(getMethodUrl(url), write(dictionary)) onComplete {
      case Success(_) => p.success(Unit)
      case Failure(e) => p.failure(new BackendException("Failed to remove dictionary: " + e.getMessage))
    }
    p.future
  }

  /**
    * Remove dictionary
    *
    * @param dictionary
    * @return
    */
  def removeDictionary(dictionary: Dictionary): Future[Unit] = {
    val p = Promise[Unit]()
    val url = "dictionary/" + encodeURIComponent(dictionary.clientId.toString) + "/" + encodeURIComponent(dictionary
      .objectId.toString)
    $http.delete(getMethodUrl(url)) onComplete {
      case Success(_) => p.success(Unit)
      case Failure(e) => p.failure(new BackendException("Failed to remove dictionary: " + e.getMessage))
    }
    p.future
  }

  /**
    * Set dictionary status
    *
    * @param dictionary
    * @param status
    */
  def setDictionaryStatus(dictionary: Dictionary, status: TranslationGist): Future[Unit] = {
    val p = Promise[Unit]()
    val req = JSON.stringify(js.Dynamic.literal("state_translation_gist_client_id" -> status.clientId, "state_translation_gist_object_id" -> status.objectId))
    val url = "dictionary/" + encodeURIComponent(dictionary.clientId.toString) + "/" + encodeURIComponent(dictionary.objectId.toString) + "/state"
    $http.put(getMethodUrl(url), req) onComplete {
      case Success(_) => p.success(())
      case Failure(e) => p.failure(BackendException("Failed to update dictionary status", e))
    }
    p.future
  }

  /**
    * Get list of published dictionaries
    * XXX: Actually it returns a complete tree of languages
    *
    * @return
    */
  def getPublishedDictionaries: Future[Seq[Language]] = {

    val p = Promise[Seq[Language]]()
    val req = JSON.stringify(js.Dynamic.literal(group_by_lang = true, group_by_org = false))
    $http.post[js.Dynamic](getMethodUrl("published_dictionaries"), req) onComplete {
      case Success(response) =>
        try {
          val languages = read[Seq[Language]](js.JSON.stringify(response))
          p.success(languages)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed dictionary json", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed dictionary data. Missing some required fields", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to get list of dictionaries: ", e))
    }
    p.future
  }

  // Perspectives


  def perspectives(published: Boolean = false): Future[Seq[Perspective]] = {
    val p = Promise[Seq[Perspective]]()
    var url = "perspectives"
    if (published) {
      url = addUrlParameter(url, "published", "true")
    }

    $http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        try {
          p.success(read[Seq[Perspective]](js.JSON.stringify(response)))
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed perspectives json", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed perspectives data. Missing some " +
            "required fields: ", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to get perspective: ", e))
    }
    p.future
  }


  /**
    * Get perspective by id
    *
    * @param perspectiveId
    * @return
    */
  def getPerspective(perspectiveId: CompositeId): Future[Perspective] = {
    val p = Promise[Perspective]()
    val url = "perspective/" + encodeURIComponent(perspectiveId.clientId.toString) + "/" + encodeURIComponent(perspectiveId.objectId.toString)
    $http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        try {
          p.success(read[Perspective](js.JSON.stringify(response)))
        } catch {
          case e: upickle.Invalid.Json => p.failure(new BackendException("Malformed perspective json:" + e.getMessage))
          case e: upickle.Invalid.Data => p.failure(new BackendException("Malformed perspective data. Missing some " +
            "required fields: " + e.getMessage))
        }
      case Failure(e) => p.failure(new BackendException("Failed to get perspective: " + e.getMessage))
    }
    p.future
  }

  /**
    * Set perspective status
    *
    * @param perspective
    * @param status
    * @return
    */
  def setPerspectiveStatus(perspective: Perspective, status: TranslationGist): Future[Unit] = {
    val p = Promise[Unit]()
    val req = JSON.stringify(js.Dynamic.literal("state_translation_gist_client_id" -> status.clientId, "state_translation_gist_object_id" -> status.objectId))

    val url = "dictionary/" + encodeURIComponent(perspective.parentClientId.toString) +
      "/" + encodeURIComponent(perspective.parentObjectId.toString) +
      "/perspective/" + encodeURIComponent(perspective.clientId.toString) +
      "/" + encodeURIComponent(perspective.objectId.toString) + "/state"

    $http.put(getMethodUrl(url), req) onComplete {
      case Success(_) => p.success(())
      case Failure(e) => p.failure(new BackendException("Failed to update perspective status: " + e.getMessage))
    }
    p.future
  }

  /**
    * Remove perspective
    *
    * @param dictionary
    * @param perspective
    * @return
    */
  def removePerspective(dictionary: Dictionary, perspective: Perspective): Future[Unit] = {
    val p = Promise[Unit]()
    val url = "dictionary/" + encodeURIComponent(dictionary.clientId.toString) + "/" +
      encodeURIComponent(dictionary.objectId.toString) + "/perspective/" + encodeURIComponent(perspective.clientId
      .toString) +
      "/" + encodeURIComponent(perspective.objectId.toString)

    $http.delete(getMethodUrl(url)) onComplete {
      case Success(_) => p.success(())
      case Failure(e) => p.failure(new BackendException("Failed to remove perspective: " + e.getMessage))
    }
    p.future
  }

  def getPerspectiveRoles(dictionaryId: CompositeId, perspectiveId: CompositeId): Future[PerspectiveRoles] = {
    val p = Promise[PerspectiveRoles]()

    val url = "dictionary/" + encodeURIComponent(dictionaryId.clientId.toString) +
      "/" + encodeURIComponent(dictionaryId.objectId.toString) +
      "/perspective/" + encodeURIComponent(perspectiveId.clientId.toString) +
      "/" + encodeURIComponent(perspectiveId.objectId.toString) + "/roles"

    $http.get[js.Dynamic](url) onComplete {
      case Success(response) =>
        try {
          val roles = read[PerspectiveRoles](js.JSON.stringify(response))
          p.success(roles)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed perspective roles json.", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed perspective roles data. Missing some required fields.", e))
          case e: Throwable => p.failure(BackendException("Failed to get perspective roles. Unexpected exception", e))
        }

      case Failure(e) => p.failure(BackendException("Failed to get perspective roles", e))
    }
    p.future
  }


  def setPerspectiveRoles(dictionaryId: CompositeId, perspectiveId: CompositeId, roles: PerspectiveRoles): Future[Unit] = {
    val p = Promise[Unit]()
    val url = getMethodUrl("dictionary/" +
      encodeURIComponent(dictionaryId.clientId.toString) +
      "/" + encodeURIComponent(dictionaryId.objectId.toString) +
      "/perspective/" + encodeURIComponent(perspectiveId.clientId.toString) +
      "/" + encodeURIComponent(perspectiveId.objectId.toString) + "/roles")

    $http.post[js.Dynamic](url, write(roles)) onComplete {
      case Success(response) =>
        p.success(())
      case Failure(e) => p.failure(BackendException("Failed to update perspective roles", e))
    }

    p.future
  }




  /**
    * Update perspective
    *
    * @param dictionary
    * @param perspective
    * @return
    */
  def updatePerspective(dictionary: Dictionary, perspective: Perspective): Future[Unit] = {
    val p = Promise[Unit]()
    val url = "dictionary/" + encodeURIComponent(dictionary.clientId.toString) + "/" +
      encodeURIComponent(dictionary.objectId.toString) + "/perspective/" + encodeURIComponent(perspective.clientId
      .toString) +
      "/" + encodeURIComponent(perspective.objectId.toString)
    $http.put(getMethodUrl(url), write(perspective)) onComplete {
      case Success(_) => p.success(())
      case Failure(e) => p.failure(new BackendException("Failed to update perspective: " + e.getMessage))
    }
    p.future
  }


  def getPerspectiveMeta(dictionaryId: CompositeId, perspectiveId: CompositeId, metadata: Seq[String]): Future[MetaData] = {
    val p = Promise[MetaData]()
    val url = "dictionary/" + encodeURIComponent(dictionaryId.clientId.toString) + "/" + encodeURIComponent(dictionaryId.objectId.toString) +
      "/perspective/" + encodeURIComponent(perspectiveId.clientId.toString) + "/" + encodeURIComponent(perspectiveId.objectId.toString) + "/meta"

    $http.post[js.Dictionary[js.Any]](getMethodUrl(url), write(metadata)) onComplete {
      case Success(response) =>
        val meta = read[MetaData](JSON.stringify(response))
        p.success(meta)
      case Failure(e) => p.failure(BackendException("Failed to get perspective metadata", e))
    }
    p.future

  }

  def getPerspectiveMeta(perspective: Perspective): Future[MetaData] = {
    val dictionaryId = CompositeId(perspective.parentClientId, perspective.parentObjectId)
    val perspectiveId = CompositeId.fromObject(perspective)
    if (perspective.metadata.nonEmpty) {
      getPerspectiveMeta(dictionaryId, perspectiveId, perspective.metadata)
    } else {
      Future.successful(MetaData())
    }
  }

  def setPerspectiveMeta(dictionaryId: CompositeId, perspectiveId: CompositeId, metadata: MetaData) = {
    val p = Promise[Unit]()
    org.scalajs.dom.console.log(write(metadata))

    val url = "dictionary/" + encodeURIComponent(dictionaryId.clientId.toString) + "/" + encodeURIComponent(dictionaryId.objectId.toString) +
      "/perspective/" + encodeURIComponent(perspectiveId.clientId.toString) + "/" + encodeURIComponent(perspectiveId.objectId.toString) + "/meta"
    $http.put(getMethodUrl(url), write(metadata)) onComplete {
      case Success(_) => p.success(())
      case Failure(e) => p.failure(new BackendException("Failed to update perspective: " + e.getMessage))
    }
    p.future
  }


  def allPerspectivesMeta: Future[Seq[PerspectiveMeta]] = {
    val p = Promise[Seq[PerspectiveMeta]]()
    val url = "perspectives_meta"
    $http.get[js.Any](getMethodUrl(url)) onComplete {
      case Success(response) =>

        try {
          val metaDataList = read[Seq[PerspectiveMeta]](JSON.stringify(response))
          p.success(metaDataList)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed perspectives metadata json.", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed perspectives metadata. Missing some required fields.", e))
          case e: Throwable => p.failure(BackendException("Failed to get metadata list. Unexpected exception", e))
        }

      case Failure(e) => p.failure(BackendException("Failed to get metadata list", e))
    }
    p.future
  }



  /**
    * Get information about current user
    *
    * @return
    */
  def getCurrentUser: Future[User] = {
    val p = Promise[User]()
    $http.get[js.Object](getMethodUrl("user")) onComplete {
      case Success(js) =>
        try {
          val user = read[User](JSON.stringify(js))
          p.success(user)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed user json:", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed user data. Missing some required fields", e))
          case e: Throwable => p.failure(BackendException("Unknown exception", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to get current user", e))
    }
    p.future
  }


  def updateCurrentUser(user: User): Future[Unit] = {
    val p = Promise[Unit]()
    $http.put[js.Object](getMethodUrl("user"), write(user)) onComplete {
      case Success(js) =>
        p.success(())
      case Failure(e) => p.failure(BackendException("Failed to update current user", e))
    }
    p.future
  }

  def updatePassword(oldPassword: String, newPassword: String): Future[Unit] = {
    val p = Promise[Unit]()

    val req = js.Dynamic.literal("old_password" -> oldPassword, "new_password" -> newPassword)
    $http.put[js.Object](getMethodUrl("user"), JSON.stringify(req)) onComplete {
      case Success(js) =>
        p.success(())
      case Failure(e) => p.failure(BackendException("Failed to update user password", e))
    }
    p.future
  }

  def getUser(userId: Int): Future[User] = {
    val p = Promise[User]()
    $http.get[js.Object](getMethodUrl("user/" + encodeURIComponent(userId.toString))) onComplete {
      case Success(js) =>
        try {
          val user = read[User](JSON.stringify(js))
          p.success(user)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed user json", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed user data. Missing some " +
            "required fields", e))
          case e: Throwable => p.failure(BackendException("Unknown exception", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to get  user", e))
    }
    p.future
  }

  def getUsers: Future[Seq[UserListEntry]] = {
    val p = Promise[Seq[UserListEntry]]()
    $http.get[js.Dynamic](getMethodUrl("users")) onComplete {
      case Success(js) =>
        try {
          val user = read[Seq[UserListEntry]](JSON.stringify(js.users))
          p.success(user)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed users json", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed users data. Missing some " +
            "required fields", e))
          case e: Throwable => p.failure(BackendException("Unknown exception", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to get list of users", e))
    }
    p.future
  }


  def getField(id: CompositeId): Future[Field] = {
    val p = Promise[Field]()
    val url = "field/" + encodeURIComponent(id.clientId.toString) + "/" + encodeURIComponent(id.objectId.toString)
    $http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        try {
          val field = read[Field](js.JSON.stringify(response))
          p.success(field)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed field json", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed field data. Missing some required fields", e))
          case e: Throwable => p.failure(BackendException("Unknown exception", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to fetch perspective fields", e))
    }
    p.future
  }

  /**
    * GetPerspective fields
    *
    * @param dictionary
    * @param perspective
    * @return
    */
  def getFields(dictionary: CompositeId, perspective: CompositeId): Future[Seq[Field]] = {
    val p = Promise[Seq[Field]]()

    val url = "dictionary/" + encodeURIComponent(dictionary.clientId.toString) + "/" +
      encodeURIComponent(dictionary.objectId.toString) +
      "/perspective/" + encodeURIComponent(perspective.clientId.toString) +
      "/" + encodeURIComponent(perspective.objectId.toString) + "/fields"

    $http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        try {
          val fields = read[Seq[Field]](js.JSON.stringify(response))
          p.success(fields)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed fields json.", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed fields data. Missing some required fields", e))
          case e: Throwable => p.failure(BackendException("Unknown exception.", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to fetch perspective fields.", e))
    }
    p.future
  }

  def updateFields(dictionaryId: CompositeId, perspectiveId: CompositeId, req: Seq[js.Dynamic]): Future[Unit] = {
    val p = Promise[Unit]()
    val url = "dictionary/" + encodeURIComponent(dictionaryId.clientId.toString) + "/" + encodeURIComponent(dictionaryId
      .objectId.toString) + "/perspective/" + encodeURIComponent(perspectiveId.clientId.toString) + "/" +
      encodeURIComponent(perspectiveId
        .objectId.toString) + "/fields"
    $http.put(getMethodUrl(url), req.toJSArray) onComplete {
      case Success(_) => p.success(())
      case Failure(e) => p.failure(new BackendException("Failed to update perspective fields: " + e.getMessage))
    }
    p.future
  }

  /**
    * Get perspective with fields
    *
    * @param dictionary
    * @param perspective
    * @return
    */
  def getPerspectiveFields(dictionary: Dictionary, perspective: Perspective): Future[Perspective] = {
    val p = Promise[Perspective]()
    getFields(CompositeId.fromObject(dictionary), CompositeId.fromObject(perspective)) onComplete {
      case Success(fields) =>
        perspective.fields = fields.toJSArray
        p.success(perspective)
      case Failure(e) => p.failure(new BackendException("Failed to fetch perspective fields: " + e.getMessage))
    }
    p.future
  }

  def perspectiveSource(perspectiveId: CompositeId): Future[Seq[Source[_]]] = {
    val p = Promise[Seq[Source[_]]]()

    val url = "perspective/" + encodeURIComponent(perspectiveId.clientId.toString) +
      "/" + encodeURIComponent(perspectiveId.objectId.toString) + "/tree"

    $http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        try {

          if (response.asInstanceOf[js.Object].hasOwnProperty("error"))
            p.failure(new BackendException(
              "Error while getting perspective source:\n" + response.error))

          else p.success(read[Seq[Source[_]]](js.JSON.stringify(response)))

        } catch {
          case e: Throwable => p.failure(BackendException("Unknown exception", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to get perspective source", e))
    }
    p.future
  }

  /**
    * Get lexical entries list
    *
    * @param dictionary
    * @param perspective
    * @param action - "all", "published", etc
    * @param offset
    * @param count
    * @return
    */
  def getLexicalEntries(dictionary: CompositeId, perspective: CompositeId, action: LexicalEntriesType, offset: Int, count: Int, sortBy: Option[String] = None): Future[Seq[LexicalEntry]] = {
    val p = Promise[Seq[LexicalEntry]]()

    import LexicalEntriesType._
    val a = action match {
      case All => "all"
      case Published => "published"
      case NotAccepted => "not_accepted"
    }

    var url = "dictionary/" + encodeURIComponent(dictionary.clientId.toString) +
      "/" + encodeURIComponent(dictionary.objectId.toString) +
      "/perspective/" + encodeURIComponent(perspective.clientId.toString) +
      "/" + encodeURIComponent(perspective.objectId.toString) + "/" + a

    url = addUrlParameter(url, "start_from", offset.toString)
    url = addUrlParameter(url, "count", count.toString)

    sortBy.foreach { s =>
      val ids = s.split("_")
      if (ids.length == 2) {
        url = addUrlParameter(url, "field_client_id", ids(0))
        url = addUrlParameter(url, "field_object_id", ids(1))
      }
    }

    $http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        try {
          val entries = read[Seq[LexicalEntry]](js.JSON.stringify(response))
          p.success(entries)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed lexical entries json", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed lexical entries data. Missing some required fields", e))
          case e: Throwable => p.failure(BackendException("Unknown exception", e))

        }
      case Failure(e) => p.failure(BackendException("Failed to get lexical entries", e))
    }
    p.future
  }


  def getLexicalEntriesCount(dictionaryId: CompositeId, perspectiveId: CompositeId, action: LexicalEntriesType): Future[Int] = {
    val p = Promise[Int]()

    import LexicalEntriesType._

    val method = action match {
      case All => "all_count"
      case Published => "published_count"
      case NotAccepted => "not_accepted_count"
    }

    val url = "dictionary/" + encodeURIComponent(dictionaryId.clientId.toString) +
      "/" + encodeURIComponent(dictionaryId.objectId.toString) +
      "/perspective/" + encodeURIComponent(perspectiveId.clientId.toString) +
      "/" + encodeURIComponent(perspectiveId.objectId.toString) +
      "/" + method

    $http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        try {
          p.success(response.count.asInstanceOf[Int])
        } catch {
          case e: Throwable => p.failure(new BackendException("Unknown exception:" + e.getMessage))
        }
      case Failure(e) => p.failure(new BackendException("Failed to get published lexical entries count: " + e.getMessage))
    }
    p.future
  }



  def connectedLexicalEntries(entryId: CompositeId, fieldId: CompositeId, onlyConnected: Boolean = false, published: Boolean = false) = {
    val p = Promise[Seq[LexicalEntry]]()

    val url = s"lexical_entry/${encodeURIComponent(entryId.clientId.toString)}/${encodeURIComponent(entryId.objectId.toString)}/connected?field_client_id=${encodeURIComponent(fieldId.clientId.toString)}&field_object_id=${encodeURIComponent(fieldId.objectId.toString)}&accepted=${encodeURIComponent(onlyConnected.toString)}&published=${encodeURIComponent(published.toString)}"

    $http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        try {
          val entries = read[Seq[LexicalEntry]](js.JSON.stringify(response))
          p.success(entries)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed connected lexical entries json", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed connected lexical entries data. Missing some required fields", e))
          case e: Throwable => p.failure(new BackendException("Unknown exception:" + e.getMessage))

        }
      case Failure(e) => p.failure(BackendException("Failed to get connected lexical entries", e))
    }
    p.future
  }

  def connectLexicalEntry(dictionaryId:CompositeId, perspectiveId: CompositeId, fieldId: CompositeId, targetEntry: LexicalEntry, sourceEntry: LexicalEntry): Future[Unit] = {
    val p = Promise[Unit]()
    val url = s"dictionary/${dictionaryId.clientId}/${dictionaryId.objectId}/perspective/${perspectiveId.clientId}/${perspectiveId.objectId}/lexical_entry/connect"
    val req = js.Dynamic.literal("field_client_id" -> fieldId.clientId,
      "field_object_id" -> fieldId.objectId,
      "connections" -> js.Array(
        js.Dynamic.literal("client_id" -> targetEntry.clientId, "object_id" -> targetEntry.objectId),
        js.Dynamic.literal("client_id" -> sourceEntry.clientId, "object_id" -> sourceEntry.objectId)
      )
    )
    $http.post(getMethodUrl(url), req) onComplete {
      case Success(response) => p.success(())
      case Failure(e) => p.failure(BackendException("Failed to connect lexical entries", e))
    }
    p.future
  }

  def disconnectLexicalEntry(entry: LexicalEntry, fieldId: CompositeId): Future[Unit] = {
    val p = Promise[Unit]()

    val url = s"group_entity/${entry.clientId}/${entry.objectId}"
    val req = js.Dynamic.literal(
      "field_client_id" -> fieldId.clientId,
      "field_object_id" -> fieldId.objectId
    )

    val xhr = new dom.XMLHttpRequest()
    xhr.open("DELETE", getMethodUrl(url))
    xhr.setRequestHeader("Content-Type", "application/json;charset=UTF-8")

    xhr.onload = { (e: dom.Event) =>
      if (xhr.status == 200) {
        p.success(())
      } else {
        p.failure(new BackendException("Failed to disconnect lexical entries"))
      }
    }
    xhr.send(JSON.stringify(req))

    p.future
  }

  def removeLexicalEntry(dictionaryId: CompositeId, perspectiveId: CompositeId, entryId: CompositeId): Future[Unit] = {

    val p = Promise[Unit]()

    val url = "dictionary/" + encodeURIComponent(dictionaryId.clientId.toString) + "/" +
      encodeURIComponent(dictionaryId.objectId.toString) +
      "/perspective/" + encodeURIComponent(perspectiveId.clientId.toString) + "/" +
      encodeURIComponent(perspectiveId.objectId.toString) +
      "/lexical_entry/" + encodeURIComponent(entryId.clientId.toString) + "/" +
      encodeURIComponent(entryId.objectId.toString)

    $http.delete(getMethodUrl(url)) onComplete {
      case Success(_) => p.success(())
      case Failure(e) => p.failure(BackendException("Failed to remove entry", e))
    }
    p.future
  }


  def approveLexicalEntry(dictionaryId: CompositeId, perspectiveId: CompositeId, entryId: CompositeId): Future[Unit] = {

    val p = Promise[Unit]()

    val url = "dictionary/" + encodeURIComponent(dictionaryId.clientId.toString) + "/" +
      encodeURIComponent(dictionaryId.objectId.toString) +
      "/perspective/" + encodeURIComponent(perspectiveId.clientId.toString) + "/" +
      encodeURIComponent(perspectiveId.objectId.toString) +
      "/lexical_entry/" + encodeURIComponent(entryId.clientId.toString) + "/" +
      encodeURIComponent(entryId.objectId.toString) + "/approve"

    val xhr = new dom.XMLHttpRequest()
    xhr.open("PATCH", getMethodUrl(url))
    xhr.setRequestHeader("Content-Type", "application/json;charset=UTF-8")

    xhr.onload = { (e: dom.Event) =>
      if (xhr.status == 200) {
        p.success(())
      } else {
        p.failure(new BackendException("Failed to approve lexical entry"))
      }
    }
    xhr.send()

    p.future
  }




  def getEntity(dictionaryId: CompositeId, perspectiveId: CompositeId, entryId: CompositeId, entityId: CompositeId): Future[Entity] = {

    val p = Promise[Entity]()

    val url = "dictionary/" + encodeURIComponent(dictionaryId.clientId.toString) + "/" +
      encodeURIComponent(dictionaryId.objectId.toString) +
      "/perspective/" + encodeURIComponent(perspectiveId.clientId.toString) + "/" +
      encodeURIComponent(perspectiveId.objectId.toString) +
      "/lexical_entry/" + encodeURIComponent(entryId.clientId.toString) + "/" +
      encodeURIComponent(entryId.objectId.toString) +
      "/entity/" + encodeURIComponent(entityId.clientId.toString) + "/" +
      encodeURIComponent(entityId.objectId.toString)

    $http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) => p.success(read[Entity](js.JSON.stringify(response)))
      case Failure(e) => p.failure(BackendException("Failed to get entity", e))
    }
    p.future
  }


  def createEntity(dictionaryId: CompositeId, perspectiveId: CompositeId, entryId: CompositeId, entity: EntityData): Future[CompositeId] = {

    val p = Promise[CompositeId]()

    val url = "dictionary/" + encodeURIComponent(dictionaryId.clientId.toString) + "/" +
      encodeURIComponent(dictionaryId.objectId.toString) +
      "/perspective/" + encodeURIComponent(perspectiveId.clientId.toString) + "/" +
      encodeURIComponent(perspectiveId.objectId.toString) +
      "/lexical_entry/" + encodeURIComponent(entryId.clientId.toString) + "/" +
      encodeURIComponent(entryId.objectId.toString) + "/entity"

    $http.post[js.Dynamic](getMethodUrl(url), write(entity)) onComplete {
      case Success(response) => p.success(read[CompositeId](js.JSON.stringify(response)))
      case Failure(e) => p.failure(BackendException("Failed to create entity", e))
    }
    p.future
  }

  def removeEntity(dictionaryId: CompositeId, perspectiveId: CompositeId, entryId: CompositeId, entityId: CompositeId): Future[Unit] = {

    val p = Promise[Unit]()

    val url = "dictionary/" + encodeURIComponent(dictionaryId.clientId.toString) + "/" +
      encodeURIComponent(dictionaryId.objectId.toString) +
      "/perspective/" + encodeURIComponent(perspectiveId.clientId.toString) + "/" +
      encodeURIComponent(perspectiveId.objectId.toString) +
      "/lexical_entry/" + encodeURIComponent(entryId.clientId.toString) + "/" +
      encodeURIComponent(entryId.objectId.toString) + "/entity/" +
      encodeURIComponent(entityId.clientId.toString) + "/" +
      encodeURIComponent(entityId.objectId.toString)

    $http.delete(getMethodUrl(url)) onComplete {
      case Success(_) => p.success(())
      case Failure(e) => p.failure(BackendException("Failed to remove entity", e))
    }
    p.future
  }

  def changedApproval(dictionaryId: CompositeId, perspectiveId: CompositeId, entryId: CompositeId, entityIds: Seq[CompositeId], approve: Boolean): Future[Unit] = {

    val p = Promise[Unit]()

    val method = if (approve) "PATCH" else "DELETE"

    val url = "dictionary/" + encodeURIComponent(dictionaryId.clientId.toString) + "/" +
          encodeURIComponent(dictionaryId.objectId.toString) +
          "/perspective/" + encodeURIComponent(perspectiveId.clientId.toString) + "/" +
          encodeURIComponent(perspectiveId.objectId.toString) + "/approve"

    val req = entityIds.map(id => js.Dynamic.literal("client_id" -> id.clientId, "object_id" -> id.objectId)).toJSArray

    val xhr = new dom.XMLHttpRequest()
    xhr.open(method, getMethodUrl(url))
    xhr.setRequestHeader("Content-Type", "application/json;charset=UTF-8")

    xhr.onload = { (e: dom.Event) =>
      if (xhr.status == 200) {
        p.success(())
      } else {
        p.failure(new BackendException("Failed to change approval status"))
      }
    }
    xhr.send(JSON.stringify(req))

    p.future
  }

  def approveAll(dictionaryId: CompositeId, perspectiveId: CompositeId): Future[Unit] = {

    val p = Promise[Unit]()
    val url = "dictionary/" + encodeURIComponent(dictionaryId.clientId.toString) + "/" +
      encodeURIComponent(dictionaryId.objectId.toString) +
      "/perspective/" + encodeURIComponent(perspectiveId.clientId.toString) + "/" +
      encodeURIComponent(perspectiveId.objectId.toString) + "/approve_all"

    val xhr = new dom.XMLHttpRequest()
    xhr.open("PATCH", getMethodUrl(url))
    xhr.setRequestHeader("Content-Type", "application/json;charset=UTF-8")

    xhr.onload = { (e: dom.Event) =>
      if (xhr.status == 200) {
        p.success(())
      } else {
        p.failure(new BackendException("Failed to approve all entities"))
      }
    }
    xhr.send()

    p.future
  }



  def acceptEntities(dictionaryId: CompositeId, perspectiveId: CompositeId, ids: Seq[CompositeId]): Future[Unit] = {
    val p = Promise[Unit]()

    val url = "dictionary/" + encodeURIComponent(dictionaryId.clientId.toString) + "/" +
      encodeURIComponent(dictionaryId.objectId.toString) +
      "/perspective/" + encodeURIComponent(perspectiveId.clientId.toString) + "/" +
      encodeURIComponent(perspectiveId.objectId.toString) + "/accept"


    val xhr = new dom.XMLHttpRequest()
    xhr.open("PATCH", getMethodUrl(url))
    xhr.setRequestHeader("Content-Type", "application/json;charset=UTF-8")

    xhr.onload = { (e: dom.Event) =>
      if (xhr.status == 200) {
        p.success(())
      } else {
        p.failure(new BackendException("Failed to changed approval status entities"))
      }
    }
    xhr.send(write(ids))

    p.future
  }



  /**
    * Get list of dictionaries
    *
    * @param clientID client's id
    * @param objectID object's id
    * @return sound markup in ELAN format
    */
  def getSoundMarkup(clientID: Int, objectID: Int): Future[String] = {
    val req = JSON.stringify(js.Dynamic.literal(client_id = clientID, object_id = objectID))
    val p = Promise[String]()

    $http.post[js.Dynamic](getMethodUrl("convert/markup"), req) onComplete {
      case Success(response) =>
        try {
          val markup = read[String](js.JSON.stringify(response.content))
          p.success(markup)
        } catch {
          case e: upickle.Invalid.Json => p.failure(new BackendException("Malformed markup json:" + e.getMessage))
          case e: upickle.Invalid.Data => p.failure(new BackendException("Malformed markup data. Missing some " +
            "required fields: " + e.getMessage))
        }
      case Failure(e) => p.failure(new BackendException("Failed to get sound markup: " + e.getMessage))
    }
    p.future
  }

  /**
    * Log in
    *
    * @param username
    * @param password
    * @return
    */
  def login(username: String, password: String): Future[Int] = {
    val promise = Promise[Int]()
    val req = JSON.stringify(js.Dynamic.literal(login = username, password = password))
    $http.post[js.Dynamic](getMethodUrl("signin"), req) onComplete {
      case Success(response) =>
        try {
          val clientId = response.client_id.asInstanceOf[Int]
          promise.success(clientId)
        } catch {
          case e: Throwable => promise.failure(BackendException("Unknown exception", e))
        }
      case Failure(e) => promise.failure(BackendException("Login failure", e))
    }
    promise.future
  }


  def desktop_login(username: String, password: String): Future[Int] = {
    val p = Promise[Int]()
    val req = js.Dynamic.literal(login = username, password = password)
    val xhr = new dom.XMLHttpRequest()
    xhr.open("POST", getMethodUrl("signin/desktop"))
    xhr.setRequestHeader("Content-Type", "application/json;charset=UTF-8")
    xhr.onload = { (e: dom.raw.Event) =>
      if (xhr.status == 200) {
        try {
          val response: Dynamic = JSON.parse(xhr.responseText)
          val clientId = response.client_id.asInstanceOf[Int]
          p.success(clientId)
        } catch {
          case e: Throwable =>
            p.failure(BackendException("Failed to login", e))
        }
      } else {

        try {
          val response: Dynamic = JSON.parse(xhr.responseText)
          if (!js.isUndefined(response.error)) {
            val errorMessage = "Failed to login: " + response.error.asInstanceOf[String]
            p.failure(new BackendException(errorMessage))
          } else {
            p.failure(new BackendException("Failed to login"))
          }
        } catch {
          case e: Throwable => p.failure(BackendException("Failed to login, unexpected exception", e))
        }
      }
    }
    xhr.send(JSON.stringify(req))
    p.future
  }


  /**
    * Logout user
    *
    * @return
    */
  def logout(): Future[Unit] = {
    val p = Promise[Unit]()
    $http.get[js.Dynamic](getMethodUrl("logout")) onComplete {
      case Success(response) => p.success(())
      case Failure(e) => p.failure(BackendException("Failed to logout", e))
    }
    p.future
  }

  /**
    * Sign up
    *
    * @param login
    * @param name
    * @param password
    * @param email
    * @param day
    * @param month
    * @param year
    * @return
    */
  def signup(login: String, name: String, password: String, email: String, day: Int, month: Int, year: Int): Future[Unit] = {
    val p = Promise[Unit]()
    val req = JSON.stringify(js.Dynamic.literal(login = login, name = name, email = email, password = password, day = day, month = month, year = year))
    $http.post[js.Dynamic](getMethodUrl("signup"), req) onComplete {
      case Success(response) => p.success(())
      case Failure(e) => p.failure(BackendException("Failed to sign up", e))
    }
    p.future
  }

  /**
    * Get list of all statuses
    *
    * @return
    */
  def allStatuses() = {
    val p = Promise[Seq[TranslationGist]]()

    $http.get[js.Dynamic](getMethodUrl("all_statuses")) onComplete {
      case Success(response) =>
        val statuses = read[Seq[TranslationGist]](js.JSON.stringify(response))
        p.success(statuses)
      case Failure(e) => p.failure(BackendException("Failed get list of status values.", e))
    }
    p.future
  }


  def allTranslationGists(): Future[Seq[TranslationGist]] = {
    val p = Promise[Seq[TranslationGist]]()
    $http.get[js.Dynamic]("all_translationgists") onComplete {
      case Success(response) =>
        p.success(read[Seq[TranslationGist]](js.JSON.stringify(response)))
      case Failure(e) => p.failure(BackendException("Failed to get all gists", e))
    }
    p.future
  }


  /**
    * Gets translation atom by id
    *
    * @param clientId
    * @param objectId
    * @return
    */
  @Deprecated
  def translationAtom(clientId: Int, objectId: Int): Future[TranslationAtom] = {
    val p = Promise[TranslationAtom]()
    val url = "translationatom/" + encodeURIComponent(clientId.toString) + "/" + encodeURIComponent(objectId.toString)
    $http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        val atom = read[TranslationAtom](js.JSON.stringify(response))
        p.success(atom)
      case Failure(e) => p.failure(BackendException("Failed to get translation atom", e))
    }
    p.future
  }

  def translationAtom(atomId: CompositeId): Future[TranslationAtom] = {
    val p = Promise[TranslationAtom]()
    val url = "translationatom/" + encodeURIComponent(atomId.clientId.toString) + "/" + encodeURIComponent(atomId.objectId.toString)
    $http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        val atom = read[TranslationAtom](js.JSON.stringify(response))
        p.success(atom)
      case Failure(e) => p.failure(BackendException("Failed to get translation atom", e))
    }
    p.future
  }

  /**
    * Creates translation atom
    *
    * @param gistId
    * @return
    */
  def createTranslationAtom(gistId: CompositeId, string: LocalizedString): Future[CompositeId] = {
    val p = Promise[CompositeId]()
    val req = JSON.stringify(js.Dynamic.literal("parent_client_id" -> gistId.clientId,
      "parent_object_id" -> gistId.objectId,
      "locale_id" -> string.localeId,
      "content" -> string.str
    ))

    $http.post[js.Dynamic](getMethodUrl("translationatom"), req) onComplete {
      case Success(response) =>
        try {
          val gistId = read[CompositeId](js.JSON.stringify(response))
          p.success(gistId)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Creation of translation atom failed. Malformed json", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Creation of translation atom failed. Malformed data", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to create translation atom", e))
    }
    p.future
  }

  def updateTranslationAtom(translationAtom: TranslationAtom): Future[Unit] = {
    val p = Promise[Unit]()

    val url = "translationatom/" + encodeURIComponent(translationAtom.clientId.toString) + "/" + encodeURIComponent(translationAtom.objectId.toString)

    val req = JSON.stringify(js.Dynamic.literal(
      "content" -> translationAtom.content
    ))

    $http.put[js.Dynamic](getMethodUrl(url), req) onComplete {
      case Success(response) => p.success(())
      case Failure(e) => p.failure(BackendException("Failed to update translation atom", e))
    }
    p.future
  }

  @Deprecated
  def translationGist(clientId: Int, objectId: Int): Future[TranslationGist] = {
    val p = Promise[TranslationGist]()
    val url = "translationgist/" + encodeURIComponent(clientId.toString) + "/" + encodeURIComponent(objectId.toString)
    $http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        try {
          val gist = read[TranslationGist](js.JSON.stringify(response))
          p.success(gist)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed translation gist json", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed translation gist data. Missing some required fields", e))
          case e: Throwable => p.failure(BackendException("Unexpected exception", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to get translation gist", e))
    }
    p.future
  }

  def translationGist(gistId: CompositeId): Future[TranslationGist] = {
    val p = Promise[TranslationGist]()
    val url = "translationgist/" + encodeURIComponent(gistId.clientId.toString) + "/" + encodeURIComponent(gistId.objectId.toString)
    $http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        try {
          val gist = read[TranslationGist](js.JSON.stringify(response))
          p.success(gist)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed translation gist json", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed translation gist data. Missing some required fields", e))
          case e: Throwable => p.failure(BackendException("Unexpected exception", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to get translation gist", e))
    }
    p.future
  }



  def createTranslationGist(gistType: String): Future[CompositeId] = {
    val p = Promise[CompositeId]()
    val req = JSON.stringify(js.Dynamic.literal("type" -> gistType))
    $http.post[js.Dynamic](getMethodUrl("translationgist"), req) onComplete {
      case Success(response) =>
        try {
          val gistId = read[CompositeId](js.JSON.stringify(response))
          p.success(gistId)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Creation of translation gist failed. Malformed json", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Creation of translation gist failed. Malformed data", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to create translation gist", e))
    }
    p.future
  }

  def createField(translationGist: CompositeId, dataTypeGist: CompositeId): Future[CompositeId] = {
    val p = Promise[CompositeId]()

    val req = JSON.stringify(
      js.Dynamic.literal("translation_gist_client_id" -> translationGist.clientId,
        "translation_gist_object_id" -> translationGist.objectId,
        "data_type_translation_gist_client_id" -> dataTypeGist.clientId,
        "data_type_translation_gist_object_id" -> dataTypeGist.objectId)
    )

    $http.post[js.Dynamic](getMethodUrl("field"), req) onComplete {
      case Success(response) =>
        try {
          val gistId = read[CompositeId](js.JSON.stringify(response))
          p.success(gistId)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Creation of field failed. Malformed json", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Creation of field failed. Malformed data", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to create field", e))
    }
    p.future
  }

  def fields(): Future[Seq[Field]] = {
    val p = Promise[Seq[Field]]()

    $http.get[js.Dynamic](getMethodUrl("fields")) onComplete {
      case Success(response) =>
        try {
          val fields = read[Seq[Field]](js.JSON.stringify(response))
          p.success(fields)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed fields json", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed fields data", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to get list of fields", e))
    }
    p.future
  }

  def dataTypes(): Future[Seq[TranslationGist]] = {
    val p = Promise[Seq[TranslationGist]]()

    $http.get[js.Dynamic](getMethodUrl("all_data_types")) onComplete {
      case Success(response) =>
        try {
          val fields = read[Seq[TranslationGist]](js.JSON.stringify(response))
          p.success(fields)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed data types json", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed data types data", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to get list of data types", e))
    }
    p.future
  }

  def createDictionary(names: Seq[LocalizedString], language: Language, isCorpora: Boolean = false): Future[CompositeId] = {
    val p = Promise[CompositeId]()
    createTranslationGist("Dictionary") map {
      gistId =>
        Future.sequence(names.filter(_.str.nonEmpty).map(name => createTranslationAtom(gistId, name))) map {
          _ =>

            val req = if (!isCorpora) {
              js.Dynamic.literal("translation_gist_client_id" -> gistId.clientId,
                "translation_gist_object_id" -> gistId.objectId,
                "parent_client_id" -> language.clientId,
                "parent_object_id" -> language.objectId)
            } else {
              js.Dynamic.literal("translation_gist_client_id" -> gistId.clientId,
                "translation_gist_object_id" -> gistId.objectId,
                "parent_client_id" -> language.clientId,
                "parent_object_id" -> language.objectId,
                "category" -> "lingvodoc.ispras.ru/corpora")
            }

            $http.post[js.Dynamic]("dictionary", req) onComplete {
              case Success(response) =>
                try {
                  val id = read[CompositeId](js.JSON.stringify(response))
                  p.success(id)
                } catch {
                  case e: upickle.Invalid.Json => p.failure(BackendException("Failed to create dictionary.", e))
                  case e: upickle.Invalid.Data => p.failure(BackendException("Failed to create dictionary.", e))
                }
              case Failure(e) => p.failure(BackendException("Failed to create dictionary", e))
            }
        }
    }

    p.future
  }


  def createDictionary(languageId: CompositeId, nameId: CompositeId): Future[CompositeId] = {
    val p = Promise[CompositeId]()

    val req = js.Dynamic.literal("translation_gist_client_id" -> nameId.clientId,
      "translation_gist_object_id" -> nameId.objectId,
      "parent_client_id" -> languageId.clientId,
      "parent_object_id" -> languageId.objectId)

    $http.post[js.Dynamic]("dictionary", req) onComplete {
      case Success(response) =>
        try {
          val id = read[CompositeId](js.JSON.stringify(response))
          p.success(id)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Failed to create dictionary.", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Failed to create dictionary.", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to create dictionary", e))
    }
    p.future
  }



  def createPerspectives(dictionaryId: CompositeId, req: Seq[js.Dynamic]): Future[Seq[CompositeId]] = {
    val p = Promise[Seq[CompositeId]]()
    val url = "dictionary/" + encodeURIComponent(dictionaryId.clientId.toString) + "/" + encodeURIComponent(dictionaryId.objectId.toString) + "/complex_create"
    $http.post[js.Dynamic](getMethodUrl(url), req.toJSArray) onComplete {
      case Success(response) =>
        try {
          val id = read[Seq[CompositeId]](js.JSON.stringify(response))
          p.success(id)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Failed to create perspective.", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Failed to create perspective.", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to create perspective", e))
    }
    p.future
  }


  /**
    * Create a new lexical entry
    *
    * @param dictionaryId
    * @param perspectiveId
    * @return
    */
  def createLexicalEntry(dictionaryId: CompositeId, perspectiveId: CompositeId): Future[CompositeId] = {
    val p = Promise[CompositeId]()

    val url = "dictionary/" + encodeURIComponent(dictionaryId.clientId.toString) + "/" +
      encodeURIComponent(dictionaryId.objectId.toString) + "/perspective/" +
      encodeURIComponent(perspectiveId.clientId.toString) + "/" +
      encodeURIComponent(perspectiveId.objectId.toString) + "/lexical_entry"

    $http.post[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        try {
          val id = read[CompositeId](js.JSON.stringify(response))
          p.success(id)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Failed to create lexical entry.", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Failed to create lexical entry.", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to create lexical entry", e))
    }

    p.future
  }

  /**
    * Get lexical entry by id
    *
    * @param dictionaryId
    * @param perspectiveId
    * @param entryId
    * @return
    */
  def getLexicalEntry(dictionaryId: CompositeId, perspectiveId: CompositeId, entryId: CompositeId): Future[LexicalEntry] = {
    val p = Promise[LexicalEntry]()

    val url = "dictionary/" + encodeURIComponent(dictionaryId.clientId.toString) + "/" +
      encodeURIComponent(dictionaryId.objectId.toString) + "/perspective/" +
      encodeURIComponent(perspectiveId.clientId.toString) + "/" +
      encodeURIComponent(perspectiveId.objectId.toString) + "/lexical_entry/" +
      encodeURIComponent(entryId.clientId.toString) + "/" +
      encodeURIComponent(entryId.objectId.toString)

    $http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        try {
          val entry = read[LexicalEntry](js.JSON.stringify(response))
          p.success(entry)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Failed to get lexical entry.", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Failed to get lexical entry.", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to get lexical entry", e))
    }

    p.future
  }

  def search(query: String, perspectiveId: Option[CompositeId], tagsOnly: Boolean, fieldId: Option[CompositeId] = None, published: Option[Boolean] = None): Future[Seq[SearchResult]] = {
    val p = Promise[Seq[SearchResult]]()

    var url = "basic_search?searchstring=" + encodeURIComponent(query) + "&can_add_tags=" + encodeURIComponent(tagsOnly.toString)

    perspectiveId match {
      case Some(id) => url = url + "&perspective_client_id=" + encodeURIComponent(id.clientId.toString) + "&perspective_object_id=" + encodeURIComponent(id.objectId.toString)
      case None =>
    }

    fieldId foreach { id =>
      url = url + "&field_client_id=" + encodeURIComponent(id.clientId.toString) + "&field_object_id=" + encodeURIComponent(id.objectId.toString)
    }

    published foreach { p =>
      url = url + "&published=" + encodeURIComponent(p.toString)
    }

    $http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        try {
          val entries = read[Seq[SearchResult]](js.JSON.stringify(response))
          p.success(entries)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Search failed.", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Search failed.", e))
        }
      case Failure(e) => p.failure(BackendException("Search failed", e))
    }
    p.future
  }


  def advanced_search(query: AdvancedSearchQuery): Future[Seq[LexicalEntry]] = {
    val p = Promise[Seq[LexicalEntry]]()

    var url = "advanced_search"

    $http.post[js.Dynamic](getMethodUrl(url), write(query)) onComplete {
      case Success(response) =>
        try {
          val entries = read[Seq[LexicalEntry]](js.JSON.stringify(response))
          p.success(entries)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Search failed.", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Search failed.", e))
        }
      case Failure(e) => p.failure(BackendException("Search failed", e))
    }
    p.future
  }


  def getLocales(): Future[Seq[Locale]] = {
    val p = Promise[Seq[Locale]]()
    $http.get[js.Dynamic](getMethodUrl("all_locales")) onComplete {
      case Success(response) =>
        try {
          val locales = read[Seq[Locale]](js.JSON.stringify(response))
          p.success(locales)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Failed to get list of locales", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Failed to get list of locales", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to get list of locales", e))
    }
    p.future
  }

  def userFiles: Future[Seq[File]] = {
    val p = Promise[Seq[File]]()

    $http.get[js.Dynamic](getMethodUrl("blobs")) onComplete {
      case Success(response) =>
        try {
          val blobs = read[Seq[File]](js.JSON.stringify(response))
          p.success(blobs)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Failed to get list of user files.", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Failed to get list of user files.", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to get list of user files.", e))
    }

    p.future
  }


  def sociolinguisticsBlobs: Future[Seq[File]] = {
    val p = Promise[Seq[File]]()
    $http.get[js.Dynamic](getMethodUrl("blobs?is_global=true&data_type=sociolinguistics")) onComplete {
      case Success(response) =>
        try {
          val blobs = read[Seq[File]](js.JSON.stringify(response))
          p.success(blobs)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Failed to get list of sociolinguistics files.", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Failed to get list of sociolinguistics files.", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to get list of user files.", e))
    }
    p.future
  }


  def uploadFile(formData: FormData): Future[CompositeId] = {
    val p = Promise[CompositeId]()
    val inputData = InputData.formdata2ajax(formData)
    dom.ext.Ajax.post(getMethodUrl("blob"), inputData) onComplete {
      case Success(response) =>
        val id = read[CompositeId](response.responseText)
        p.success(id)
      case Failure(e) => p.failure(BackendException("Failed to upload", e))
    }
    p.future
  }

  def uploadFile(formData: FormData, progressEventHandler: (Int, Int) => Unit): Future[CompositeId] = {
    val p = Promise[CompositeId]()

    val xhr = new dom.XMLHttpRequest()
    xhr.open("POST", getMethodUrl("blob"))

    // executed once upload is complete
    xhr.onload = { (e: dom.Event) =>
      if (xhr.status == 200) {
        val id = read[CompositeId](xhr.responseText)
        p.success(id)
      } else {

        p.failure(new BackendException("Failed to upload file: " + xhr.statusText + xhr.responseText))
      }
    }

    // track upload progress
    xhr.upload.onprogress = (e: dom.ProgressEvent) => {
      progressEventHandler(e.loaded, e.total)
    }

    xhr.send(formData)
    p.future
  }


  def blob(blobId: CompositeId): Future[File] = {
    val p = Promise[File]()

    val url = "blobs/" + encodeURIComponent(blobId.clientId.toString) +
      "/" + encodeURIComponent(blobId.objectId.toString)

    $http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        try {
          p.success(read[File](js.JSON.stringify(response)))
        } catch {
          case e: Throwable => p.failure(BackendException("Unknown exception", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to get blob", e))
    }
    p.future
  }

  def removeBlob(blobId: CompositeId): Future[Unit] = {
    val p = Promise[Unit]()

    val url = "blobs/" + encodeURIComponent(blobId.clientId.toString) +
      "/" + encodeURIComponent(blobId.objectId.toString)

    $http.delete[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        try {
          p.success(())
        } catch {
          case e: Throwable => p.failure(BackendException("Unknown exception", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to remove blob", e))
    }
    p.future
  }


  def convertMarkup(entityId: CompositeId): Future[String] = {
    val p = Promise[String]()

    val req = js.Dynamic.literal("client_id" -> entityId.clientId, "object_id" -> entityId.objectId)
    val xhr = new dom.XMLHttpRequest()
    xhr.open("POST", getMethodUrl("convert/markup"))
    xhr.setRequestHeader("Content-Type", "application/json;charset=UTF-8")

    xhr.onload = { (e: dom.Event) =>
      if (xhr.status == 200) {
        p.success(xhr.responseText)
      } else {
        p.failure(new BackendException("Failed to convert markup"))
      }
    }
    xhr.send(JSON.stringify(req))
    p.future
  }



  def serviceTranslation(search: String): Future[TranslationGist] = {
    val p = Promise[TranslationGist]()

    val req = js.Dynamic.literal("searchstring" -> search)
    val xhr = new dom.XMLHttpRequest()
    xhr.open("POST", getMethodUrl("translation_service_search"))
    xhr.setRequestHeader("Content-Type", "application/json;charset=UTF-8")

    xhr.onload = { (e: dom.Event) =>
      if (xhr.status == 200) {
        val gist = read[TranslationGist](xhr.responseText)
        p.success(gist)
      } else {
        p.failure(new BackendException("Failed to changed approval status entities"))
      }
    }
    xhr.send(JSON.stringify(req))
    p.future
  }

  def getDialeqtDictionaryName(blobId: CompositeId): Future[String] = {

    val url = s"convert_dictionary_dialeqt_get_info/${encodeURIComponent(blobId.clientId.toString)}/${encodeURIComponent(blobId.objectId.toString)}"

    val p = Promise[String]()
    $http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        p.success(response.dictionary_name.asInstanceOf[String])
      case Failure(e) =>
        p.failure(BackendException("Failed to get Dialeqt dictionary name", e))
    }
    p.future
  }

  def convertDialeqtDictionary(languageId: CompositeId, fileId: CompositeId, translations: CompositeId): Future[Unit] = {
    val p = Promise[Unit]()

    val req = js.Dynamic.literal("language_client_id" -> languageId.clientId,
      "language_object_id" -> languageId.objectId,
      "blob_client_id" -> fileId.clientId,
      "blob_object_id" -> fileId.objectId,
      "gist_client_id" -> translations.clientId,
      "gist_object_id" -> translations.objectId
    )

    $http.post(getMethodUrl("convert_dictionary_dialeqt"), req) onComplete {
      case Success(response) => p.success(())
      case Failure(e) => p.failure(BackendException("Failed to convert dialeqt dictionary.", e))
    }
    p.future
  }

  def convertDialeqtDictionary(fileId: CompositeId, dictionaryId: CompositeId): Future[Unit] = {
    val p = Promise[Unit]()

    val req = js.Dynamic.literal(
      "blob_client_id" -> fileId.clientId,
      "blob_object_id" -> fileId.objectId,
      "dictionary_client_id" -> dictionaryId.clientId,
      "dictionary_object_id" -> dictionaryId.objectId
    )

    $http.post(getMethodUrl("convert_dictionary_dialeqt"), req) onComplete {
      case Success(response) => p.success(())
      case Failure(e) => p.failure(BackendException("Failed to convert dialeqt dictionary.", e))
    }
    p.future
  }



  def corporaFields(): Future[Seq[Field]] = {
    val p = Promise[Seq[Field]]()

    $http.get[js.Dynamic](getMethodUrl("corpora_fields")) onComplete {
      case Success(response) =>
        try {
          val fields = read[Seq[Field]](js.JSON.stringify(response))
          p.success(fields)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed fields json.", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed fields data. Missing some required fields", e))
          case e: Throwable => p.failure(BackendException("Unknown exception.", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to fetch perspective fields.", e))
    }
    p.future
  }

  def getAvailableDesktopDictionaries: Future[Seq[Language]] = {
    val p = Promise[Seq[Language]]()
    val req = JSON.stringify(js.Dynamic.literal(group_by_lang = true, group_by_org = false))
    $http.post[js.Dynamic](getMethodUrl("published_dictionaries/desktop"), req) onComplete {
      case Success(response) =>
        try {
          val languages = read[Seq[Language]](js.JSON.stringify(response))
          p.success(languages)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed dictionary json", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed dictionary data. Missing some required fields", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to get list of dictionaries: ", e))
    }
    p.future
  }

  def getAvailableDesktopPerspectives(published: Boolean = false): Future[Seq[Perspective]] = {
    val p = Promise[Seq[Perspective]]()
    var url = "perspectives/desktop"
    if (published) {
      url = addUrlParameter(url, "published", "true")
    }
    $http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        try {
          p.success(read[Seq[Perspective]](js.JSON.stringify(response)))
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed perspectives json", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed perspectives data. Missing some " +
            "required fields: ", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to get perspective: ", e))
    }
    p.future
  }

  def syncDownloadDictionary(dictionaryId: CompositeId): Future[Unit] = {
    val p = Promise[Unit]()
    val req = write[CompositeId](dictionaryId)
    $http.post[js.Dynamic]("sync/download", req) onComplete {
      case Success(response) =>
          p.success(())
      case Failure(e) => p.failure(BackendException("Failed to download dictionary", e))
    }
    p.future
  }

  def syncAll(): Future[Unit] = {
    val p = Promise[Unit]()
    $http.post[js.Dynamic]("sync/all") onComplete {
      case Success(response) =>
        p.success(())
      case Failure(e) => p.failure(BackendException("Failed to synchronize", e))
    }
    p.future
  }

  def desktopPerspectivePermissions(): Future[Map[Int, Map[Int, PerspectivePermissions]]] = {
    import upickle.Js
    implicit def MapWithStringKeysR[V: Reader] = Reader[Map[Int, V]] {
      case json: Js.Obj => json.value.map(x => (x._1.toInt, readJs[V](x._2))).toMap
    }
    val p = Promise[Map[Int, Map[Int, PerspectivePermissions]]]()
    $http.get[js.Dynamic]("permissions/perspectives/desktop") onComplete {
      case Success(response) =>
        val permissions = read[Map[Int, Map[Int, PerspectivePermissions]]](js.JSON.stringify(response)).map { e =>
          (e._1.toInt, e._2.map { e1 =>
            (e1._1.toInt, e1._2)
          })
        }
        p.success(permissions)
      case Failure(e) => p.failure(BackendException("Failed to get permissions", e))
    }
    p.future
  }

  def sociolinguisticsQuestions(): Future[Seq[String]] = {
    val p = Promise[Seq[String]]()
    $http.get[js.Dynamic]("sociolinguistics/questions") onComplete {
      case Success(response) =>
        p.success(read[Seq[String]](js.JSON.stringify(response)))
      case Failure(e) => p.failure(BackendException("Failed to get sociolinguistics questions", e))
    }
    p.future
  }

  def sociolinguisticsAnswers(): Future[Seq[String]] = {
    val p = Promise[Seq[String]]()
    $http.get[js.Dynamic]("sociolinguistics/answers") onComplete {
      case Success(response) =>
        p.success(read[Seq[String]](js.JSON.stringify(response)))
      case Failure(e) => p.failure(BackendException("Failed to get sociolinguistics answers", e))
    }
    p.future
  }

  def sociolinguistics(): Future[Seq[SociolinguisticsEntry]] = {
    val p = Promise[Seq[SociolinguisticsEntry]]()
    $http.get[js.Dynamic]("sociolinguistics") onComplete {
      case Success(response) =>
        p.success(read[Seq[SociolinguisticsEntry]](js.JSON.stringify(response)))
      case Failure(e) => p.failure(BackendException("Failed to get sociolinguistics", e))
    }
    p.future
  }

  def validateEafCorpus(file: String): Future[Boolean] = {
    val p = Promise[Boolean]()
    $http.post[js.Dynamic]("convert_five_tiers_validate", js.Dynamic.literal("eaf_url" -> encodeURI(file))) onComplete {
      case Success(response) =>
        p.success(response.is_valid.asInstanceOf[js.Any].asInstanceOf[Boolean])
      case Failure(e) => p.failure(BackendException("Failed to validate corpus", e))
    }
    p.future
  }

  def convertEafCorpus(corpusId: CompositeId, dictionaryId: CompositeId, soundFile: Option[String], markupFile: Option[String]): Future[Unit] = {
    val p = Promise[Unit]()
    var req = Map[String, js.Any](
      "client_id" -> corpusId.clientId,
      "object_id" -> corpusId.objectId,
      "dictionary_client_id" -> dictionaryId.clientId,
      "dictionary_object_id" -> dictionaryId.objectId
    )

    soundFile foreach { url =>
      req = req + ("sound_url" -> encodeURI(url))
    }

    markupFile foreach { url =>
      req = req + ("eaf_url" -> encodeURI(url))
    }

    $http.post[js.Dynamic]("convert_five_tiers", req.toJSDictionary) onComplete {
      case Success(response) =>
        p.success(())
      case Failure(e) => p.failure(BackendException("Failed to convert corpus", e))
    }
    p.future
  }

  /** Phonology generation request. */
  def phonology(
    perspectiveId: CompositeId,
    group_by_description: Boolean,
    only_first_translation: Boolean,
    vowel_selection: Boolean,
    maybe_tier_list: Option[Seq[String]]):
    Future[Unit] =
  {
    val p = Promise[Unit]

    val request =

      JSON.stringify(js.Dynamic.literal(
        "perspective_client_id" -> perspectiveId.clientId,
        "perspective_object_id" -> perspectiveId.objectId,
        "group_by_description" -> group_by_description,
        "only_first_translation" -> only_first_translation,
        "vowel_selection" -> vowel_selection,

        "maybe_tier_list" -> (maybe_tier_list
          map { tier_seq => js.Array(tier_seq: _*) }
          getOrElse(null))))

    $http.post[js.Dynamic](getMethodUrl("phonology"), request) onComplete
    {
      case Success(response) =>

        try
        {
          if (response.asInstanceOf[js.Object].hasOwnProperty("error"))

            p.failure(new BackendException(
              "Error while launching phonology computation:\n" + response.error))

          else p.success(())
        }

        catch
        {
          case e: upickle.Invalid.Json => p.failure(
            BackendException("Malformed json", e))

          case e: upickle.Invalid.Data => p.failure(
            BackendException("Malformed data. Missing some required fields", e))

          case e: Throwable => p.failure(
            BackendException("Unknown exception", e))
        }

      case Failure(e) => p.failure(BackendException(
        "Failed to launch phonology computation: " + e.getMessage, e))
    }

    p.future
  }

  def tasks(): Future[Seq[Task]] = {
    val p = Promise[Seq[Task]]()
    $http.get[js.Dynamic](getMethodUrl("tasks")) onComplete {
      case Success(response)  =>
        p.success(read[Seq[Task]](js.JSON.stringify(response)))
      case Failure(e) =>
        p.failure(BackendException("Failed to get list of tasks", e))
    }
    p.future
  }

  def removeTask(task: Task): Future[Unit] = {
    val p = Promise[Unit]()
    val url = "tasks/" + encodeURIComponent(task.id)
    $http.delete[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response)  =>
        p.success(())
      case Failure(e) =>
        p.failure(BackendException("Failed to remove task", e))
    }
    p.future
  }

  /**
    * Checks if the user has create/delete permissions required to merge lexical entries and entities.
    */
  def mergePermissions(perspectiveId: CompositeId): Future[Boolean] =
  {
    val p = Promise[Boolean]()

    val url = getMethodUrl("merge/permissions/" +
      encodeURIComponent(perspectiveId.clientId.toString) + "/" +
      encodeURIComponent(perspectiveId.objectId.toString))

    val request = JSON.stringify(js.Dynamic.literal())

    $http.post[js.Dynamic](url, request) onComplete
    {
      case Success(response) =>

        try
        {
          if (response.asInstanceOf[js.Object].hasOwnProperty("error"))

            p.failure(new BackendException(
              "Error while checking merge permissions:\n" + response.error))

          else p.success(read[Boolean](
            js.JSON.stringify(response.user_has_permissions)))
        }

        catch
        {
          case e: upickle.Invalid.Json => p.failure(
            BackendException("Malformed JSON", e))

          case e: Throwable => p.failure(
            BackendException("Unknown exception", e))
        }

      case Failure(e) => p.failure(BackendException("Failed to get merge permissions: " + e.getMessage, e))
    }

    p.future
  }

  /**
    * Requests mergeable lexical entries for a perspective.
    */
  def mergeSuggestions(
    perspectiveId: CompositeId,
    algorithm: String,
    field_selection_list: js.Array[js.Dynamic],
    threshold: Double):
    Future[(Seq[LexicalEntry], Seq[(CompositeId, CompositeId, Double)], Boolean)] =
  {
    val p = Promise[(Seq[LexicalEntry], Seq[(CompositeId, CompositeId, Double)], Boolean)]()

    val url = getMethodUrl("merge/suggestions/" +
      encodeURIComponent(perspectiveId.clientId.toString) + "/" +
      encodeURIComponent(perspectiveId.objectId.toString))

    val request = JSON.stringify(js.Dynamic.literal(
      "algorithm" -> algorithm,
      "field_selection_list" -> field_selection_list,
      "levenshtein" -> 1,
      "threshold" -> threshold))

    /* Trying to get merge suggestions. */

    $http.post[js.Dynamic](url, request) onComplete
    {
      case Success(response) =>

        try
        {
          if (response.asInstanceOf[js.Object].hasOwnProperty("error"))

            p.failure(new BackendException(
              "Error while getting merge suggestions:\n" + response.error))

          else
          {
            /* Returning merge suggestions we've got. */

            val entry_seq = read[Seq[LexicalEntry]](
              js.JSON.stringify(response.entry_data))

            val match_seq = read[Seq[(CompositeId, CompositeId, Double)]](
              js.JSON.stringify(response.match_result))

            val user_has_permissions = read[Boolean](
              js.JSON.stringify(response.user_has_permissions))

            p.success((entry_seq, match_seq, user_has_permissions))
          }
        }

        catch
        {
          /* Terminating with error. */

          case e: upickle.Invalid.Json => p.failure(
            BackendException("Malformed merge suggestions JSON", e))

          case e: upickle.Invalid.Data => p.failure(
            BackendException("Malformed data. Missing some required fields", e))

          case e: Throwable => p.failure(
            BackendException("Unknown exception", e))
        }

      case Failure(e) => p.failure(BackendException("Failed to get merge suggestions: " + e.getMessage, e))
    }

    p.future
  }

  /**
    * Merges multiple groups of lexical entries, provided that each group is a subset of a single
    * perspective, returns client/object ids of new lexical entries, a new entry for each merged group.
    *
    * @param publish_any
    *   If this flag is true, we publish results of entity merge if any merged entity is published. If this
    *   flag is false, we publish results of entity merge if all merged entity are published.
    */
  def mergeBulk(
    publish_any: Boolean,
    group_seq: Seq[Seq[CompositeId]]):
    Future[Seq[CompositeId]] =
  {
    val p = Promise[Seq[CompositeId]]

    val request =

      JSON.stringify(js.Dynamic.literal(
        "publish_any" -> publish_any,
        "group_list" ->

        js.Array(group_seq map { entry_id_seq =>
          js.Array(entry_id_seq map { entry_id =>

          js.Dynamic.literal(
            "client_id" -> entry_id.clientId,
            "object_id" -> entry_id.objectId)}: _*)}: _*)))

    $http.post[js.Dynamic](getMethodUrl("merge/bulk"), request) onComplete
    {
      case Success(response) =>

        try
        {
          if (response.asInstanceOf[js.Object].hasOwnProperty("error"))

            p.failure(new BackendException(
              "Error while performing merges:\n" + response.error))

          else p.success(read[Seq[CompositeId]](js.JSON.stringify(response.result)))
        }

        catch
        {
          case e: upickle.Invalid.Json => p.failure(
            BackendException("Malformed json", e))

          case e: upickle.Invalid.Data => p.failure(
            BackendException("Malformed data. Missing some required fields", e))

          case e: Throwable => p.failure(
            BackendException("Unknown exception", e))
        }

      case Failure(e) => p.failure(BackendException("Failed to perform bulk merge: " + e.getMessage, e))
    }

    p.future
  }

  /** Launches background merge task, parameters are the same as of 'mergeBulk' method. */
  def mergeBulkAsync(
    publish_any: Boolean,
    group_seq: Seq[Seq[CompositeId]]):
    Future[Unit] =
  {
    val p = Promise[Unit]

    val request =

      JSON.stringify(js.Dynamic.literal(
        "publish_any" -> publish_any,
        "group_list" ->

        js.Array(group_seq map { entry_id_seq =>
          js.Array(entry_id_seq map { entry_id =>

          js.Dynamic.literal(
            "client_id" -> entry_id.clientId,
            "object_id" -> entry_id.objectId)}: _*)}: _*)))

    $http.post[js.Dynamic](getMethodUrl("merge/bulk_async"), request) onComplete
    {
      case Success(response) =>

        try
        {
          if (response.asInstanceOf[js.Object].hasOwnProperty("error"))

            p.failure(new BackendException(
              "Error while launching asynchronous merge:\n" + response.error))

          else p.success(())
        }

        catch
        {
          case e: upickle.Invalid.Json => p.failure(
            BackendException("Malformed json", e))

          case e: upickle.Invalid.Data => p.failure(
            BackendException("Malformed data. Missing some required fields", e))

          case e: Throwable => p.failure(
            BackendException("Unknown exception", e))
        }

      case Failure(e) => p.failure(BackendException(
        "Failed to launch bulk asynchronous merge: " + e.getMessage, e))
    }

    p.future
  }

  /** 
    * Gathers user participation statistics for a specified perspective in a given time interval
    * [time_begin, time_end), with time interval endpoints 'time_begin', 'time_end' specified as Unix
    * timestamps formatted as YYYY-MM-DDtHH:MM:SS strings.
    */
  def perspectiveStatistics(
    perspective_id: CompositeId, date_from: String, date_to: String):
    Future[js.Dictionary[js.Dictionary[js.Object]]] =
  {
    val p = Promise[js.Dictionary[js.Dictionary[js.Object]]]

    var url = getMethodUrl("statistics/perspective/" +
      encodeURIComponent(perspective_id.clientId.toString) + "/" +
      encodeURIComponent(perspective_id.objectId.toString))

    url = addUrlParameter(url, "time_begin", date_from)
    url = addUrlParameter(url, "time_end", date_to)

    $http.get[js.Dynamic](url) onComplete
    {
      case Success(response) =>

        try
        {
          if (response.asInstanceOf[js.Object].hasOwnProperty("error"))

            p.failure(new BackendException(
              "Error while gathering perspective statistics:\n" + response.error))

          else p.success(response.asInstanceOf[js.Dictionary[js.Dictionary[js.Object]]])
        }

        catch
        {
          case e: upickle.Invalid.Json => p.failure(
            BackendException("Malformed json", e))

          case e: upickle.Invalid.Data => p.failure(
            BackendException("Malformed data. Missing some required fields", e))

          case e: Throwable => p.failure(
            BackendException("Unknown exception", e))
        }

      case Failure(e) => p.failure(BackendException(
        "Failed to gather perspective statistics: " + e.getMessage, e))
    }

    p.future
  }

  /** 
    * Gathers user participation statistics for a specified dictionary in a given time interval
    * [time_begin, time_end), with time interval endpoints 'time_begin', 'time_end' specified as Unix
    * timestamps formatted as YYYY-MM-DDtHH:MM:SS strings.
    */
  def dictionaryStatistics(
    dictionary_id: CompositeId, date_from: String, date_to: String):
    Future[js.Dictionary[js.Dictionary[js.Object]]] =
  {
    val p = Promise[js.Dictionary[js.Dictionary[js.Object]]]

    var url = getMethodUrl("statistics/dictionary/" +
      encodeURIComponent(dictionary_id.clientId.toString) + "/" +
      encodeURIComponent(dictionary_id.objectId.toString))

    url = addUrlParameter(url, "time_begin", date_from)
    url = addUrlParameter(url, "time_end", date_to)

    $http.get[js.Dynamic](url) onComplete
    {
      case Success(response) =>

        try
        {
          if (response.asInstanceOf[js.Object].hasOwnProperty("error"))

            p.failure(new BackendException(
              "Error while gathering dictionary statistics:\n" + response.error))

          else p.success(response.asInstanceOf[js.Dictionary[js.Dictionary[js.Object]]])
        }

        catch
        {
          case e: upickle.Invalid.Json => p.failure(
            BackendException("Malformed json", e))

          case e: upickle.Invalid.Data => p.failure(
            BackendException("Malformed data. Missing some required fields", e))

          case e: Throwable => p.failure(
            BackendException("Unknown exception", e))
        }

      case Failure(e) => p.failure(BackendException(
        "Failed to gather dictionary statistics: " + e.getMessage, e))
    }

    p.future
  }

  /** Gets a list of names of phonology markup tiers for a specified perspective. */
  def phonologyTierList(perspectiveId: CompositeId):
    Future[(Int, js.Dictionary[Int])] =
  {
    val p = Promise[(Int, js.Dictionary[Int])]()

    val url = s"""phonology_tier_list?
      |perspective_client_id=${perspectiveId.clientId}&
      |perspective_object_id=${perspectiveId.objectId}
      |""".stripMargin.replaceAll("\n", "")

    $http.get[js.Dynamic](url) onComplete
    {
      case Success(response) =>

        try
        {
          if (response.asInstanceOf[js.Object].hasOwnProperty("error"))

            p.failure(new BackendException(
              "Error while getting phonology markup tier list:\n" + response.error))

          else p.success((
            read[Int](js.JSON.stringify(response.total_count)),
            response.tier_count.asInstanceOf[js.Dictionary[Int]]))
        }

        catch
        {
          case e: upickle.Invalid.Json => p.failure(
            BackendException("Malformed json", e))

          case e: upickle.Invalid.Data => p.failure(
            BackendException("Malformed data. Missing some required fields", e))

          case e: Throwable => p.failure(
            BackendException("Unknown exception", e))
        }

      case Failure(e) => p.failure(BackendException(
        "Failed to get phonology markup tier list: " + e.getMessage, e))
    }

    p.future
  }


  def createGrant(grant: GrantRequest): Future[Unit] = {
    val p = Promise[Unit]()
    $http.post[js.Dynamic](getMethodUrl("grant"), write[GrantRequest](grant)) onComplete {
      case Success(response)  =>
        p.success(())
      case Failure(e) =>
        p.failure(BackendException("Failed to create grant", e))
    }
    p.future
  }


  def updateGrant(grant: Grant): Future[Unit] = {
    val p = Promise[Unit]()
    $http.put[js.Dynamic](getMethodUrl("grant/" + encodeURIComponent(grant.id.toString)), write[Grant](grant)) onComplete {
      case Success(response)  =>
        p.success(())
      case Failure(e) =>
        p.failure(BackendException("Failed to create grant", e))
    }
    p.future
  }

  def grant(grantId: Int): Future[Grant] = {
    val p = Promise[Grant]()
    $http.get[js.Dynamic](getMethodUrl("grants/" + encodeURIComponent(grantId.toString))) onComplete {
      case Success(response)  =>
        p.success(read[Grant](js.JSON.stringify(response)))
      case Failure(e) =>
        p.failure(BackendException("Failed to get grant", e))
    }
    p.future
  }

  def grants(): Future[Seq[Grant]] = {
    val p = Promise[Seq[Grant]]()
    $http.get[js.Dynamic](getMethodUrl("all_grants")) onComplete {
      case Success(response)  =>
        p.success(read[Seq[Grant]](js.JSON.stringify(response)))
      case Failure(e) =>
        p.failure(BackendException("Failed to get list of grants", e))
    }
    p.future
  }

  def grantUserRequests(): Future[Seq[UserRequest]] = {
    val p = Promise[Seq[UserRequest]]()
    $http.get[js.Dynamic](getMethodUrl("get_current_userrequests")) onComplete {
      case Success(response)  =>
        p.success(read[Seq[UserRequest]](js.JSON.stringify(response)))
      case Failure(e) =>
        p.failure(BackendException("Failed to get list of grant requests", e))
    }
    p.future
  }


  def addDictionaryToGrant(grantId: Int, dictionaryId: CompositeId): Future[Unit] = {
    val p = Promise[Unit]()

    val req = js.Dynamic.literal(
      "grant_id" -> grantId,
      "client_id" -> dictionaryId.clientId,
      "object_id" -> dictionaryId.objectId
    )

    $http.post[js.Dynamic](getMethodUrl("add_dictionary_to_grant"), req) onComplete {
      case Success(response)  =>
        p.success(())
      case Failure(e) =>
        p.failure(BackendException("Failed to add dictionary to grant", e))
    }
    p.future
  }

  def addUserToGrant(grantId: Int, userId: Int): Future[Unit] = {
    val p = Promise[Unit]()

    val req = js.Dynamic.literal(
      "grant_id" -> grantId,
      "user_id" -> userId
    )

    $http.post[js.Dynamic](getMethodUrl("add_user_to_grant"), req) onComplete {
      case Success(response)  =>
        p.success(())
      case Failure(e) =>
        p.failure(BackendException("Failed to add user to grant", e))
    }
    p.future
  }


  def acceptUserRequest(requestId: Int, accept: Boolean): Future[Unit] = {
    val p = Promise[Unit]()

    val req = js.Dynamic.literal(
      "accept" -> accept
    )

    $http.post[js.Dynamic](getMethodUrl("accept_userrequest/" + encodeURIComponent(requestId.toString)), req) onComplete {
      case Success(response)  =>
        p.success(())
      case Failure(e) =>
        p.failure(BackendException("Failed to add user to grant", e))
    }
    p.future
  }

  def grantUserPermission(grantId: Int): Future[Unit] = {
    val p = Promise[Unit]()

    $http.get[js.Dynamic](getMethodUrl("get_grant_permission/" + encodeURIComponent(grantId.toString))) onComplete {
      case Success(response)  =>
        p.success(())
      case Failure(e) =>
        p.failure(BackendException("Failed to add user to grant", e))
    }
    p.future
  }

  def organizations(): Future[Seq[Organization]] = {
    val p = Promise[Seq[Organization]]()

    $http.get[js.Dynamic](getMethodUrl("organization_list")) onComplete {
      case Success(response)  =>
        p.success(read[Seq[Organization]](js.JSON.stringify(response.organizations)))
      case Failure(e) =>
        p.failure(BackendException("Failed to obtain list of organizations", e))
    }
    p.future
  }

  def createOrganization(name: String, about: String): Future[Int] = {
    val p = Promise[Int]()
    $http.post[js.Dynamic](getMethodUrl("organization"), js.Dynamic.literal(
      "name" -> name,
      "about" -> about
    )) onComplete {
      case Success(response)  =>
        p.success(response.organization_id.asInstanceOf[Int])
      case Failure(e) =>
        p.failure(BackendException("Failed to create organization", e))
    }
    p.future
  }

  def updateOrganization(organization: Organization, addUsers: Seq[Int] = Seq[Int](), removeUsers: Seq[Int] = Seq[Int]()): Future[Int] = {
    val p = Promise[Int]()

    val req = js.JSON.parse(write(organization))
    req.add_users = addUsers.toJSArray
    req.remove_users = removeUsers.toJSArray

    $http.put[js.Dynamic](getMethodUrl("organization/" + encodeURIComponent(organization.id.toString)), req) onComplete {
      case Success(response)  =>
        p.success(response.organization_id.asInstanceOf[Int])
      case Failure(e) =>
        p.failure(BackendException("Failed to update organization", e))
    }
    p.future
  }

  def joinOrganization(organizationId: Int): Future[Unit] = {
    val p = Promise[Unit]()

    $http.get[js.Dynamic](getMethodUrl("participate_org/" + encodeURIComponent(organizationId.toString))) onComplete {
      case Success(response)  =>
        p.success(())
      case Failure(e) =>
        p.failure(BackendException("Failed to add user to organization", e))
    }
    p.future
  }

  def joinOrganizationAdmin(organizationId: Int): Future[Unit] = {
    val p = Promise[Unit]()

    $http.get[js.Dynamic](getMethodUrl("administrate_org/" + encodeURIComponent(organizationId.toString))) onComplete {
      case Success(response)  =>
        p.success(())
      case Failure(e) =>
        p.failure(BackendException("Failed to add user to organization's admins", e))
    }
    p.future
  }

  def homePageText(): Future[String] = {
    val p = Promise[String]()

    $http.get[String](getMethodUrl("home_page_text")) onComplete {
      case Success(response)  =>
        p.success(response)
      case Failure(e) =>
        p.failure(BackendException("Failed to get home page text", e))
    }
    p.future
  }

  /** Sound/markup archive generation request. */
  def sound_and_markup(
    perspectiveId: CompositeId,
    published_mode: String):
    Future[Unit] =
  {
    val p = Promise[Unit]

    val url = s"""sound_and_markup?
      |perspective_client_id=${perspectiveId.clientId}&
      |perspective_object_id=${perspectiveId.objectId}&
      |published_mode=${published_mode}
      |""".stripMargin.replaceAll("\n", "")

    $http.get[js.Dynamic](url) onComplete
    {
      case Success(response) =>

        try
        {
          if (response.asInstanceOf[js.Object].hasOwnProperty("error"))

            p.failure(new BackendException(
              "Error while launching sound/markup archive generation:\n" + response.error))

          else p.success(())
        }

        catch
        {
          case e: upickle.Invalid.Json => p.failure(
            BackendException("Malformed json", e))

          case e: upickle.Invalid.Data => p.failure(
            BackendException("Malformed data. Missing some required fields", e))

          case e: Throwable => p.failure(
            BackendException("Unknown exception", e))
        }

      case Failure(e) => p.failure(BackendException(
        "Failed to launch sound/markup archive generation: " + e.getMessage, e))
    }

    p.future
  }
}


@injectable("BackendService")
class BackendServiceFactory($http: HttpService, val timeout: Timeout, val exceptionHandler: ExceptionHandler) extends Factory[BackendService] {
  override def apply(): BackendService = new BackendService($http, timeout, exceptionHandler)
}

