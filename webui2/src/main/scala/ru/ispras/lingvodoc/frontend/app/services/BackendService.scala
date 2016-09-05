package ru.ispras.lingvodoc.frontend.app.services

import ru.ispras.lingvodoc.frontend.api.exceptions.BackendException
import ru.ispras.lingvodoc.frontend.app.model._
import upickle.default._

import scala.concurrent.{Future, Promise}
import ru.ispras.lingvodoc.frontend.app.utils.LingvodocExecutionContext.Implicits.executionContext

import scala.scalajs.js
import scala.scalajs.js.URIUtils._
import scala.scalajs.js.{Date, JSON}
import scala.scalajs.js.Any.fromString
import scala.util.{Failure, Success, Try}
import com.greencatsoft.angularjs._
import com.greencatsoft.angularjs.core.HttpPromise.promise2future
import com.greencatsoft.angularjs.core.{HttpService, Q}

import scala.scalajs.js.JSConverters._
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.services.LexicalEntriesType.LexicalEntriesType


object LexicalEntriesType extends Enumeration {
  type LexicalEntriesType = Value
  val Published = Value("published")
  val All = Value("all")
}


@injectable("BackendService")
class BackendService($http: HttpService, $q: Q) extends Service {

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
  def getDictionaryPerspectives(dictionary: Dictionary): Future[Seq[Perspective]] = {
    val p = Promise[Seq[Perspective]]()
    val url = getMethodUrl("dictionary/" + encodeURIComponent(dictionary.clientId.toString) + "/" +
      encodeURIComponent(dictionary.objectId.toString) + "/perspectives")
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
    * Get list of dictionaries with perspectives
    *
    * @param query
    * @return
    */
  def getDictionariesWithPerspectives(query: DictionaryQuery): Future[Seq[Dictionary]] = {
    val p = Promise[Seq[Dictionary]]()
    getDictionaries(query) onComplete {
      case Success(dictionaries) =>
        val futures = dictionaries map {
          dictionary => getDictionaryPerspectives(dictionary)
        }
        Future.sequence(futures) onComplete {
          case Success(perspectives) =>
            val g = (dictionaries, perspectives).zipped.map { (dictionary, p) =>
              dictionary.perspectives = dictionary.perspectives ++ p
              dictionary
            }
            p.success(g)
          case Failure(e) => p.failure(new BackendException("Failed to get list of perspectives: " + e.getMessage))
        }
      case Failure(e) => p.failure(new BackendException("Failed to get list of dictionaries with perspectives: " + e
        .getMessage))
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
          case e: upickle.Invalid.Json => p.failure(new BackendException("Malformed languages json:" + e.getMessage))
          case e: upickle.Invalid.Data => p.failure(new BackendException("Malformed languages data. Missing some required" +
            " fields: " + e.getMessage))
        }
      case Failure(e) => p.failure(new BackendException("Failed to get list of languages: " + e.getMessage))
    }
    p.future
  }


  /**
    * Get dictionary
    *
    * @param clientId
    * @param objectId
    * @return
    */
  def getDictionary(clientId: Int, objectId: Int): Future[Dictionary] = {
    val p = Promise[Dictionary]()
    val url = "dictionary/" + encodeURIComponent(clientId.toString) + "/" + encodeURIComponent(objectId.toString)
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
  def setDictionaryStatus(dictionary: Dictionary, status: String): Future[Unit] = {
    val p = Promise[Unit]()
    val req = JSON.stringify(js.Dynamic.literal(status = status))
    val url = "dictionary/" + encodeURIComponent(dictionary.clientId.toString) + "/" + encodeURIComponent(dictionary
      .objectId.toString) + "/state"
    $http.put(getMethodUrl(url), req) onComplete {
      case Success(_) =>
        //dictionary.status = status
        p.success(())
      case Failure(e) => p.failure(new BackendException("Failed to update dictionary status: " + e.getMessage))
    }
    p.future
  }

  /**
    * Get list of published dictionaries
    * XXX: Actually it returns a complete tree of languages
    *
    * @return
    */
  def getPublishedDictionaries: core.Promise[Seq[Language]] = {
    val defer = $q.defer[Seq[Language]]()
    val req = JSON.stringify(js.Dynamic.literal(group_by_lang = true, group_by_org = false))
    $http.post[js.Dynamic](getMethodUrl("published_dictionaries"), req) onComplete {
      case Success(response) =>
        try {
          val languages = read[Seq[Language]](js.JSON.stringify(response))
          defer.resolve(languages)
        } catch {
          case e: upickle.Invalid.Json => defer.reject("Malformed dictionary json:" + e.getMessage)
          case e: upickle.Invalid.Data => defer.reject("Malformed dictionary data. Missing some required fields: " +
            e.getMessage)
        }
      case Failure(e) => defer.reject("Failed to get list of dictionaries: " + e.getMessage)
    }
    defer.promise
  }

  // Perspectives

  /**
    * Get perspective by ids
    *
    * @param clientId
    * @param objectId
    * @return
    */
  def getPerspective(clientId: Int, objectId: Int): Future[Perspective] = {
    val p = Promise[Perspective]()
    val url = "perspective/" + encodeURIComponent(clientId.toString) + "/" + encodeURIComponent(objectId.toString)
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
    * @param dictionary
    * @param perspective
    * @param status
    * @return
    */
  def setPerspectiveStatus(dictionary: Dictionary, perspective: Perspective, status: String): Future[Unit] = {
    val p = Promise[Unit]()
    val req = JSON.stringify(js.Dynamic.literal(status = status))

    val url = "dictionary/" + encodeURIComponent(dictionary.clientId.toString) +
      "/" + encodeURIComponent(dictionary.objectId.toString) +
      "/perspective/" + encodeURIComponent(perspective.clientId.toString) +
      "/" + encodeURIComponent(perspective.objectId.toString) + "/state"

    $http.put(getMethodUrl(url), req) onComplete {
      case Success(_) =>
        //perspective.status = status
        p.success(())
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


  /**
    * Get list of published perspectives for specified dictionary
    *
    * @param dictionary
    * @return
    */
  def getPublishedDictionaryPerspectives(dictionary: Dictionary): Future[Seq[Perspective]] = {
    val p = Promise[Seq[Perspective]]()
    getDictionaryPerspectives(dictionary) onComplete {
      case Success(perspectives) =>
        //val publishedPerspectives = perspectives.filter(p => p.status.toUpperCase.equals("PUBLISHED"))
        val publishedPerspectives = perspectives
        p.success(publishedPerspectives)
      case Failure(e) => p.failure(BackendException("Failed to get published perspectives", e))
    }
    p.future
  }

  def setPerspectiveMeta(dictionary: Dictionary, perspective: Perspective, metadata: MetaData) = {
    val p = Promise[Unit]()
    val url = ""
    $http.put(getMethodUrl(url), write(metadata)) onComplete {
      case Success(_) => p.success(())
      case Failure(e) => p.failure(new BackendException("Failed to update perspective: " + e.getMessage))
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
          case e: upickle.Invalid.Json => p.failure(new BackendException("Malformed user json:" + e.getMessage))
          case e: upickle.Invalid.Data => p.failure(new BackendException("Malformed user data. Missing some " +
            "required fields: " + e.getMessage))
          case e: Throwable => p.failure(new BackendException("Unknown exception:" + e.getMessage))
        }
      case Failure(e) => p.failure(new BackendException("Failed to get current user: " + e.getMessage))
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
  def getFields(dictionary: Dictionary, perspective: Perspective): Future[Seq[Field]] = {
    val p = Promise[Seq[Field]]()

    val url = "dictionary/" + encodeURIComponent(dictionary.clientId.toString) + "/" + encodeURIComponent(dictionary
      .objectId.toString) +
      "/perspective/" + encodeURIComponent(perspective.clientId.toString) + "/" + encodeURIComponent(perspective
      .objectId.toString) + "/fields"


    $http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        try {
          val fields = read[Seq[Field]](js.JSON.stringify(response.fields))
          p.success(fields)
        } catch {
          case e: upickle.Invalid.Json => p.failure(new BackendException("Malformed fields json:" + e.getMessage))
          case e: upickle.Invalid.Data => p.failure(new BackendException("Malformed fields data. Missing some " +
            "required fields: " + e.getMessage))
          case e: Throwable => p.failure(new BackendException("Unknown exception:" + e.getMessage))
        }
      case Failure(e) => p.failure(new BackendException("Failed to fetch perspective fields: " + e.getMessage))
    }
    p.future
  }

  /**
    * Update perspective fields
    *
    * @param dictionary
    * @param perspective
    * @return
    */
  def updateFields(dictionary: Dictionary, perspective: Perspective): Future[Unit] = {
    val p = Promise[Unit]()
    val url = "dictionary/" + encodeURIComponent(dictionary.clientId.toString) + "/" + encodeURIComponent(dictionary
      .objectId.toString) + "/perspective/" + encodeURIComponent(perspective.clientId.toString) + "/" +
      encodeURIComponent(perspective
        .objectId.toString) + "/fields"
    $http.post(getMethodUrl(url), write(perspective)) onComplete {
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
    getFields(dictionary, perspective) onComplete {
      case Success(fields) =>
        perspective.fields = fields.toJSArray
        p.success(perspective)
      case Failure(e) => p.failure(new BackendException("Failed to fetch perspective fields: " + e.getMessage))
    }
    p.future
  }


  /**
    *
    * @param dictionary
    * @param perspective
    * @return
    */
  def getPublishedLexicalEntriesCount(dictionary: Dictionary, perspective: Perspective): Future[Int] = {
    val p = Promise[Int]()

    val url = "dictionary/" + encodeURIComponent(dictionary.clientId.toString) +
      "/" + encodeURIComponent(dictionary.objectId.toString) +
      "/perspective/" + encodeURIComponent(perspective.clientId.toString) +
      "/" + encodeURIComponent(perspective.objectId.toString) + "/published_count"

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
  def getLexicalEntries(dictionary: Dictionary, perspective: Perspective, action: LexicalEntriesType, offset: Int, count: Int): Future[Seq[LexicalEntry]] = {
    val p = Promise[Seq[LexicalEntry]]()

    import LexicalEntriesType._
    val a = action match {
      case All => "all"
      case Published => "published"
    }

    var url = "dictionary/" + encodeURIComponent(dictionary.clientId.toString) +
      "/" + encodeURIComponent(dictionary.objectId.toString) +
      "/perspective/" + encodeURIComponent(perspective.clientId.toString) +
      "/" + encodeURIComponent(perspective.objectId.toString) + "/" + a

    url = addUrlParameter(url, "start_from", offset.toString)
    url = addUrlParameter(url, "count", count.toString)

    $http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        try {
          val entries = read[Seq[LexicalEntry]](js.JSON.stringify(response.lexical_entries))
          p.success(entries)
        } catch {
          case e: upickle.Invalid.Json => p.failure(new BackendException("Malformed lexical entries json:" + e.getMessage))
          case e: upickle.Invalid.Data => p.failure(new BackendException("Malformed lexical entries data. Missing some required fields: " + e.getMessage))
          case e: Throwable => p.failure(new BackendException("Unknown exception:" + e.getMessage))

        }
      case Failure(e) => p.failure(new BackendException("Failed to get lexical entries: " + e.getMessage))
    }
    p.future
  }

  /**
    * Get list of dictionaries
    *
    * @param clientID client's id
    * @param objectID object's id
    *
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
  def login(username: String, password: String) = {
    val defer = $q.defer[Int]()
    val req = JSON.stringify(js.Dynamic.literal(login = username, password = password))
    $http.post[js.Dynamic](getMethodUrl("signin"), req) onComplete {
      case Success(response) =>
        try {
          val clientId = response.client_id.asInstanceOf[Int]
          defer.resolve(clientId)
        } catch {
          case e: Throwable => defer.reject("Unknown exception:" + e.getMessage)
        }
      case Failure(e) => defer.reject("Failed to sign in: " + e.getMessage)
    }
    defer.promise
  }

  /**
    * Logout user
    *
    * @return
    */
  def logout(): core.Promise[Unit] = {
    val defer = $q.defer[Unit]()
    val p = Promise[Unit]()
    $http.get[js.Dynamic](getMethodUrl("logout")) onComplete {
      case Success(response) => defer.resolve(())
      case Failure(e) => defer.reject(e.getMessage)
    }
    defer.promise
  }

  /**
    * Sign up
    * @param login
    * @param name
    * @param password
    * @param email
    * @param day
    * @param month
    * @param year
    * @return
    */
  def signup(login: String, name: String, password: String, email: String, day: Int, month: Int, year: Int) = {
    val defer = $q.defer[Unit]()
    val req = JSON.stringify(js.Dynamic.literal(login = login, name = name, email = email, password = password, day = day, month = month, year = year))
    $http.post[js.Dynamic](getMethodUrl("signup"), req) onComplete {
      case Success(response) => defer.resolve(())
      case Failure(e) => defer.reject("Failed to sign up: " + e.getMessage)
    }
    defer.promise
  }

  /**
    * Get list of all statuses
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


  /**
    * Gets translation atom by id
    * @param clientId
    * @param objectId
    * @return
    */
  def translationAtom(clientId: Int, objectId: Int): Future[TranslationAtom] = {
    val defer = $q.defer[TranslationAtom]()
    val url = "translationatom/" + encodeURIComponent(clientId.toString) + "/" + encodeURIComponent(objectId.toString)
    $http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        val atom = read[TranslationAtom](js.JSON.stringify(response))
        defer.resolve(atom)
      case Failure(e) => defer.reject("Failed to get translation atom: " + e.getMessage)
    }
    defer.promise
  }

  /**
    * Creates translation atom
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


  def translationGist(clientId: Int, objectId: Int): Future[TranslationGist] = {
    val defer = $q.defer[TranslationGist]()
    val url = "translationgist/" + encodeURIComponent(clientId.toString) + "/" + encodeURIComponent(objectId.toString)
    $http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        try {
          val gist = read[TranslationGist](js.JSON.stringify(response))
          defer.resolve(gist)
        } catch {
          case e: upickle.Invalid.Json => defer.reject("Malformed translation gist json:" + e.getMessage)
          case e: upickle.Invalid.Data => defer.reject("Malformed translation gist data. Missing some " + "required fields: " + e.getMessage)
          case e: Throwable => defer.reject("Unexpected exception:" + e.getMessage)
        }
      case Failure(e) => defer.reject("Failed to get translation gist: " + e.getMessage)
    }
    defer.promise
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


  def translateLanguage(language: Language, localeId: Int): Future[Language] = {
    val defer = $q.defer[Language]()

    translationGist(language.translationGistClientId, language.translationGistObjectId) onComplete {
      case Success(gist) =>
        gist.atoms.find(atom => atom.localeId == localeId) match {
          case Some(atom) => language.translation = Some(atom.content)
          case None => language.translation = None
        }
        defer.resolve(language)

      case Failure(e) => defer.reject("Failed to get translation for language: " + e.getMessage)
    }
    defer.future
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


  def createDictionary(names: Seq[LocalizedString], language: Language): Future[CompositeId] = {
    val p = Promise[CompositeId]()

    createTranslationGist("Dictionary") map {
      gistId =>
        Future.sequence(names.map(name => createTranslationAtom(gistId, name))) map {
          _ =>
            val req = js.Dynamic.literal("translation_gist_client_id" -> gistId.clientId,
              "translation_gist_object_id" -> gistId.objectId,
              "parent_client_id" -> language.clientId,
              "parent_object_id" -> language.objectId
            )

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


  def createPerspectives(dictionaryId: CompositeId, req: Seq[js.Dynamic]): Future[CompositeId] = {
    val p = Promise[CompositeId]()
    val url = "dictionary/" + encodeURIComponent(dictionaryId.clientId.toString) + "/" + encodeURIComponent(dictionaryId.objectId.toString) + "/complex_create"
    $http.post[js.Dynamic](getMethodUrl(url), req.toJSArray) onComplete {
      case Success(response) =>
        try {
          val id = read[CompositeId](js.JSON.stringify(response))
          p.success(id)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Failed to create perspective.", e))
          case e: upickle.Invalid.Data => p.failure(BackendException("Failed to create perspective.", e))
        }
      case Failure(e) => p.failure(BackendException("Failed to create perspective", e))
    }
    p.future
  }


  def getLocales(): Future[Seq[Locale]] = {
    val defer = $q.defer[Seq[Locale]]()
    val locales = Locale(2, "En", "English", "") :: Locale(1, "Ru", "Russian", "") :: Locale(3, "De", "German", "") :: Locale(4, "Fr", "French", "") :: Nil
    defer.resolve(locales)
    defer.future
  }




}


@injectable("BackendService")
class BackendServiceFactory($http: HttpService, $q: Q) extends Factory[BackendService] {
  override def apply(): BackendService = new BackendService($http, $q)
}
