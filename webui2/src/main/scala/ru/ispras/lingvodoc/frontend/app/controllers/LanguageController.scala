package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{Scope, Timeout}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import org.scalajs.dom._
import ru.ispras.lingvodoc.frontend.app.exceptions.ControllerException
import ru.ispras.lingvodoc.frontend.app.model.Language
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, ModalOptions, ModalService}

import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}


@js.native
trait LanguageScope extends Scope {
  var languages: js.Array[Language] = js.native
}


@injectable("LanguageController")
class LanguageController(scope: LanguageScope, modal: ModalService, backend: BackendService, val timeout: Timeout) extends AbstractController[LanguageScope](scope) with AngularExecutionContextProvider {

  scope.languages = js.Array()

  load()


  @JSExport
  def createLanguage(parentLanguage: Language) = {
    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/createLanguage.html"
    options.controller = "CreateLanguageController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          "parentLanguage" -> parentLanguage.asInstanceOf[js.Object]
        )
      }
    ).asInstanceOf[js.Dictionary[js.Any]]

    val instance = modal.open[Language](options)

    instance.result map {
      lang: Language => parentLanguage.languages.push(lang)
    }
  }

  @JSExport
  def createRootLanguage() = {
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
    ).asInstanceOf[js.Dictionary[js.Any]]

    val instance = modal.open[Language](options)

    instance.result map {
      lang: Language => scope.languages.push(lang)
    }
  }

  private[this] def load() = {
    backend.getLanguages onComplete {
      case Success(tree: Seq[Language]) =>
        scope.languages = tree.toJSArray
        console.log(scope.languages)
      case Failure(e) => throw ControllerException("Failed to get list of languages", e)
    }
  }
}