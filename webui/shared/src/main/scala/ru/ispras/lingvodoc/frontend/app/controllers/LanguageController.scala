package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.{ModalOptions, ModalService}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import ru.ispras.lingvodoc.frontend.app.exceptions.ControllerException
import ru.ispras.lingvodoc.frontend.app.model.Language
import ru.ispras.lingvodoc.frontend.app.services.BackendService

import scala.annotation.tailrec
import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}


@js.native
trait LanguageScope extends Scope {
  var languages: js.Array[Language] = js.native
}


@injectable("LanguageController")
class LanguageController(scope: LanguageScope, modal: ModalService, backend: BackendService, val timeout: Timeout, val exceptionHandler: ExceptionHandler) extends AbstractController[LanguageScope](scope) with AngularExecutionContextProvider {

  scope.languages = js.Array()

  load()


  @JSExport
  def createLanguage(parentLanguage: Language): Unit = {
    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/createLanguage.html"
    options.controller = "CreateLanguageController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          "parentLanguage" -> Some(parentLanguage).asInstanceOf[js.Object]
        )
      }
    ).asInstanceOf[js.Dictionary[Any]]

    val instance = modal.open[Language](options)

    instance.result foreach { _ =>
      load()
    }
  }

  @JSExport
  def createRootLanguage(): Unit = {
    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/createLanguage.html"
    options.controller = "CreateLanguageController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal()
      }
    ).asInstanceOf[js.Dictionary[Any]]

    val instance = modal.open[Language](options)

    instance.result foreach { _ =>
        load()
    }
  }

  @JSExport
  def editLanguage(language: Language): Unit = {
    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/createLanguage.html"
    options.controller = "CreateLanguageController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          "language" -> language.asInstanceOf[js.Object],
          "parentLanguage" -> Language.findParentLanguage(language, scope.languages.toSeq).asInstanceOf[js.Object]
        )
      }
    ).asInstanceOf[js.Dictionary[Any]]

    modal.open[Language](options).result foreach { _ =>
      load()
    }
  }

  private[this] def load() = {
    backend.getLanguages onComplete {
      case Success(tree: Seq[Language]) =>
        scope.languages = tree.toJSArray
      case Failure(e) => throw ControllerException("Failed to get list of languages", e)
    }
  }
}
