package ru.ispras.lingvodoc.frontend.app.directives

import com.greencatsoft.angularjs.core._
import com.greencatsoft.angularjs._
import org.scalajs.dom.Element
import org.scalajs.dom.raw.MouseEvent

import scala.scalajs.js
import com.greencatsoft.angularjs.core.Promise

@injectable("clickAndHold")
class ClickAndHoldDirective(parse: Parse, timeout: Timeout) extends AttributeDirective {

  override def link(scope: ScopeType, elements: Seq[Element], attrs: Attributes): Unit = {

    import org.scalajs.dom.html

    val element: html.Element = elements.head.asInstanceOf[html.Element]
    var activeTimeout: Option[Promise[Unit]] = Option.empty

    element.onmousedown = (event: MouseEvent) => {
      activeTimeout = Some(timeout(() =>{
        val handler: Option[parse.ParsedExpression] = attrs("clickAndHold").toOption.map(parse(_))
        handler.foreach(_(scope, js.Dynamic.literal()))
      }, 2000))
    }

    element.onmouseup = (event: MouseEvent) => {
      activeTimeout.foreach { p =>
        timeout.cancel(p)
      }
    }
  }

}
