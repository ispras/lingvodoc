package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.Scope
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, ModalOptions, ModalService, UserService}
import com.greencatsoft.angularjs.{AbstractController, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.api.exceptions.BackendException
import ru.ispras.lingvodoc.frontend.app.exceptions.ControllerException
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.utils.LingvodocExecutionContext.Implicits.executionContext
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.scalajs.js
import scala.scalajs.js.Array
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.URIUtils.encodeURIComponent
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}


@js.native
trait DashboardScope extends Scope {
  var dictionaries: js.Array[Dictionary] = js.native
  var statuses: js.Array[TranslationGist] = js.native
}

@JSExport
@injectable("DashboardController")
class DashboardController(scope: DashboardScope, modal: ModalService, userService: UserService, backend: BackendService) extends
AbstractController[DashboardScope](scope) {

  scope.dictionaries = js.Array[Dictionary]()
  scope.statuses = js.Array[TranslationGist]()

  load()


  @JSExport
  def getActionLink(dictionary: Dictionary, perspective: Perspective, action: String) = {
    "/dictionary/" +
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
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(dictionary = dictionary.asInstanceOf[js.Object])
      }
    ).asInstanceOf[js.Dictionary[js.Any]]

    val instance = modal.open[Dictionary](options)

    instance.result map {
      case d: Dictionary => console.log(d.toString)
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
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          dictionary = dictionary.asInstanceOf[js.Object],
          perspective = perspective.asInstanceOf[js.Object])
      }
    ).asInstanceOf[js.Dictionary[js.Any]]

    val instance = modal.open[Perspective](options)

    instance.result map {
      case p: Perspective => console.log(p.toString)
    }
  }

  @JSExport
  def createPerspective(dictionary: Dictionary) = {
    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/createPerspective.html"
    options.controller = "CreatePerspectiveController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          dictionary = dictionary.asInstanceOf[js.Object]
        )
      }
    ).asInstanceOf[js.Dictionary[js.Any]]

    val instance = modal.open[Perspective](options)

    instance.result map {
      p: Perspective => console.log(p.toString)
    }
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
    backend.removeDictionary(dictionary)
  }

  @JSExport
  def removePerspective(dictionary: Dictionary, perspective: Perspective) = {
    backend.removePerspective(dictionary, perspective)
  }

  @JSExport
  def getStatuses(): Array[TranslationAtom] = {
    val localeId = Utils.getLocale().getOrElse(2)
    scope.statuses.flatMap(gist =>
      gist.atoms.find(atom => atom.localeId == localeId)
    )
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




  private[this] def load() = {

    backend.allStatuses() onComplete  {
      case Success(statuses) =>
        scope.statuses = statuses.toJSArray
        backend.getCurrentUser onComplete {
          case Success(user) =>
            userService.setUser(user)
            // load dictionary list
            val query = DictionaryQuery(user.id, Seq[Int]())
            backend.getDictionariesWithPerspectives(query) onComplete {
              case Success(dictionaries) =>
                scope.dictionaries = dictionaries.toJSArray
              case Failure(e) => console.error(e.getMessage)
            }
          case Failure(e) => console.error(e.getMessage)
        }


      case Failure(e) =>
    }
  }



}

