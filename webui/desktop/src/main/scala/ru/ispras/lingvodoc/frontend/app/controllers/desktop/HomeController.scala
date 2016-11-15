package ru.ispras.lingvodoc.frontend.app.controllers.desktop

import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import com.greencatsoft.angularjs.core._
import ru.ispras.lingvodoc.frontend.app.controllers.traits.LoadingPlaceholder
import ru.ispras.lingvodoc.frontend.app.model.{Location => _, _}
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.UndefOr
import scala.scalajs.js.annotation.JSExport
import scala.scalajs.js.JSConverters._


@js.native
trait HomeScope extends Scope {
  var languages: js.Array[Language] = js.native
}

@injectable("HomeController")
class HomeController(scope: HomeScope, val rootScope: RootScope,
                     val location: Location,
                     val backend: BackendService,
                     val timeout: Timeout,
                     val exceptionHandler: ExceptionHandler)
  extends AbstractController(scope)
    with AngularExecutionContextProvider
    with LoadingPlaceholder {

  private[this] var selectedDictionaries = Seq[Dictionary]()
  private[this] var perspectiveMeta = Seq[PerspectiveMeta]()

  scope.languages = js.Array[Language]()

  @JSExport
  def getPerspectiveAuthors(perspective: Perspective): UndefOr[String] = {
    perspectiveMeta.find(_.getId == perspective.getId).flatMap(_.metaData.authors.map(_.authors)).orUndefined
  }


  @JSExport
  def isDictionarySelected(dictionary: Dictionary): Boolean = {
    selectedDictionaries.exists(_.getId == dictionary.getId)
  }

  @JSExport
  def toggleDictionarySelection(dictionary: Dictionary) = {
    if (isDictionarySelected(dictionary)) {
      selectedDictionaries = selectedDictionaries.filterNot(_.getId == dictionary.getId)
    } else {
      selectedDictionaries = selectedDictionaries :+ dictionary
    }
  }

  @JSExport
  def download() = {
    Future.sequence(selectedDictionaries.map(dictionary => backend.syncDownloadDictionary(CompositeId.fromObject(dictionary)))) foreach { _ =>

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
      backend.getAvailableDesktopDictionaries map { languages =>
        backend.getAvailableDesktopPerspectives(published = true) map { perspectives =>
          Utils.flattenLanguages(languages).foreach { language =>
            language.dictionaries.foreach { dictionary =>
              dictionary.perspectives = perspectives.filter(perspective => perspective.parentClientId == dictionary.clientId && perspective.parentObjectId == dictionary.objectId).toJSArray
            }
          }
          scope.languages = languages.toJSArray
          languages
        }
      }
    }
  })







}
