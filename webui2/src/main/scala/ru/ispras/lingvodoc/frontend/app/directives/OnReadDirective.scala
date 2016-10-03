package ru.ispras.lingvodoc.frontend.app.directives

import com.greencatsoft.angularjs._
import com.greencatsoft.angularjs.core.Parse
import org.scalajs.dom.Element
import org.scalajs.dom.raw._
import org.scalajs.dom.console
import scala.scalajs.js.JSConverters._

import scala.scalajs.js
import scala.scalajs.js.typedarray.{ArrayBuffer, Uint8Array}

@injectable("onReadData")
class OnReadDirective(parse: Parse) extends AttributeDirective {

  override def link(scope: ScopeType, elems: Seq[Element], attrs: Attributes): Unit = {
    // input element
    val input = elems.head.asInstanceOf[HTMLInputElement]
    val expr = attrs("onReadData").get

    // this handler is invoked every time user selects a new file
    val onchangeHandler = (event: Event) => {
      if (input.files.length > 0) {
        val file = input.files(0)
        val fn = parse(expr)
        fn(scope, js.Dynamic.literal("$file" -> file))
      }
    }
    input.onchange = onchangeHandler
  }
}






















