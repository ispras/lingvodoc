package ru.ispras.lingvodoc.frontend.app.services

import ru.ispras.lingvodoc.frontend.api.exceptions.BackendException
import ru.ispras.lingvodoc.frontend.app.model._
import upickle.default._

import scala.concurrent.{Promise, Future}
import scala.scalajs.concurrent.JSExecutionContext.Implicits.runNow
import scala.scalajs.js
import scala.scalajs.js.URIUtils._
import scala.scalajs.js.{Date, JSON}
import scala.scalajs.js.Any.fromString
import scala.util.{Failure, Success, Try}

import com.greencatsoft.angularjs.{Factory, Service}
import com.greencatsoft.angularjs.core.HttpPromise.promise2future
import com.greencatsoft.angularjs.core.HttpService
import com.greencatsoft.angularjs.injectable
import scala.scalajs.js.JSConverters._
import org.scalajs.dom.console


@injectable("BackendService")
class BackendService(http: HttpService) extends Service {

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
   * @param dictionary
   * @return
   */
  def getDictionaryPerspectives(dictionary: Dictionary): Future[Seq[Perspective]] = {
    val p = Promise[Seq[Perspective]]()
    val url = getMethodUrl("dictionary/" + encodeURIComponent(dictionary.clientId.toString) + "/" +
      encodeURIComponent(dictionary.objectId.toString) + "/perspectives")
    http.get[js.Dynamic](url) onComplete {
      case Success(response) =>
        try {
          val perspectives = read[Seq[Perspective]](js.JSON.stringify(response.perspectives))
          p.success(perspectives)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed perspectives json:" + e.getMessage))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed perspectives data. Missing some " +
            "required fields: " + e.getMessage))
          case e: Throwable => p.failure(BackendException("Unexpected exception:" + e.getMessage))
        }

      case Failure(e) => p.failure(BackendException("Failed to get list of perspectives for dictionary " + dictionary
        .translationString + ": " + e.getMessage))
    }
    p.future
  }

  /**
   * Get list of dictionaries
   * @param query
   * @return
   */
  def getDictionaries(query: DictionaryQuery): Future[Seq[Dictionary]] = {
    val p = Promise[Seq[Dictionary]]()

    http.post[js.Dynamic](getMethodUrl("dictionaries"), write(query)) onComplete {
      case Success(response) =>
        try {
          val dictionaries = read[Seq[Dictionary]](js.JSON.stringify(response.dictionaries))
          p.success(dictionaries)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed dictionary json:" + e.getMessage))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed dictionary data. Missing some " +
            "required fields: " + e.getMessage))
        }
      case Failure(e) => p.failure(BackendException("Failed to get list of dictionaries: " + e.getMessage))
    }
    p.future
  }

  /**
   * Get list of dictionaries with perspectives
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
          case Failure(e) => p.failure(BackendException("Failed to get list of perspectives: " + e.getMessage))
        }
      case Failure(e) => p.failure(BackendException("Failed to get list of dictionaries with perspectives: " + e
        .getMessage))
    }
    p.future
  }

  /**
   * Get language graph
   * @return
   */
  def getLanguages: Future[Seq[Language]] = {
    val p = Promise[Seq[Language]]()
    http.get[js.Dynamic](getMethodUrl("languages")) onComplete {
      case Success(response) =>
        try {
          val languages = read[Seq[Language]](js.JSON.stringify(response.languages))
          p.success(languages)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed languages json:" + e.getMessage))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed languages data. Missing some required" +
            " fields: " + e.getMessage))
        }
      case Failure(e) => p.failure(BackendException("Failed to get list of languages: " + e.getMessage))
    }
    p.future
  }


  /**
   * Get dictionary
   * @param clientId
   * @param objectId
   * @return
   */
  def getDictionary(clientId: Int, objectId: Int): Future[Dictionary] = {
    val p = Promise[Dictionary]()
    val url = "dictionary/" + encodeURIComponent(clientId.toString) + "/" + encodeURIComponent(objectId.toString)
    http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        try {
          p.success(read[Dictionary](js.JSON.stringify(response)))
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed dictionary json:" + e.getMessage))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed dictionary data. Missing some " +
            "required fields: " + e.getMessage))
        }
      case Failure(e) => p.failure(BackendException("Failed to get dictionary: " + e.getMessage))
    }
    p.future
  }

  /**
   * Update dictionary properties
   * @param dictionary
   * @return
   */
  def updateDictionary(dictionary: Dictionary): Future[Unit] = {
    val p = Promise[Unit]()
    val url = "dictionary/" + encodeURIComponent(dictionary.clientId.toString) + "/" + encodeURIComponent(dictionary
      .objectId.toString)
    http.put(getMethodUrl(url), write(dictionary)) onComplete {
      case Success(_) => p.success(Unit)
      case Failure(e) => p.failure(BackendException("Failed to remove dictionary: " + e.getMessage))
    }
    p.future
  }

  /**
   * Remove dictionary
   * @param dictionary
   * @return
   */
  def removeDictionary(dictionary: Dictionary): Future[Unit] = {
    val p = Promise[Unit]()
    val url = "dictionary/" + encodeURIComponent(dictionary.clientId.toString) + "/" + encodeURIComponent(dictionary
      .objectId.toString)
    http.delete(getMethodUrl(url)) onComplete {
      case Success(_) => p.success(Unit)
      case Failure(e) => p.failure(BackendException("Failed to remove dictionary: " + e.getMessage))
    }
    p.future
  }

  /**
   * Set dictionary status
   * @param dictionary
   * @param status
   */
  def setDictionaryStatus(dictionary: Dictionary, status: String): Future[Unit] = {
    val p = Promise[Unit]()
    val req = JSON.stringify(js.Dynamic.literal(status = status))
    val url = "dictionary/" + encodeURIComponent(dictionary.clientId.toString) + "/" + encodeURIComponent(dictionary
      .objectId.toString) + "/state"
    http.put(getMethodUrl(url), req) onComplete {
      case Success(_) =>
        dictionary.status = status
        p.success(Unit)
      case Failure(e) => p.failure(BackendException("Failed to update dictionary status: " + e.getMessage))
    }
    p.future
  }


  // Perspectives

  /**
   * Set perspective status
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

    http.put(getMethodUrl(url), req) onComplete {
      case Success(_) =>
        perspective.status = status
        p.success(Unit)
      case Failure(e) => p.failure(BackendException("Failed to update perspective status: " + e.getMessage))
    }
    p.future
  }

  /**
   * Remove perspective
   * @param dictionary
   * @param perspective
   * @return
   */
  def removePerspective(dictionary: Dictionary, perspective: Perspective): Future[Unit] = {
    val p = Promise[Unit]()
    val url = "dictionary/" + encodeURIComponent(dictionary.clientId.toString) + "/" + encodeURIComponent(dictionary
      .objectId.toString) + encodeURIComponent(perspective.clientId.toString) + "/" + encodeURIComponent(perspective
      .objectId.toString)
    http.delete(getMethodUrl(url)) onComplete {
      case Success(_) => p.success(())
      case Failure(e) => p.failure(BackendException("Failed to remove perspective: " + e.getMessage))
    }
    p.future
  }

  /**
   * Get information about current user
   * @return
   */
  def getCurrentUser: Future[User] = {
    val p = Promise[User]()
    http.get[js.Object](getMethodUrl("user")) onComplete {
      case Success(js) =>
        try {
          val user = read[User](JSON.stringify(js))
          p.success(user)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed user json:" + e.getMessage))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed user data. Missing some " +
            "required fields: " + e.getMessage))
          case e: Throwable => p.failure(BackendException("Unknown exception:" + e.getMessage))
        }
      case Failure(e) => p.failure(BackendException("Failed to get current user: " + e.getMessage))
    }
    p.future
  }

  /**
   * GetPerspective fields
   * @param dictionary
   * @param perspective
   * @return
   */
  def getPerspectiveFields(dictionary: Dictionary, perspective: Perspective): Future[Seq[Field]] = {
    val p = Promise[Seq[Field]]()

    val url = "dictionary/" + encodeURIComponent(dictionary.clientId.toString) + "/" + encodeURIComponent(dictionary
      .objectId.toString) +
      "/perspective/" + encodeURIComponent(perspective.clientId.toString) + "/" + encodeURIComponent(perspective
      .objectId.toString) + "/fields"

    http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        try {
          val fields = read[Seq[Field]](js.JSON.stringify(response.fields))
          p.success(fields)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed fields json:" + e.getMessage))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed fields data. Missing some " +
            "required fields: " + e.getMessage))
          case e: Throwable => p.failure(BackendException("Unknown exception:" + e.getMessage))
        }
      case Failure(e) => p.failure(BackendException("Failed to fetch perspective fields: " + e.getMessage))
    }
    p.future
  }

  /**
   * Get lexical entries list
   * @param dictionary
   * @param perspective
   * @param action - "all", "published", etc
   * @param offset
   * @param count
   * @return
   */
  def getLexicalEntries(dictionary: Dictionary, perspective: Perspective, action: String, offset: Int, count: Int): Future[Seq[LexicalEntry]] = {
    val p = Promise[Seq[LexicalEntry]]()

    var url = "dictionary/" + encodeURIComponent(dictionary.clientId.toString) + "/" + encodeURIComponent(dictionary
      .objectId.toString) +
      "/perspective/" + encodeURIComponent(perspective.clientId.toString) + "/" + encodeURIComponent(perspective
      .objectId.toString) + "/" + action

    url = addUrlParameter(url, "start_from", offset.toString)
    url = addUrlParameter(url, "count", count.toString)

    http.get[js.Dynamic](getMethodUrl(url)) onComplete {
      case Success(response) =>
        try {
          val entries = read[Seq[LexicalEntry]](js.JSON.stringify(response.lexical_entries))
          p.success(entries)
        } catch {
          case e: upickle.Invalid.Json => p.failure(BackendException("Malformed lexical entries json:" + e.getMessage))
          case e: upickle.Invalid.Data => p.failure(BackendException("Malformed lexical entries data. Missing some " +
            "required fields: " + e.getMessage))
          case e: Throwable => p.failure(BackendException("Unknown exception:" + e.getMessage))
        }
      case Failure(e) => p.failure(BackendException("Failed to get lexical entries: " + e.getMessage))
    }
    p.future
  }
}

@injectable("BackendService")
class BackendServiceFactory(http: HttpService) extends Factory[BackendService] {
  override def apply(): BackendService = new BackendService(http)
}
