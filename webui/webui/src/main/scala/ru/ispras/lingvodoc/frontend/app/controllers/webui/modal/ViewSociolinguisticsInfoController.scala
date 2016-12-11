package ru.ispras.lingvodoc.frontend.app.controllers.webui.modal

import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import ru.ispras.lingvodoc.frontend.app.controllers.traits.LoadingPlaceholder
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, ModalInstance}
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.annotation.{JSExport, JSExportAll}
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.UndefOr


@JSExportAll
case class QuizElement(question: String, answer: String)


@js.native
trait ViewSociolinguisticsInfoScope extends Scope {
  var entry: SociolinguisticsEntry = js.native
  var quiz: js.Array[QuizElement] = js.native
  var pageLoaded: Boolean = js.native
}

@injectable("ViewSociolinguisticsInfoController")
class ViewSociolinguisticsInfoController(scope: ViewSociolinguisticsInfoScope,
                                         instance: ModalInstance[Option[LatLng]],
                                         backend: BackendService,
                                         val timeout: Timeout,
                                         val exceptionHandler: ExceptionHandler,
                                         params: js.Dictionary[js.Function0[js.Any]])
  extends AbstractController[ViewSociolinguisticsInfoScope](scope)
    with AngularExecutionContextProvider
    with LoadingPlaceholder {

  private[this] var languages = Seq[Language]()
  private[this] var dictionaries = Seq[Dictionary]()
  private[this] var perspectives = Seq[Perspective]()

  scope.entry = params("entry").asInstanceOf[SociolinguisticsEntry]
  scope.quiz = js.Array[QuizElement]()
  scope.pageLoaded = false


  private[this] def getPerspective(perspectiveId: CompositeId): Option[Perspective] = {
    perspectives.find(_.getId == perspectiveId.getId)
  }

  @JSExport
  def getQuestionsAnswers(sociolinguisticsEntry: SociolinguisticsEntry): js.Array[QuizElement] = {
    sociolinguisticsEntry.questions.map(q => QuizElement(q._1, q._2)).toSeq.toJSArray
  }

  @JSExport
  def getPerspectives(sociolinguisticsEntry: SociolinguisticsEntry): js.Array[Perspective] = {
    sociolinguisticsEntry.perspectives.flatMap(p => getPerspective(p)).toJSArray
  }

  @JSExport
  def getPerspectiveFullName(perspective: Perspective): UndefOr[String] = {
    dictionaries.find(d => d.clientId == perspective.parentClientId && d.objectId == perspective.parentObjectId).flatMap { dictionary =>
      languages.find(language => language.clientId == dictionary.parentClientId && language.objectId == dictionary.parentObjectId) map { language =>
        s"${language.translation} / ${dictionary.translation} / ${perspective.translation}"
      }
    }.orUndefined
  }

  @JSExport
  def close(): Unit = {
    instance.dismiss(())
  }

  doAjax(() => {
    backend.getLanguages flatMap { langs =>
      languages = Utils.flattenLanguages(langs)
      backend.getDictionaries(DictionaryQuery()) flatMap { dicts =>
        dictionaries = dicts
        backend.perspectives() map { persps =>
          perspectives = persps
          scope.quiz = getQuestionsAnswers(scope.entry)
        }
      }
    }
  })

  override protected def onLoaded[T](result: T): Unit = {}

  override protected def onError(reason: Throwable): Unit = {}

  override protected def preRequestHook(): Unit = {
    scope.pageLoaded = false
  }

  override protected def postRequestHook(): Unit = {
    scope.pageLoaded = true
  }
}
