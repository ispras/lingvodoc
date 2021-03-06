package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{ExceptionHandler, Location, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.{ModalOptions, ModalService}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.controllers.traits.{LoadingPlaceholder, Messages}
import ru.ispras.lingvodoc.frontend.app.exceptions.ControllerException
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, UserService}
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.URIUtils.encodeURIComponent
import scala.scalajs.js.annotation.{JSExport, JSExportAll}
import scala.scalajs.js.Array
import scala.util.{Failure, Success}


@JSExportAll
case class PageStatus(var loaded: Boolean = false)


@js.native
trait DashboardScope extends Scope {
  var dictionaries: js.Array[Dictionary] = js.native
  var statuses: js.Array[TranslationGist] = js.native
  var status: Boolean = js.native
}


@JSExport
@injectable("DashboardController")
class DashboardController(scope: DashboardScope, val modal: ModalService, location: Location, userService: UserService, backend: BackendService, val timeout: Timeout, val exceptionHandler: ExceptionHandler) extends
  AbstractController[DashboardScope](scope)
  with AngularExecutionContextProvider
  with LoadingPlaceholder
  with Messages
{

  scope.dictionaries = js.Array[Dictionary]()
  scope.statuses = js.Array[TranslationGist]()
  scope.status = false

  private[this] var hasGlobalChangeStatusRole = false
  private[this] var hasChangeStatusRole = Seq.empty[CompositeId]
  private[this] var hasGlobalPerspectiveChangeStatusRole = false
  private[this] var hasChangePerspectiveStatusRole = Seq.empty[CompositeId]


  @JSExport
  def getActionLink(dictionary: Dictionary, perspective: Perspective, action: String) = {
    "#/dictionary/" +
      encodeURIComponent(dictionary.clientId.toString) + '/' +
      encodeURIComponent(dictionary.objectId.toString) + "/perspective/" +
      encodeURIComponent(perspective.clientId.toString) + "/" +
      encodeURIComponent(perspective.objectId.toString) + "/" +
      action
  }

  @JSExport
  def editDictionaryProperties(dictionary: Dictionary) = {
    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/dictionaryProperties.html"
    options.controller = "DictionaryPropertiesController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.windowClass = "sm-modal-window"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(dictionary = dictionary.asInstanceOf[js.Object])
      }
    ).asInstanceOf[js.Dictionary[Any]]

    val instance = modal.open[Dictionary](options)

    instance.result map {
      case d: Dictionary =>
    }
  }

  @JSExport
  def editPerspectiveProperties(dictionary: Dictionary, perspective: Perspective) = {
    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/perspectiveProperties.html"
    options.controller = "PerspectivePropertiesController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.windowClass = "sm-modal-window"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          dictionary = dictionary.asInstanceOf[js.Object],
          perspective = perspective.asInstanceOf[js.Object])
      }
    ).asInstanceOf[js.Dictionary[Any]]

    val instance = modal.open[Perspective](options)

    instance.result map {
      case p: Perspective => console.log(p.toString)
    }
  }

  @JSExport
  def createPerspective(dictionary: Dictionary) = {
    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/createPerspective.html"
    options.controller = "CreatePerspectiveModalController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          dictionary = dictionary.asInstanceOf[js.Object]
        )
      }
    ).asInstanceOf[js.Dictionary[Any]]

    val instance = modal.open[Unit](options)

    instance.result map {
      _ =>
        backend.getDictionaryPerspectives(dictionary, onlyPublished = false) map {
          perspectives => dictionary.perspectives = perspectives.toJSArray
        }
    }
  }


  @JSExport
  def editDictionaryRoles(dictionary: Dictionary) = {
    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/editDictionaryRoles.html"
    options.controller = "EditDictionaryRolesModalController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          dictionary = dictionary.asInstanceOf[js.Object]
        )
      }
    ).asInstanceOf[js.Dictionary[Any]]

    val instance = modal.open[Unit](options)

    instance.result map {
      _ =>
    }
  }

  @JSExport
  def editPerspectiveRoles(dictionary: Dictionary, perspective: Perspective) = {
    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/editPerspectiveRoles.html"
    options.controller = "EditPerspectiveRolesModalController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          dictionary = dictionary.asInstanceOf[js.Object],
          perspective = perspective.asInstanceOf[js.Object]
        )
      }
    ).asInstanceOf[js.Dictionary[Any]]

    val instance = modal.open[Unit](options)

    instance.result map {
      _ =>
    }
  }

  @JSExport
  def loadMyDictionaries() = {
    val load = () => {
      val user = userService.getUser()
      val query = DictionaryQuery()
      query.userCreated = Some(Seq[Int](user.id))
      backend.getDictionariesWithPerspectives(query) map {
        dictionaries =>
          scope.dictionaries = dictionaries.toJSArray
          dictionaries
      } recover {
        case e: Throwable => Future.failed(e)
      }
    }
    doAjax(load)
  }

  @JSExport
  def loadAvailableDictionaries() = {


    val load = () => {
      val user = userService.getUser()
      val query = DictionaryQuery()
      query.author = Some(user.id)
      backend.getDictionariesWithPerspectives(query) map {
        dictionaries =>
          scope.dictionaries = dictionaries.toJSArray
          dictionaries
      } recover {
        case e: Throwable => Future.failed(e)
      }
    }
    doAjax(load)
  }


  @JSExport
  def setDictionaryStatus(dictionary: Dictionary, status: TranslationAtom) = {

    scope.statuses.find(gist => gist.clientId == status.parentClientId && gist.objectId == status.parentObjectId) match {
      case Some(gist) => backend.setDictionaryStatus(dictionary, gist) onComplete {
        case Success(_) =>
          dictionary.stateTranslationGistClientId = gist.clientId
          dictionary.stateTranslationGistObjectId = gist.objectId
        case Failure(e) => throw ControllerException("Failed to set dictionary status!", e)
      }
      case None => throw new ControllerException("Status not found!")
    }
  }

  @JSExport
  def setPerspectiveStatus(perspective: Perspective, status: TranslationAtom) = {

    scope.statuses.find(gist => gist.clientId == status.parentClientId && gist.objectId == status.parentObjectId) match {
      case Some(gist) => backend.setPerspectiveStatus(perspective, gist) onComplete {
        case Success(_) =>
          perspective.stateTranslationGistClientId = gist.clientId
          perspective.stateTranslationGistObjectId = gist.objectId
        case Failure(e) => throw ControllerException("Failed to set perspective status!", e)
      }
      case None => throw new ControllerException("Status not found!")
    }
  }

  @JSExport
  def removeDictionary(dictionary: Dictionary) = {
    backend.removeDictionary(dictionary) map { _ =>
      scope.dictionaries = scope.dictionaries.filterNot(_.getId == dictionary.getId)
    } recover {
      case e: Throwable =>
        showException(e)
    }
  }

  @JSExport
  def removePerspective(dictionary: Dictionary, perspective: Perspective) = {
    backend.removePerspective(dictionary, perspective) map { _ =>
      scope.dictionaries.find(_.getId == dictionary.getId) foreach { d =>
        d.perspectives = d.perspectives.filterNot(_.getId == perspective.getId)
      }
    } recover {
      case e: Throwable =>
        showException(e)
    }
  }

  @JSExport
  def getStatuses(): Array[TranslationAtom] = {
    val localeId = Utils.getLocale().getOrElse(2)
    scope.statuses.flatMap(gist =>
      gist.atoms.find(atom => atom.localeId == localeId)
    )
  }

  @JSExport
  def changingDictionaryStatusDisabled(dictionary: Dictionary): Boolean = {
    !(hasGlobalChangeStatusRole || hasChangeStatusRole.exists(_.getId == dictionary.getId))
  }

  @JSExport
  def changingPerspectveStatusDisabled(perspective: Perspective): Boolean = {
    !(hasGlobalPerspectiveChangeStatusRole || hasChangePerspectiveStatusRole.exists(_.getId == perspective.getId))
  }

  @JSExport
  def getDictionaryStatus(dictionary: Dictionary): TranslationAtom = {
    val localeId = Utils.getLocale().getOrElse(2)
    scope.statuses.find(gist => gist.clientId == dictionary.stateTranslationGistClientId && gist.objectId == dictionary.stateTranslationGistObjectId) match {
      case Some(statusGist) => statusGist.atoms.find(atom => atom.localeId == localeId) match {
        case Some(atom) => atom
        case None => throw new ControllerException("Status has no translation for current locale!")
      }
      case None => throw new ControllerException("Unknown status id!")
    }
  }

  @JSExport
  def getPerspectiveStatus(perspective: Perspective): TranslationAtom = {
    val localeId = Utils.getLocale().getOrElse(2)
    scope.statuses.find(gist => gist.clientId == perspective.stateTranslationGistClientId && gist.objectId == perspective.stateTranslationGistObjectId) match {
      case Some(statusGist) => statusGist.atoms.find(atom => atom.localeId == localeId) match {
        case Some(atom) => atom
        case None => throw new ControllerException("Status has no translation for current locale!")
      }
      case None => throw new ControllerException("Unknown status id!")
    }
  }

  /** Opens dictionary statistics page. */
  @JSExport
  def dictionaryStatistics(dictionary: Dictionary): Unit =
  {
    val options = ModalOptions()

    options.templateUrl = "/static/templates/modal/dictionaryStatistics.html"
    options.controller = "DictionaryStatisticsModalController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"

    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          dictionaryId = CompositeId(dictionary.clientId, dictionary.objectId).asInstanceOf[js.Object]
        )
      }
    ).asInstanceOf[js.Dictionary[Any]]

    modal.open[Unit](options)
  }

  /** Opens perspective statistics page. */
  @JSExport
  def perspectiveStatistics(perspective: Perspective): Unit =
  {
    val options = ModalOptions()

    options.templateUrl = "/static/templates/modal/perspectiveStatistics.html"
    options.controller = "PerspectiveStatisticsModalController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"

    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          perspectiveId = CompositeId(perspective.clientId, perspective.objectId).asInstanceOf[js.Object]
        )
      }
    ).asInstanceOf[js.Dictionary[Any]]

    modal.open[Unit](options)
  }


  override protected def onLoaded[T](result: T): Unit = {
  }

  override protected def onError(reason: Throwable): Unit = {

  }

  override protected def preRequestHook(): Unit = {
    scope.status = false
  }

  override protected def postRequestHook(): Unit = {
    scope.status = true
  }


  doAjax(() => {
    backend.allStatuses().flatMap(statuses => {
      scope.statuses = statuses.toJSArray
      backend.getCurrentUser flatMap { user =>

        hasGlobalChangeStatusRole = user.roles.filter(_.name == "Can edit dictionary status").exists(_.subjectOverride)
        hasChangeStatusRole = user.roles.filter(_.name == "Can edit dictionary status").filter(_.subject.nonEmpty).flatMap(_.subject)

        hasGlobalPerspectiveChangeStatusRole = user.roles.filter(_.name == "Can edit perspective status").exists(_.subjectOverride)
        hasChangePerspectiveStatusRole = user.roles.filter(_.name == "Can edit perspective status").filter(_.subject.nonEmpty).flatMap(_.subject)

        userService.setUser(user)
        // load dictionary list
        val query = DictionaryQuery()
        query.author = Some(user.id)
        query.corpora = Some(false)
        backend.getDictionariesWithPerspectives(query) map {
          dictionaries => scope.dictionaries = dictionaries.toJSArray
            dictionaries
        } recover {
          case e: Throwable => Future.failed[Any](e)
        }
      } recover {
        case e: Throwable => Future.failed[Any](e)
      }
    }).recover {
      case e: Throwable => Future.failed[Any](e)
    }
  })
}

