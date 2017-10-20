package ru.ispras.lingvodoc.frontend.app.directives

import com.greencatsoft.angularjs._
import com.greencatsoft.angularjs.core.Parse
import org.scalajs.dom.Element
import org.scalajs.dom.raw._

import scala.scalajs.js

@injectable("onReadFile")
class OnReadFileDirective(parse: Parse) extends AttributeDirective {

  override def link(scope: ScopeType, elems: Seq[Element], attrs: Attributes): Unit = {

    // input element
    val input = elems.head.asInstanceOf[HTMLInputElement]
    val expr = attrs("onReadFile").get

    // this handler is invoked every time user selects a new file
    val onchangeHandler = (event: Event) => {
      val file = input.files(0)
      //      val reader = new FileReader()
      //
      //      reader.onload = (e: UIEvent) => {
      //        val encodingName = "base64"
      //        val dataUrl = reader.result.asInstanceOf[String]
      //        val  encodingNameIndex = dataUrl.indexOf(encodingName)
      //        val base64content = dataUrl.substring(encodingNameIndex + encodingName.length + 1)
      //
      //        val fn = parse(expr)
      //        fn(scope, js.Dynamic.literal("$fileName" -> file.name, "$fileType" -> file.`type`, "$fileContent" -> base64content))
      //      }

      //      reader.readAsDataURL(file)

      val fn = parse(expr)
      fn(scope, js.Dynamic.literal("$file" -> file))
    }

    input.onchange = onchangeHandler
  }
}






















