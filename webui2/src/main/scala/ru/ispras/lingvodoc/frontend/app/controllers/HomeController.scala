package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{Scope, Timeout}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import ru.ispras.lingvodoc.frontend.app.controllers.traits.LoadingPlaceholder
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.BackendService

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.{Any, UndefOr}
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}
import scala.scalajs.js.JSConverters._

import org.scalajs.dom.console


@js.native
trait HomeScope extends Scope {
  var languages: js.Array[Language] = js.native
  var authors: js.Array[js.Dynamic] = js.native
}

@JSExport
@injectable("HomeController")
class HomeController(scope: HomeScope, backend: BackendService, val timeout: Timeout)
  extends AbstractController[HomeScope](scope)
    with LoadingPlaceholder
    with AngularExecutionContextProvider {

  scope.languages = js.Array[Language]()
  scope.authors = js.Array[js.Dynamic]()

  @JSExport
  def getPerspectiveAuthors(perspective: Perspective): UndefOr[String] = {

    console.log(scope.authors.length)
    console.log(perspective.getId)

    scope.authors.find(_.id.asInstanceOf[String] == perspective.getId) match {
      case Some(x) => x.authors.asInstanceOf[String]
      case None => ""
    }
  }

  private[this] def setPerspectives(languages: Seq[Language]): Unit = {
    for (language <- languages) {
      for (dictionary <- language.dictionaries) {
        backend.getDictionaryPerspectives(dictionary, onlyPublished = true) onComplete {
          case Success(perspectives) =>
            dictionary.perspectives = perspectives.toJSArray

            perspectives.filter(_.metadata.nonEmpty).foreach(p => {
              backend.getPerspectiveMeta(p) map { meta =>
                meta.authors.foreach { authors =>
                  if (authors.authors.nonEmpty) {
                    scope.authors.push(js.Dynamic.literal("id" -> p.getId, "authors" -> authors.authors))
                  }
                }
              }
            })
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
    backend.allStatuses() map { _ =>
      backend.getPublishedDictionaries map { languages =>
          setPerspectives(languages)
          scope.languages = languages.toJSArray
          languages
      }
    }
  })
}
