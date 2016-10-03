package ru.ispras.lingvodoc.frontend.app.directives

import com.greencatsoft.angularjs._
import org.scalajs.dom.{Element, console}
import org.scalajs.dom.raw._
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.concurrent.ExecutionContext.Implicits.global
import scala.scalajs.js
import scala.util.{Failure, Success}


@injectable("translatable")
class TranslatableDirective(backend: BackendService) extends ElementDirective with IsolatedScope {

  private[this] var cachedTranslations = Map[String, String]()
  private[this] val failedTranslations = js.Array[String]()

  private[this] def addFailedTranslation(str: String) = {
    failedTranslations.push(str)
    if (failedTranslations.indexOf(str) < 0) {
      console.log("addition failed?!")
    }
  }

  private[this] def isTranslationInFailedList(str: String): Boolean = {
    failedTranslations.contains(str)
  }

  override def link(scope: ScopeType, elems: Seq[Element], attrs: Attributes): Unit = {
    val element = elems.head.asInstanceOf[HTMLElement]
    attrs("str") map {
      searchString =>
        
        backend.serviceTranslation(searchString) onComplete {
          case Success(gist) =>
            val localeId = Utils.getLocale().getOrElse(2)
            gist.atoms.find(_.localeId == localeId) foreach {
              atom => element.textContent = atom.content
                element.textContent = atom.content
            }
          case Failure(e) =>
            addFailedTranslation(searchString)
        }
    }
  }
}
