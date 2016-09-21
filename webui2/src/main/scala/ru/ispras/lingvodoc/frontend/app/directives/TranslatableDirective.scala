package ru.ispras.lingvodoc.frontend.app.directives

import com.greencatsoft.angularjs._
import com.greencatsoft.angularjs.core.ModelController
import com.greencatsoft.angularjs.core.Parse
import org.scalajs.dom
import org.scalajs.dom.Element
import org.scalajs.dom.raw._
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import ru.ispras.lingvodoc.frontend.app.utils.Utils
import ru.ispras.lingvodoc.frontend.app.utils.LingvodocExecutionContext.Implicits.executionContext

import scala.scalajs.js.JSConverters._
import scala.util.{Failure, Success}


@injectable("translatable")
class TranslatableDirective(backend: BackendService) extends ElementDirective {

  var cachedTranslations = Map[String, String]()

  override def link(scope: ScopeType, elems: Seq[Element], attrs: Attributes): Unit = {
    val element = elems.head.asInstanceOf[HTMLElement]
    attrs("str") map {
      searchString =>
        if (cachedTranslations.keySet.contains(searchString)) {
          element.textContent = cachedTranslations(searchString)
        } else {
          backend.serviceTranslation(searchString) onComplete {
            case Success(gist) =>
              val localeId = Utils.getLocale().getOrElse(2)
              gist.atoms.find(_.localeId == localeId) foreach {
                atom => element.textContent = atom.content
                  element.textContent = atom.content
              }
            case Failure(e) =>
              console.log(searchString)
          }
        }
    }
  }
}
