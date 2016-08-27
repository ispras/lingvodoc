package ru.ispras.lingvodoc.frontend.extras.elan

import org.scalajs.dom
import org.scalajs.jquery._

import scala.collection.mutable.ListBuffer


private [elan] object Utils {
  // convert JQuery object to XML string. This will not work if document starts with XML declaration <?xml...
  // see http://stackoverflow.com/questions/22647651/convert-xml-document-back-to-string-with-jquery
  def jQuery2XML(jq: JQuery): String = if (jq.length == 0)
      ""
    else {
      val jqCloned = jq.clone() // clone the object, since it will be screwed up by additional tag
      jqCloned.appendTo("<x></x>").parent().html()
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
  // TODO: perhaps several MEDIA_DESCRIPTORS make sense?
  def fromMultiple[T](xmls: JQuery, apply: (JQuery => T), join: (T, T) => T): Option[T] =
    Utils.jQuery2List(xmls).foldLeft[Option[T]](None) {
      (acc, newXML) => Some(apply(newXML)) ++ acc reduceOption (join(_, _))
  }
}

// this trait and two its descendants wrap XML attribute providing convenient toString method
trait XMLAttr { val name: String }

class RequiredXMLAttr[T](val name: String, var value: T) extends XMLAttr {
  override def toString = name + "=\"" + value + "\""
}

object RequiredXMLAttr {
  def apply[T](name: String, value: T) = new RequiredXMLAttr(name, value)

  // These methods attribute's value from Jquery element; if no converter supplied, attr type is String
  // we need this particular method only because Scala forbids two apply's with default values, see
  // "multiple overloaded alternatives of method apply define default arguments"
  def apply(jqEl: JQuery, name: String): RequiredXMLAttr[String] = RequiredXMLAttr(jqEl, name, None)
  def apply(jqEl: JQuery, name: String, defaultValue: Option[String]): RequiredXMLAttr[String] =
    RequiredXMLAttr(jqEl, name, defaultValue, identity)
  def apply[T](jqEl: JQuery, name: String, defaultValue: Option[T] = None, converter: String => T): RequiredXMLAttr[T] = {
    // this is a required attr; if xml node doesn't have it, it must be provided as a default value
    val value = OptionalXMLAttr(jqEl, name, converter).value.getOrElse(defaultValue.get)
    RequiredXMLAttr(name, value)
  }
}

class OptionalXMLAttr[T](val name: String, var value: Option[T]) extends XMLAttr {
  override def toString = value.fold("") { name + "=\"" + _ + "\"" } // yes, it is just getOrElse :)
  // set attr2 value if it exists
  def updateValue(attr2: OptionalXMLAttr[T]) { value = attr2.value orElse value }
}

object OptionalXMLAttr {
  def apply[T](name: String, value: Option[T]) = new OptionalXMLAttr(name, value)

  // Read attribute's value from Jquery element; if no converter supplied, attr type is String
  def apply(jQuery: JQuery, name: String): OptionalXMLAttr[String] = OptionalXMLAttr(jQuery, name, identity)
  def apply[T](jqEl: JQuery, name: String, converter: String => T): OptionalXMLAttr[T] = {
    val valOpt = jqEl.attr(name).toOption.map(converter(_))
    OptionalXMLAttr(name, valOpt)
  }
}

object XMLAttrConversions {
  implicit def requiredXMLAttr2Value[T](attr: RequiredXMLAttr[T]): T = attr.value
  implicit def optionalXMLAttr2Value[T](attr: OptionalXMLAttr[T]): Option[T] = attr.value
}
