package ru.ispras.lingvodoc.frontend.app.controllers.modal

import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import ru.ispras.lingvodoc.frontend.app.controllers.traits.SimplePlay
import ru.ispras.lingvodoc.frontend.app.model.{Entity, Language, Locale, LocalizedString}
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, ModalInstance, ModalOptions, ModalService}
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.scalajs.js.JSConverters._
import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}


@js.native
trait ConvertEafScope extends Scope {
  var locales: js.Array[Locale] = js.native
  var languages: js.Array[Language] = js.native
  var language: Option[Language] = js.native
  var languageId: String = js.native
}

@injectable("ConvertEafController")
class ConvertEafController(scope: ConvertEafScope,
                           modal: ModalService,
                           instance: ModalInstance[Unit],
                           backend: BackendService,
                           val timeout: Timeout,
                           val exceptionHandler: ExceptionHandler,
                           params: js.Dictionary[js.Function0[js.Any]])
  extends AbstractController[ConvertEafScope](scope)
    with AngularExecutionContextProvider {

  private[this] var indentation = Map[String, Int]()


  scope.locales = js.Array[Locale]()
  scope.languages = js.Array[Language]()
  scope.language = None
  scope.languageId = ""



  @JSExport
  def newLanguage() = {

    val parentLanguage = scope.languages.find(_.getId == scope.languageId)

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

    instance.result foreach { _ =>
      backend.getLanguages onComplete {
        case Success(tree: Seq[Language]) =>
          indentation = indentations(tree)
          scope.languages = Utils.flattenLanguages(tree).toJSArray
        case Failure(e) =>
      }
    }
  }


  @JSExport
  def languagePadding(language: Language) = {
    "&nbsp;&nbsp;&nbsp;" * indentation.getOrElse(language.getId, 0)
  }

  private[this] def getDepth(language: Language, tree: Seq[Language], depth: Int = 0): Option[Int] = {
    if (tree.exists(_.getId == language.getId)) {
      Some(depth)
    } else {
      for (lang <- tree) {
        val r = getDepth(language, lang.languages.toSeq, depth + 1)
        if (r.nonEmpty) {
          return r
        }
      }
      Option.empty[Int]
    }
  }

  private[this] def indentations(tree: Seq[Language]) = {
    val languages = Utils.flattenLanguages(tree).toJSArray
    languages.map { language =>
      language.getId -> getDepth(language, tree).get
    }.toMap
  }


  backend.getLanguages onComplete {
    case Success(tree: Seq[Language]) =>
      indentation = indentations(tree)
      scope.languages = Utils.flattenLanguages(tree).toJSArray
    case Failure(e) =>
  }




}
