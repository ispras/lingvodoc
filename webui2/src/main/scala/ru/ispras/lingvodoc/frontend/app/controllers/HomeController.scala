package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.Scope
import com.greencatsoft.angularjs.{AbstractController, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.api.exceptions.BackendException
import ru.ispras.lingvodoc.frontend.app.model.{Language, Perspective}
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import ru.ispras.lingvodoc.frontend.app.utils.LingvodocExecutionContext.Implicits.executionContext

import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}


@js.native
trait HomeScope extends Scope {
  var languages: js.Array[Language] = js.native
}

@injectable("HomeController")
class HomeController(scope: HomeScope, backend: BackendService) extends AbstractController[HomeScope](scope) {

  @JSExport
  def getPerspectiveAuthors(perspective: Perspective): String = {
    "Metadata is not supported!"
  }

  private[this] def setPerspectives(languages: Seq[Language]): Unit = {
    for (language <- languages) {
      for (dictionary <- language.dictionaries) {
        backend.getPublishedDictionaryPerspectives(dictionary) onComplete {
          case Success(perspectives) => dictionary.perspectives = perspectives.toJSArray
          case Failure(e) =>
        }
      }
      setPerspectives(language.languages.toSeq)
    }
  }

  backend.getPublishedDictionaries onComplete {
    case Success(languages) =>
      console.log(languages.toJSArray)
      setPerspectives(languages)
      scope.languages = languages.toJSArray
    case Failure(e) => console.log(e.getMessage)
  }
}
