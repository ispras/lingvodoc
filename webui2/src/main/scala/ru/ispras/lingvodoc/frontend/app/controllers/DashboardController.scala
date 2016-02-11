package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.Scope
import com.greencatsoft.angularjs.extensions.{ModalOptions, ModalService}
import com.greencatsoft.angularjs.{AbstractController, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.BackendService

import scala.scalajs.concurrent.JSExecutionContext.Implicits.runNow
import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.URIUtils.encodeURIComponent
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}


@js.native
trait DashboardScope extends Scope {
  var dictionaries: js.Array[Dictionary] = js.native
  var user: User = js.native
}

@JSExport
@injectable("DashboardController")
class DashboardController(scope: DashboardScope, modal: ModalService, backend: BackendService) extends
AbstractController[DashboardScope](scope) {
  val userId = 1

  scope.dictionaries = js.Array[Dictionary]()

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
    options.templateUrl = "DictionaryPropertiesModal.html"
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
    options.templateUrl = "PerspectivePropertiesModal.html"
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
  def setDictionaryStatus(dictionary: Dictionary, status: String) = {
    backend.setDictionaryStatus(dictionary, status)
  }

  @JSExport
  def setPerspectiveStatus(dictionary: Dictionary, perspective: Perspective, status: String) = {
    backend.setPerspectiveStatus(dictionary, perspective, status)
  }

  // load dynamic data
  backend.getCurrentUser onComplete {
    case Success(user) =>

      scope.user = user

      // load dictionary list
      val query = DictionaryQuery(user.id, Seq[Int]())
      backend.getDictionariesWithPerspectives(query) onComplete {
        case Success(dictionaries) =>
          scope.dictionaries = dictionaries.toJSArray
        case Failure(e) => println(e.getMessage)
      }

    case Failure(e) => console.error(e.getMessage)
  }
}

