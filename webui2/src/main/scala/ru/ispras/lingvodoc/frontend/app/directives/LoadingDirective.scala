package ru.ispras.lingvodoc.frontend.app.directives

import com.greencatsoft.angularjs.{AttributeDirective, Attributes, injectable}
import org.scalajs.dom._
import scala.scalajs.js.timers._

@injectable("loadingData")
class LoadingDirective() extends AttributeDirective {

  override def link(scope: ScopeType, elems: Seq[Element], attrs: Attributes): Unit = {
    val loaderElement = elems.head
    import org.scalajs.jquery.jQuery

    scope.$on("loader.show", () => {
      jQuery(loaderElement).fadeIn(300)
    })

    scope.$on("loader.hide", () => {
      jQuery(loaderElement).delay(800).fadeOut(400)
    })
  }
}