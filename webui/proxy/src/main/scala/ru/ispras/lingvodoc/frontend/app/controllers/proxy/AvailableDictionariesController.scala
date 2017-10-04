package ru.ispras.lingvodoc.frontend.app.controllers.proxy

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
import scala.scalajs.js.Dynamic.global


@js.native
trait AvailableDictionariesScope extends Scope {
  var languages: js.Array[Language] = js.native
}

@injectable("AvailableDictionariesController")
class AvailableDictionariesController(scope: AvailableDictionariesScope, val rootScope: RootScope,
                     val location: Location,
                     val backend: BackendService,
                     val timeout: Timeout,
                     val exceptionHandler: ExceptionHandler)
  extends AbstractController(scope)
    with AngularExecutionContextProvider
    with LoadingPlaceholder {

  private[this] var downloadedDictionaries = Seq[Dictionary]()
  private[this] var selectedDictionaries = Seq[Dictionary]()
  private[this] var perspectiveMeta = Seq[PerspectiveMeta]()
  private[this] var permissions = Map[Int, Map[Int, PerspectivePermissions]]()

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
    global.alert("Пока не закончится процесс синхронизации, система работает в режиме 'только чтение'")
    Future.sequence(selectedDictionaries.map(dictionary => backend.syncDownloadDictionary(CompositeId.fromObject(dictionary)))) foreach { _ => }
  }

  @JSExport
  def getPerspectivePermissions(perspective: Perspective): UndefOr[PerspectivePermissions] = {
    permissions.get(perspective.clientId).flatMap { e1 => e1.get(perspective.objectId)}.orUndefined
  }

  @JSExport
  def isDownloaded(dictionary: Dictionary): Boolean = {
    downloadedDictionaries.exists(_.getId == dictionary.getId)
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

      backend.desktopPerspectivePermissions() map { p =>
        permissions = p
        backend.getAvailableDesktopDictionaries map { languages =>
          backend.getAvailableDesktopPerspectives(published = true) map { perspectives =>
            Utils.flattenLanguages(languages).foreach { language =>
              language.dictionaries.foreach { dictionary =>
                dictionary.perspectives = perspectives.filter(perspective => perspective.parentClientId == dictionary.clientId && perspective.parentObjectId == dictionary.objectId).toJSArray
              }
            }
            backend.getDictionaries(DictionaryQuery()) map { dictionaries =>
              downloadedDictionaries = dictionaries
            }
            scope.languages = languages.toJSArray
            languages
          }
        }
      }
    }
  })
}
