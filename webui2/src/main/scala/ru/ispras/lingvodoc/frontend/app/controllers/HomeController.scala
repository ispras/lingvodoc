package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{Injector, Scope}
import com.greencatsoft.angularjs.{AbstractController, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.api.exceptions.BackendException
import ru.ispras.lingvodoc.frontend.app.services.{ModalService, ModalOptions, BackendService}
import ru.ispras.lingvodoc.frontend.app.model.{Field, Language, Perspective}
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, ExceptionHandlerFactory}
import ru.ispras.lingvodoc.frontend.app.utils.LingvodocExecutionContext.Implicits.executionContext

import scala.scalajs.js
import scala.scalajs.js.{Function2, Object}
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}


@js.native
trait HomeScope extends Scope {
  var languages: js.Array[Language] = js.native
}

@injectable("HomeController")
class HomeController(scope: HomeScope, injector: Injector, backend: BackendService, modal: ModalService) extends AbstractController[HomeScope](scope) {

  private[this] val exceptionHandler = injector.get[Function2[Throwable, Object, Unit]]("$exceptionHandler")

  scope.languages = Seq[Language]().toJSArray

  load()

  @JSExport
  def getPerspectiveAuthors(perspective: Perspective): String = {
    ""
  }

  private[this] def setPerspectives(languages: Seq[Language]): Unit = {
    for (language <- languages) {
      for (dictionary <- language.dictionaries) {
        backend.getDictionaryPerspectives(dictionary, onlyPublished = true) onComplete {
          case Success(perspectives) =>
            dictionary.perspectives = perspectives.toJSArray
          case Failure(e) => exceptionHandler(BackendException("Failed to get published perspectives list", e), null)
        }
      }
      setPerspectives(language.languages.toSeq)
    }
  }


  private[this] def load() = {

    backend.allStatuses() map { _ =>
      backend.getPublishedDictionaries onComplete {
        case Success(languages) =>
          setPerspectives(languages)
          scope.languages = languages.toJSArray
        case Failure(e) => exceptionHandler(BackendException("Failed to get published dictionaries list", e), null)
      }
    }
  }
}
