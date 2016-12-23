package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import ru.ispras.lingvodoc.frontend.app.controllers.traits.LoadingPlaceholder
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.UndefOr
import scala.scalajs.js.annotation.JSExport


@js.native
trait HomeScope extends Scope {
  var languages: js.Array[Language] = js.native
  var data: String = js.native
}

@JSExport
@injectable("HomeController")
class HomeController(scope: HomeScope, backend: BackendService, val timeout: Timeout, val exceptionHandler: ExceptionHandler)
  extends AbstractController[HomeScope](scope)
    with LoadingPlaceholder
    with AngularExecutionContextProvider {


  private[this] var perspectiveMeta = Seq[PerspectiveMeta]()

  scope.languages = js.Array[Language]()

  @JSExport
  def getPerspectiveAuthors(perspective: Perspective): UndefOr[String] = {
    perspectiveMeta.find(_.getId == perspective.getId).flatMap(_.metaData.authors.map(_.authors)).orUndefined
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
      //backend.allStatuses() flatMap { _ =>
        backend.getPublishedDictionaries map { languages =>
          backend.perspectives(published = true) map { perspectives =>
            Utils.flattenLanguages(languages).foreach { language =>
              language.dictionaries.foreach { dictionary =>
                dictionary.perspectives = perspectives.filter(perspective => perspective.parentClientId == dictionary.clientId && perspective.parentObjectId == dictionary.objectId).toJSArray
              }
            }
            scope.languages = languages.toJSArray
            languages
          }
        }
      //}
    }
  })
}
