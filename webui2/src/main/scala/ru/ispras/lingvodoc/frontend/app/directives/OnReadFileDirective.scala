package ru.ispras.lingvodoc.frontend.app.directives

import com.greencatsoft.angularjs._
import com.greencatsoft.angularjs.core.ModelController
import com.greencatsoft.angularjs.core.Parse
import org.scalajs.dom
import org.scalajs.dom.Element
import org.scalajs.dom.raw._
import org.scalajs.dom.console
import scala.scalajs.js.JSConverters._

import scala.scalajs.js
import scala.scalajs.js.typedarray.{ArrayBuffer, Uint8Array}

@injectable("onReadFile")
class OnReadFileDirective(parse: Parse) extends AttributeDirective {

  override def link(scope: ScopeType, elems: Seq[Element], attrs: Attributes): Unit = {

    // input element
    val input = elems.head.asInstanceOf[HTMLInputElement]
    val expr = attrs("onReadFile").get

    // this handler is invoked every time user selects a new file
    val onchangeHandler = (event: Event) => {
      val file = input.files(0)
      val reader = new FileReader()

      reader.onload = (e: UIEvent) => {
        val content = reader.result.asInstanceOf[ArrayBuffer]
        val arr = js.Array[Byte]()
        val c = new Uint8Array(content)
        for (i <- 0 until c.byteLength) {
          arr.push(c(i).toByte)
        }
        val str = new String(arr.toArray, "Latin1")
        val b64content = dom.window.btoa(str)

        val fn = parse(expr)
        fn(scope, js.Dynamic.literal("$fileName" -> file.name, "$fileType" -> file.`type`, "$fileContent" -> b64content))
      }

      reader.readAsArrayBuffer(file)
    }

    input.onchange = onchangeHandler
  }
}






















