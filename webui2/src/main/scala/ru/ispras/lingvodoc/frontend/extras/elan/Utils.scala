package ru.ispras.lingvodoc.frontend.extras.elan

import org.scalajs.dom
import org.scalajs.jquery._

import scala.collection.mutable.ListBuffer


object Utils {
  // convert JQuery object to XML string. This will not work if document starts with XML declaration <?xml...
  // see http://stackoverflow.com/questions/22647651/convert-xml-document-back-to-string-with-jquery
  // don't forget to call it on the cloned object, or it will be screwed up by additional tag!
  private[elan] def jQuery2XML(jq: JQuery): String = {
    jq.appendTo("<x></x>").parent().html()
  }

  // wrap @content with tags @tagName with optional @attrs
  private[elan] def wrap(tagName: String, content: String, attrs: String = "") =
    s"""|<$tagName $attrs>
        |  $content
        |</$tagName>
        |
     """.stripMargin

  // sometimes, when we search for the tag, we expect several results. They come in one JQuery object, and the only
  // way to traverse them is .each method. This method converts it to Scala List
  private[elan] def jQuery2List(jq: JQuery): List[JQuery] = {
    val buf = new ListBuffer[JQuery]
    jq.each((el: dom.Element) => {
      val jqEl = jQuery(el) // working with jQuery is more handy since .attr returns Option
      buf += jqEl
    })
    buf.toList
  }
}
