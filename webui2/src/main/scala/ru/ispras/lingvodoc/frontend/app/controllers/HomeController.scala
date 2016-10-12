package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{Scope, Timeout}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import ru.ispras.lingvodoc.frontend.app.controllers.traits.LoadingPlaceholder
import ru.ispras.lingvodoc.frontend.app.model.{DictionaryQuery, Language, Perspective}
import ru.ispras.lingvodoc.frontend.app.services.BackendService

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.Any
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}
import scala.scalajs.js.JSConverters._



@js.native
trait HomeScope extends Scope {
  var languages: js.Array[Language] = js.native
}

@JSExport
@injectable("HomeController")
class HomeController(scope: HomeScope, backend: BackendService, val timeout: Timeout)
  extends AbstractController[HomeScope](scope)
    with LoadingPlaceholder
    with AngularExecutionContextProvider {

  scope.languages = js.Array[Language]()

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
          case Failure(e) =>
        }
      }
      setPerspectives(language.languages.toSeq)
    }
  }

  override protected def onLoaded[T](result: T): Unit = {}

  override protected def onError(reason: Throwable): Unit = {}

  override protected def preRequestHook(): Unit = {
  }

  override protected def postRequestHook(): Unit = {
  }

  doAjax(() => {
    backend.allStatuses() map { _ =>
      backend.getPublishedDictionaries onComplete {
        case Success(languages) =>
          setPerspectives(languages)
          scope.languages = languages.toJSArray
          languages
        case Failure(e) =>
      }
    }
  })
}
