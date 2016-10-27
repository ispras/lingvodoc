package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{Scope, Timeout}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import ru.ispras.lingvodoc.frontend.app.controllers.traits.LoadingPlaceholder
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.BackendService

import scala.scalajs.js
import scala.scalajs.js.{Any, UndefOr}
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}
import scala.scalajs.js.JSConverters._
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.api.exceptions.BackendException


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


  private[this] var perspectiveMeta = Seq[PerspectiveMeta]()

  scope.languages = js.Array[Language]()

  @JSExport
  def getPerspectiveAuthors(perspective: Perspective): UndefOr[String] = {
    perspectiveMeta.find(_.getId == perspective.getId).flatMap(_.metaData.authors.map(_.authors)).orUndefined
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

  override protected def onLoaded[T](result: T): Unit = {


  }

  override protected def onError(reason: Throwable): Unit = {}

  override protected def preRequestHook(): Unit = {
  }

  override protected def postRequestHook(): Unit = {
    scope.$digest()
  }

  doAjax(() => {
    backend.allPerspectivesMeta flatMap { p =>
      perspectiveMeta = p
      backend.allStatuses() flatMap { _ =>
        backend.getPublishedDictionaries map { languages =>
          setPerspectives(languages)
          scope.languages = languages.toJSArray
          languages
        }
      }
    }
  })
}
