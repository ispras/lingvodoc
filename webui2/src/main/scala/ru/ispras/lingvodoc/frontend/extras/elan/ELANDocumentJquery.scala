package ru.ispras.lingvodoc.frontend.extras.elan

import java.util.NoSuchElementException

import org.scalajs.dom
import org.scalajs.jquery._
import org.scalajs.dom.console

import scala.collection.immutable.HashMap

case class ELANPArserException(message: String) extends Exception(message)

/**
  * Mutable data is used everywhere since it is more handy for user interaction
  */

// there are some more currently unsupported elements TODO
//case class Locale(countryCode: String, languageCode: String, variant: String) {
//  def toXMLString: String =
//      s|<LOCALE COUNTRY_CODE=$countryCode LANGUAGE_CODE=$languageCode/>
//       """.stripMargin
//}

// FIXME
case class LinguisticType(id: String, graphicReferences: Boolean, typeAlignable: Boolean) {
  def toXMLString: String =
    s"""|<LINGUISTIC_TYPE GRAPHIC_REFERENCES="${graphicReferences.toString}"
        |  LINGUISTIC_TYPE_ID=$id TIME_ALIGNABLE="${typeAlignable.toString}"/>
    """.stripMargin
}


class ELANDocumentJquery private(annotDocXML: JQuery) {
  val (date, author, version, format) = parseAttrs(annotDocXML)
  val header = new Header(annotDocXML.find(Header.tagName))
  val timeOrder = new TimeOrder(annotDocXML.find(TimeOrder.tagName)) // timeslots without values are allowed

  //  var linguisticType = LinguisticType("", graphicReferences = false, typeAlignable = false)
  //    var locale = Locale("", "", "")
  //    var tiers = List[Tier]()


  private def parseAttrs(annotDocXML: JQuery) = (
    new RequiredXMLAttr(annotDocXML.attr(ELANDocumentJquery.dateAttrName).get) { val name = ELANDocumentJquery.dateAttrName },
    new RequiredXMLAttr(annotDocXML.attr(ELANDocumentJquery.authorAttrName).get) { val name = ELANDocumentJquery.authorAttrName },
    new RequiredXMLAttr(annotDocXML.attr(ELANDocumentJquery.versionAttrName).get) { val name = ELANDocumentJquery.versionAttrName },
    new RequiredXMLAttr(annotDocXML.attr(ELANDocumentJquery.formatAttrName).toOption.getOrElse("2.7")) { val name = ELANDocumentJquery.formatAttrName }
    )

  def content = s"$header $timeOrder"
  def attrs = s"$date $author $version $format ${ELANDocumentJquery.xmlnsXsi} ${ELANDocumentJquery.schemaLoc}"

  override def toString =
    s"""|<?xml version="1.0" encoding="UTF-8"?>
        |${Utils.wrap(ELANDocumentJquery.annotDocTagName, content, attrs)}
    """.stripMargin
}

object ELANDocumentJquery {
  val annotDocTagName = "ANNOTATION_DOCUMENT"
  val (dateAttrName, authorAttrName, versionAttrName, formatAttrName) = ("DATE", "AUTHOR", "VERSION", "FORMAT")
  // hardcoded, expected not to change
  val xmlnsXsi = new RequiredXMLAttr("http://www.w3.org/2001/XMLSchema-instance") { val name = "xmlns:xsi" }
  val schemaLoc = new RequiredXMLAttr("http://www.mpi.nl/tools/elan/EAFv2.7.xsd") { val name = "xsi:noNamespaceSchemaLocation"}
  // see http://www.mpi.nl/tools/elan/EAF_Annotation_Format.pdf for format specification
  // JQuery is used for parsing.
  // WARNING: it is assumed that the xmlString is a valid ELAN document matching xsd scheme.
  // Otherwise the result is undefined.
  def apply(xmlString: String) = new ELANDocumentJquery(jQuery(jQuery.parseXML(xmlString)).find(annotDocTagName))
}

// Represents HEADER element
class Header(headerXML: JQuery) {
  headerXML.attr(Header.mfAttrName).foreach(mf => console.log(s"WARN: ${Header.mfAttrName} attribute is deprecated and ignored by ELAN"))
  headerXML.attr(Header.timeUnits.name).filterNot(_ == Header.timeUnits.value).
    foreach(mf => console.log(s"WARN: ${Header.timeUnits.name} are always ${Header.timeUnits.value} in ELAN"))
  val mediaDescriptor = MediaDescriptor.fromMultiple(headerXML.find(MediaDescriptor.tagName))
  val linkedFileDescriptor = LinkedFileDescriptor.fromMultiple(headerXML.find(LinkedFileDescriptor.tagName))
  val props = Utils.jQuery2XML(headerXML.find(Header.propTagName)) // User-defined properties
  override def toString: String =
    Utils.wrap(Header.tagName,
      s"${mediaDescriptor.getOrElse("")} ${linkedFileDescriptor.getOrElse("")} $props",
      Header.timeUnits.toString)
}

object Header {
  val (tagName, mfAttrName, propTagName) = ("HEADER", "MEDIA_FILE", "PROPERTY")
  val timeUnits = new RequiredXMLAttr("milliseconds") { val name = "TIME_UNITS" }
}

// Represents MEDIA_DESCRIPTOR element
class MediaDescriptor private(val mediaURL: RequiredXMLAttr[String], val mimeType: RequiredXMLAttr[String],
                              val relativeMediaUrl: OptionalXMLAttr[String], val timeOrigin: OptionalXMLAttr[Long],
                              val extractedFrom: OptionalXMLAttr[String]) {
  override def toString = s"<${MediaDescriptor.tagName} $mediaURL $mimeType $relativeMediaUrl $timeOrigin $extractedFrom/>\n"
  def join(md2: MediaDescriptor): MediaDescriptor = {   // take optional attrs from md2, if they absent here
    relativeMediaUrl.updateValue(md2.relativeMediaUrl)
    timeOrigin.updateValue(md2.timeOrigin)
    extractedFrom.updateValue(md2.extractedFrom)
    this
  }
}

object MediaDescriptor {
  // there can be more than one MD tag; the last tag gets the priority
  def fromMultiple(mdXMLs: JQuery): Option[MediaDescriptor] =
    Utils.jQuery2List(mdXMLs).foldLeft[Option[MediaDescriptor]](None) {
      (acc, newMd) => Some(MediaDescriptor(newMd)) ++ acc reduceOption (_ join _)
    }
  def apply(mdXML: JQuery): MediaDescriptor = {
    new MediaDescriptor(new RequiredXMLAttr(mdXML.attr(muAttrName).get) { val name = muAttrName },
      new RequiredXMLAttr(mdXML.attr(mtAttrName).get) { val name = mtAttrName },
      new OptionalXMLAttr(mdXML.attr(rmuAttrName).toOption) { val name = rmuAttrName },
      new OptionalXMLAttr(mdXML.attr(toAttrName).toOption.map(_.toLong)) { val name = toAttrName },
      new OptionalXMLAttr(mdXML.attr(efAttrName).toOption) { val name = efAttrName }
    )
  }
  val (tagName, muAttrName, mtAttrName, rmuAttrName, toAttrName, efAttrName) =
    ("MEDIA_DESCRIPTOR", "MEDIA_URL", "MIME_TYPE", "RELATIVE_MEDIA_URL", "TIME_ORIGIN", "EXTRACTED_FROM")
}

// Represents LINKED_FILE_DESCRIPTOR element
class LinkedFileDescriptor private(val linkURL: RequiredXMLAttr[String], val mimeType: RequiredXMLAttr[String],
                                   val relativeLinkURL: OptionalXMLAttr[String], val timeOrigin: OptionalXMLAttr[Long],
                                   val associatedWith: OptionalXMLAttr[String]) {
  override def toString = s"<${LinkedFileDescriptor.tagName} $linkURL $mimeType $relativeLinkURL $timeOrigin $associatedWith/>\n"
  def join(lfd2: LinkedFileDescriptor): LinkedFileDescriptor = { // take optional attrs from lfd2, if they absent here
    relativeLinkURL.updateValue(lfd2.relativeLinkURL)
    timeOrigin.updateValue(lfd2.timeOrigin)
    associatedWith.updateValue(lfd2.associatedWith)
    this
  }
}

object LinkedFileDescriptor {
  def fromMultiple(lfdXMLs: JQuery) =
    Utils.jQuery2List(lfdXMLs).foldLeft[Option[LinkedFileDescriptor]](None) {
      (acc, newLfd) => Some(LinkedFileDescriptor(newLfd)) ++ acc reduceOption (_ join _)
    }
  def apply(lfdXML: JQuery): LinkedFileDescriptor = {
    new LinkedFileDescriptor(new RequiredXMLAttr(lfdXML.attr(luAttrName).get) { val name = luAttrName },
      new RequiredXMLAttr(lfdXML.attr(mtAttrName).get) { val name = mtAttrName },
      new OptionalXMLAttr(lfdXML.attr(rluAttrName).toOption) { val name = rluAttrName},
      new OptionalXMLAttr(lfdXML.attr(toAttrName).toOption.map(_.toLong)) { val name = toAttrName},
      new OptionalXMLAttr(lfdXML.attr(awAttrName).toOption) { val name = awAttrName }
    )
  }
  val (tagName, luAttrName, mtAttrName, rluAttrName, toAttrName, awAttrName) = ("LINKED_FILE_DESCRIPTOR", "LINK_URL",
    "MIME_TYPE", "RELATIVE_LINK_URL", "TIME_ORIGIN", "ASSOCIATED_WITH")
}

// Represents TIME_ORDER element
class TimeOrder(timeOrderXML: JQuery) {
  var timeSlots = Utils.jQuery2List(timeOrderXML.find(TimeOrder.tsTagName)).map(tsJquery => {
    tsJquery.attr(TimeOrder.tsIdAttrName).get -> tsJquery.attr(TimeOrder.tvAttrName).toOption
  }).toMap
  def content = timeSlots.map{ case (id, value) =>
    s"<${TimeOrder.tsTagName} ${new RequiredXMLAttr(id) { val name = TimeOrder.tsIdAttrName }} ${ new OptionalXMLAttr(value) { val name = TimeOrder.tvAttrName }}/>"}
  override def toString = Utils.wrap(TimeOrder.tagName, content.mkString("\n"))
}

object TimeOrder {
  val (tagName, tsTagName, tsIdAttrName, tvAttrName) = ("TIME_ORDER", "TIME_SLOT", "TIME_SLOT_ID", "TIME_VALUE")
}

// this trait and two its descendants wrap XML attribute providing convenient toString method
trait XMLAttr { val name: String }

abstract class RequiredXMLAttr[T](var value: T) extends XMLAttr {
  override def toString = name + "=\"" + value + "\""
}

abstract class OptionalXMLAttr[T](var value: Option[T]) extends XMLAttr {
  override def toString = value.fold("") { name + "=\"" + _ + "\"" } // yes, it is just getOrElse :)
  // set attr2 value if it exists
  def updateValue(attr2: OptionalXMLAttr[T]) { value = attr2.value orElse value }
}