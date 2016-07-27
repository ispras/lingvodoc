package ru.ispras.lingvodoc.frontend.extras.elan

import org.scalajs.dom
import org.scalajs.jquery._

import scala.collection.mutable.ListBuffer


private [elan] object Utils {
  // convert JQuery object to XML string. This will not work if document starts with XML declaration <?xml...
  // see http://stackoverflow.com/questions/22647651/convert-xml-document-back-to-string-with-jquery
  // don't forget to call it on the cloned object, or it will be screwed up by additional tag!
  def jQuery2XML(jq: JQuery): String = {
    jq.appendTo("<x></x>").parent().html()
  }

  // wrap @content with tags @tagName with optional @attrs
  def wrap(tagName: String, content: String, attrs: String = "") =
    s"""|<$tagName $attrs>
        |  $content
        |</$tagName>
        |
     """.stripMargin

  // sometimes, when we search for the tag, we expect several results. They come in one JQuery object, and the only
  // way to traverse them is .each method. This method converts the object into Scala List
  def jQuery2List(jq: JQuery): List[JQuery] = {
    val buf = new ListBuffer[JQuery]
    jq.each((el: dom.Element) => {
      val jqEl = jQuery(el) // working with jQuery is more handy since .attr returns Option
      buf += jqEl
    })
    buf.toList
  }

  // Some elements are allowed to appear multiple times, although they just set some values, so more than one
  // attribute value doesn't make sense. Examples are MEDIA_DESCRIPTOR and LINKED_FILE_DESCRIPTOR. In this case,
  // we will read all of them and perceive the last tag attrs as having highest priority. This method does the job:
  // it reads all of them sequentially and takes new values as it goes
  def fromMultiple[T](xmls: JQuery, apply: (JQuery => T), join: (T, T) => T): Option[T] =
    Utils.jQuery2List(xmls).foldLeft[Option[T]](None) {
      (acc, newXML) => Some(apply(newXML)) ++ acc reduceOption (join(_, _))
  }
}
