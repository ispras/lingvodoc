package ru.ispras.lingvodoc.frontend.extras.elan

import java.util.NoSuchElementException

import org.scalajs.dom
import org.scalajs.jquery._
import org.scalajs.dom.console

trait XMLAttr { val name: String }

abstract class RequiredXMLAttr[T](val value: T) extends XMLAttr {
  override def toString = name + "=\"" + value + "\""
}

abstract class OptionalXMLAttr[T](val value: Option[T]) extends XMLAttr {
  override def toString = value.fold("") { name + "=\"" + _ + "\"" }
  // looks terrible
  def orElse(value2: OptionalXMLAttr[T]) = { new OptionalXMLAttr[T](value2.getValue orElse value) { val name = value2.name} }
  def getValue = value
}

case class ELANPArserException(message: String) extends Exception(message)

// FIXME
case class LinguisticType(id: String, graphicReferences: Boolean, typeAlignable: Boolean) {
  def toXMLString: String =
    s"""|<LINGUISTIC_TYPE GRAPHIC_REFERENCES="${graphicReferences.toString}"
        |  LINGUISTIC_TYPE_ID=$id TIME_ALIGNABLE="${typeAlignable.toString}"/>
    """.stripMargin
}

class MediaDescriptor private(val mediaURL: RequiredXMLAttr[String], val mimeType: RequiredXMLAttr[String],
                              val relativeMediaUrl: OptionalXMLAttr[String], val timeOrigin: OptionalXMLAttr[Long],
                              val extractedFrom: OptionalXMLAttr[String]) {
  def toXMLString: String = s"<${MediaDescriptor.tagName} $mediaURL $mimeType $relativeMediaUrl $timeOrigin $extractedFrom/>"
  def join(md2: MediaDescriptor) = {
    new MediaDescriptor(md2.mediaURL, md2.mimeType, md2.relativeMediaUrl orElse relativeMediaUrl, md2.timeOrigin orElse
      timeOrigin, md2.extractedFrom orElse extractedFrom)
  }
}

object MediaDescriptor {
  val (tagName, muAttrName, mtAttrName, rmuAttrName, toAttrName, efAttrName) =
    ("MEDIA_DESCRIPTOR", "MEDIA_URL", "MIME_TYPE", "RELATIVE_MEDIA_URL", "TIME_ORIGIN", "EXTRACTED_FROM")
  def apply(mdXML: JQuery): MediaDescriptor = {
      new MediaDescriptor(new RequiredXMLAttr(mdXML.attr(muAttrName).get) { val name = muAttrName },
                          new RequiredXMLAttr(mdXML.attr(mtAttrName).get) { val name = mtAttrName },
                          new OptionalXMLAttr(mdXML.attr(rmuAttrName).toOption) { val name = rmuAttrName },
                          new OptionalXMLAttr(mdXML.attr(toAttrName).toOption.map(_.toLong)) { val name = toAttrName },
                          new OptionalXMLAttr(mdXML.attr(efAttrName).toOption) { val name = efAttrName }
      )
  }
}

class LinkedFileDescriptor private(val linkURL: RequiredXMLAttr[String], val mimeType: RequiredXMLAttr[String],
                                   val relativeLinkURL: OptionalXMLAttr[String], val timeOrigin: OptionalXMLAttr[Long],
                                   val assosiatedWith: OptionalXMLAttr[String]) {
  def toXMLString: String = s"<${LinkedFileDescriptor.tagName} $linkURL $mimeType $relativeLinkURL $timeOrigin $assosiatedWith/>"
}

object LinkedFileDescriptor {
  val (tagName, luAttrName, mtAttrName, rluAttrName, toAttrName, awAttrName) = ("LINKED_FILE_DESCRIPTOR", "LINK_URL",
    "MIME_TYPE", "RELATIVE_LINK_URL", "TIME_ORIGIN", "ASSOCIATED_WITH")
  def apply(lfdXML: JQuery): LinkedFileDescriptor = {
    new LinkedFileDescriptor(new RequiredXMLAttr(lfdXML.attr(luAttrName).get) { val name = luAttrName },
                             new RequiredXMLAttr(lfdXML.attr(mtAttrName).get) { val name = mtAttrName },
                             new OptionalXMLAttr(lfdXML.attr(rluAttrName).toOption) { val name = rluAttrName},
                             new OptionalXMLAttr(lfdXML.attr(toAttrName).toOption.map(_.toLong)) { val name = toAttrName},
                             new OptionalXMLAttr(lfdXML.attr(awAttrName).toOption) { val name = awAttrName }
    )
  }
}

// there are some more currently unsupported elements TODO
//case class Locale(countryCode: String, languageCode: String, variant: String) {
//  def toXMLString: String =
//      s|<LOCALE COUNTRY_CODE=$countryCode LANGUAGE_CODE=$languageCode/>
//       """.stripMargin
//}

// see http://www.mpi.nl/tools/elan/EAF_Annotation_Format.pdf for format specification
// JQuery is used for parsing.
// WARNING: it is assumed that the xmlString is a valid ELAN document matching xsd scheme.
// Otherwise the result is undefined.
class ELANDocumentJquery(xmlString: String) {
  var author, date, version = ""
  var format = "2.7"
  val units = "milliseconds"
  var mediaDescriptor: Option[MediaDescriptor] = None
  var linkedFileDescriptor: Option[LinkedFileDescriptor] = None
  var timeSlots = Map[Int, String]()
  var linguisticType = LinguisticType("", graphicReferences = false, typeAlignable = false)
  //    var locale = Locale("", "", "")
  //    var tiers = List[Tier]()
  // users can add timeslots, so we will need new ids. Points to smallest available id
  private var _nextTimeSlotId = 0
  // global for all tiers -- it is more convenient since we can store custom fields only in HEAD->PROPERTIES
  private var _nextAnnotationId = 0

  importXML(jQuery(jQuery.parseXML(xmlString)))

  private def importXML(xml: JQuery): Unit = {
    val annotDocXML = xml.find("ANNOTATION_DOCUMENT")
    author = annotDocXML.attr("AUTHOR").get
    date = annotDocXML.attr("DATE").get
    version = annotDocXML.attr("VERSION").get
    annotDocXML.attr("FORMAT").foreach(format = _)

    val ourXML = importHeader(annotDocXML.find("HEADER"))
    val timeSlotsFromXML = parseTimeSlots(annotDocXML.find("TIME_ORDER"))
  }

  // returns true, if we have previously imported this xml at least once -- then next ids will be set
  private def importHeader(headerXML: JQuery): Boolean = {
    headerXML.attr("MEDIA_FILE").foreach(mf => console.log("WARN: MEDIA_FILE attribute is deprecated and ignored by ELAN"))

    val mdXML = headerXML.find(MediaDescriptor.tagName)
    mdXML.each((el: dom.Element) => { // there can be more than one MD tag; the last tag gets the priority
      val jqEl = jQuery(el) // working with jQuery is more handy since .attr returns Option
      mediaDescriptor = mediaDescriptor match {
        case None => Some(MediaDescriptor(jqEl))
        case Some(md) => Some(md join MediaDescriptor(jqEl))
      }
    })

    val lfdXML = headerXML.find(LinkedFileDescriptor.tagName)
    lfdXML.each((el: dom.Element) => { // there can be more than one LFD tag; the last tag gets the priority
      val jqEl = jQuery(el) // working with jQuery is more handy since .attr returns Option
      linkedFileDescriptor = linkedFileDescriptor match {
        case None => Some(LinkedFileDescriptor(jqEl))
        case Some(lfd) => Some(lfd)
      }
    })

    val nextTimeSlotIdNode = headerXML.find("PROPERTY[NAME='nextTimeSlotId']")
    val nextTimeAnnotationIdNode = headerXML.find("PROPERTY[NAME='nextAnnotationId']")
    if (nextTimeSlotIdNode.length > 1 || nextTimeAnnotationIdNode.length > 1)
      throw ELANPArserException("More than one nextTimeSlotIdNode or nextTimeAnnotationIdNode property")
    val ourXML = nextTimeSlotIdNode.length != 0 && nextTimeAnnotationIdNode.length != 0
    if (ourXML) {
      _nextTimeSlotId = nextTimeSlotIdNode.text.toInt
      _nextAnnotationId = nextTimeAnnotationIdNode.text.toInt
    }
    console.log(s"nextTimeSlotId is ${_nextTimeSlotId}")
    console.log(s"nextAnnotationId is ${_nextAnnotationId}")
    ourXML
  }

  private def parseTimeSlots(timeOrder: JQuery): Unit = {
    if (timeOrder.length == 0)
      throw ELANPArserException("No TIME_ORDER tag")
    timeOrder.each((el: dom.Element) => {
      val jqEl = jQuery(el)
      console.log(jqEl.text())
    })
  }
}

object ELANDocumentJquery {
  // convert JQuery object to XML string. This will not work if document starts with XML declaration <?xml...
  // see http://stackoverflow.com/questions/22647651/convert-xml-document-back-to-string-with-jquery
  // don't forget to call it on the cloned object, or it will be screwed up by additional tag!
   private def jQuery2XML(jq: JQuery): String = {
    jq.appendTo("<x></x>").parent().html()
  }
}
