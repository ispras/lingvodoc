package ru.ispras.lingvodoc.frontend.extras.elan

import org.scalajs.dom._
import org.scalajs.jquery.JQuery

import scala.scalajs.js.annotation.JSExportAll

// Represents HEADER element
@JSExportAll
class Header(headerXML: JQuery) {
  headerXML.attr(Header.mfAttrName).foreach(mf => console.log(s"WARN: ${Header.mfAttrName} attribute is deprecated and ignored by ELAN"))
  headerXML.attr(Header.timeUnits.name).filterNot(_ == Header.timeUnits.value).
    foreach(mf => console.log(s"WARN: ${Header.timeUnits.name} are always ${Header.timeUnits.value} in ELAN"))
  val mediaDescriptor = MediaDescriptor.fromMultiple(headerXML.find(MediaDescriptor.tagName))
  val linkedFileDescriptor = LinkedFileDescriptor.fromMultiple(headerXML.find(LinkedFileDescriptor.tagName))
  var props = parseProps(Utils.jQuery2List(headerXML.find(Header.propTagName)))

  // parse user-defined properties into Map and back into String
  private def parseProps(propXMLs: List[JQuery]): Map[String, String] =
    propXMLs.map(propXML => propXML.attr("NAME").get -> propXML.text).toMap
  private def propsToString = props map {case (k, v) =>
    Utils.wrap(Header.propTagName, v, RequiredXMLAttr(Header.propAttrName, k).toString)
  } mkString "\n"

  private def content = s"${mediaDescriptor.getOrElse("")} ${linkedFileDescriptor.getOrElse("")} $propsToString"
  override def toString: String = Utils.wrap(Header.tagName, content, Header.timeUnits.toString)
}

object Header {
  val (tagName, mfAttrName, propTagName, propAttrName) = ("HEADER", "MEDIA_FILE", "PROPERTY", "NAME")
  val (lastUsedTimeSlotIDPropName, lastUsedAnnotIDPropName) = ("lingvodocLastUsedTimeSlotID", "lingvodocLastUsedAnnotationID")
  val timeUnits = RequiredXMLAttr("TIME_UNITS", "milliseconds")
}

// Represents MEDIA_DESCRIPTOR element
@JSExportAll
class MediaDescriptor (mdXML: JQuery) {
  val mediaURL = RequiredXMLAttr(mdXML, MediaDescriptor.muAttrName)
  val mimeType = RequiredXMLAttr(mdXML, MediaDescriptor.mtAttrName)
  val relativeMediaUrl = OptionalXMLAttr(mdXML, MediaDescriptor.rmuAttrName)
  val timeOrigin = OptionalXMLAttr(mdXML, MediaDescriptor.toAttrName, _.toLong)
  val extractedFrom = OptionalXMLAttr(mdXML, MediaDescriptor.efAttrName)

  override def toString = s"<${MediaDescriptor.tagName} $mediaURL $mimeType $relativeMediaUrl $timeOrigin $extractedFrom/>"
  def join(md2: MediaDescriptor): MediaDescriptor = {   // take optional attrs from md2, if they absent here
    relativeMediaUrl.updateValue(md2.relativeMediaUrl)
    timeOrigin.updateValue(md2.timeOrigin)
    extractedFrom.updateValue(md2.extractedFrom)
    this
  }
}

object MediaDescriptor {
  def apply(mdXML: JQuery) = new MediaDescriptor(mdXML)
  // there can be more than one MD tag; the last tag gets the priority
  def fromMultiple(mdXMLs: JQuery) = Utils.fromMultiple[MediaDescriptor](mdXMLs, MediaDescriptor.apply, _.join(_))
  val (tagName, muAttrName, mtAttrName, rmuAttrName, toAttrName, efAttrName) =
    ("MEDIA_DESCRIPTOR", "MEDIA_URL", "MIME_TYPE", "RELATIVE_MEDIA_URL", "TIME_ORIGIN", "EXTRACTED_FROM")
}

// Represents LINKED_FILE_DESCRIPTOR element
@JSExportAll
class LinkedFileDescriptor private(lfdXML: JQuery) {
  val linkURL = RequiredXMLAttr(lfdXML, LinkedFileDescriptor.luAttrName)
  val mimeType = RequiredXMLAttr(lfdXML, LinkedFileDescriptor.mtAttrName)
  val relativeLinkURL = OptionalXMLAttr(lfdXML, LinkedFileDescriptor.rluAttrName)
  val timeOrigin = OptionalXMLAttr(lfdXML, LinkedFileDescriptor.toAttrName, _.toLong)
  val associatedWith = OptionalXMLAttr(lfdXML, LinkedFileDescriptor.awAttrName)

  override def toString = s"<${LinkedFileDescriptor.tagName} $linkURL $mimeType $relativeLinkURL $timeOrigin $associatedWith/>"
  def join(lfd2: LinkedFileDescriptor): LinkedFileDescriptor = { // take optional attrs from lfd2, if they absent here
    relativeLinkURL.updateValue(lfd2.relativeLinkURL)
    timeOrigin.updateValue(lfd2.timeOrigin)
    associatedWith.updateValue(lfd2.associatedWith)
    this
  }
}

object LinkedFileDescriptor {
  def apply(lfdXML: JQuery) = new LinkedFileDescriptor(lfdXML)
  def fromMultiple(lfdXMLs: JQuery) = Utils.fromMultiple[LinkedFileDescriptor](lfdXMLs, LinkedFileDescriptor.apply, _.join(_))
  val (tagName, luAttrName, mtAttrName, rluAttrName, toAttrName, awAttrName) = ("LINKED_FILE_DESCRIPTOR", "LINK_URL",
    "MIME_TYPE", "RELATIVE_LINK_URL", "TIME_ORIGIN", "ASSOCIATED_WITH")
}
