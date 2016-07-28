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

// Represents ELAN (EAF) document
class ELANDocumentJquery private(annotDocXML: JQuery) {
  // attributes
  val date = RequiredXMLAttr(annotDocXML, ELANDocumentJquery.dateAttrName)
  val author = RequiredXMLAttr(annotDocXML, ELANDocumentJquery.authorAttrName)
  val version = RequiredXMLAttr(annotDocXML, ELANDocumentJquery.versionAttrName)
  val format = RequiredXMLAttr(annotDocXML, ELANDocumentJquery.formatAttrName, defaultValue = Some("2.7"))

  val header = new Header(annotDocXML.find(Header.tagName))

  val timeOrder = new TimeOrder(annotDocXML.find(TimeOrder.tagName))
  var tiers = Tier.fromXMLs(annotDocXML.find(Tier.tagName))

  //  var linguisticType = LinguisticType("", graphicReferences = false, typeAlignable = false)
  //    var locale = Locale("", "", "")
  //    var tiers = List[Tier]()

  def content = s"$header $timeOrder ${tiers.mkString("\n")}"
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
  val xmlnsXsi = RequiredXMLAttr("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
  val schemaLoc = RequiredXMLAttr("xsi:noNamespaceSchemaLocation", "http://www.mpi.nl/tools/elan/EAFv2.7.xsd")
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
  val timeUnits = RequiredXMLAttr("TIME_UNITS", "milliseconds")
}

// Represents MEDIA_DESCRIPTOR element
class MediaDescriptor (mdXML: JQuery) {
  val mediaURL = RequiredXMLAttr(mdXML, MediaDescriptor.muAttrName)
  val mimeType = RequiredXMLAttr(mdXML, MediaDescriptor.mtAttrName)
  val relativeMediaUrl = OptionalXMLAttr(mdXML, MediaDescriptor.rmuAttrName)
  val timeOrigin = OptionalXMLAttr(mdXML, MediaDescriptor.toAttrName, converter = Some((v: String) => v.toLong))
  val extractedFrom = OptionalXMLAttr(mdXML, MediaDescriptor.efAttrName)

  override def toString = s"<${MediaDescriptor.tagName} $mediaURL $mimeType $relativeMediaUrl $timeOrigin $extractedFrom/>\n"
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
class LinkedFileDescriptor private(lfdXML: JQuery) {
  val linkURL = RequiredXMLAttr(lfdXML, LinkedFileDescriptor.luAttrName)
  val mimeType = RequiredXMLAttr(lfdXML, LinkedFileDescriptor.mtAttrName)
  val relativeLinkURL = OptionalXMLAttr(lfdXML, LinkedFileDescriptor.rluAttrName)
  val timeOrigin = OptionalXMLAttr(lfdXML, LinkedFileDescriptor.toAttrName, converter = Some((v: String) => v.toLong))
  val associatedWith = OptionalXMLAttr(lfdXML, LinkedFileDescriptor.awAttrName)

  override def toString = s"<${LinkedFileDescriptor.tagName} $linkURL $mimeType $relativeLinkURL $timeOrigin $associatedWith/>\n"
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

// Represents TIME_ORDER element
class TimeOrder(timeOrderXML: JQuery) {
  var timeSlots = Utils.jQuery2List(timeOrderXML.find(TimeOrder.tsTagName)).map(tsJquery => {
    tsJquery.attr(TimeOrder.tsIdAttrName).get -> tsJquery.attr(TimeOrder.tvAttrName).toOption
  }).toMap // timeslots without values are allowed
  def content = timeSlots.map{ case (id, value) =>
    s"<${TimeOrder.tsTagName} ${new RequiredXMLAttr(id) { val name = TimeOrder.tsIdAttrName }} ${ new OptionalXMLAttr(value) { val name = TimeOrder.tvAttrName }}/>"}
  override def toString = Utils.wrap(TimeOrder.tagName, content.mkString("\n"))
}

object TimeOrder {
  val (tagName, tsTagName, tsIdAttrName, tvAttrName) = ("TIME_ORDER", "TIME_SLOT", "TIME_SLOT_ID", "TIME_VALUE")
}

// Represents Tier element
class Tier(tierXML: JQuery) {
  val tierID = RequiredXMLAttr(tierXML, Tier.tIDAttrName)
  val linguisticTypeRef = RequiredXMLAttr(tierXML, Tier.lTypeRefAttrName)
  val participant = OptionalXMLAttr(tierXML, Tier.parRefAttrName)
  val annotator = OptionalXMLAttr(tierXML, Tier.annotAttrName)
  val defaultLocale = OptionalXMLAttr(tierXML, Tier.defLocAttrName)
  val parentRef = OptionalXMLAttr(tierXML, Tier.parRefAttrName)

  var annotations: List[Annotation] = Utils.jQuery2List(tierXML.find(Annotation.tagName)).map(Annotation(_))

  def attrsToString = s"$tierID $linguisticTypeRef $participant $annotator $defaultLocale $parentRef"
  override def toString = Utils.wrap(Tier.tagName, annotations.mkString("\n"), attrsToString)
}

object Tier {
  def fromXMLs(tiers: JQuery) = Utils.jQuery2List(tiers).map(new Tier(_))
  val (tagName, tIDAttrName, lTypeRefAttrName, partAttrName, annotAttrName, defLocAttrName, parRefAttrName) = (
    "TIER", "TIER_ID", "LINGUISTIC_TYPE_REF", "PARTICIPANT", "ANNOTATOR", "DEFAULT_LOCALE", "PARENT_REF"
    )
}

// Represents Annotation element
class Annotation private(val annotation: Either[AlignableAnnotation, RefAnnotation]) {
  override def toString = Utils.wrap(Annotation.tagName, annotation.fold(identity, identity).toString)
}

object Annotation {
  // ANNOTATION contains only one element, it is either alignable or ref annotation
  def apply(annotationXML: JQuery) = {
    val includedAnnotationXML = annotationXML.children().first()
    val annotation = includedAnnotationXML.prop("tagName").toString match {
      case AlignableAnnotation.tagName => Left(new AlignableAnnotation(includedAnnotationXML))
      case RefAnnotation.tagName => Right(new RefAnnotation(includedAnnotationXML))
    }
    new Annotation(annotation)
  }
  val tagName = "ANNOTATION"
}

class AlignableAnnotation(alignAnnotXML: JQuery) extends AnnotationAttributeGroup(alignAnnotXML) {
  val timeSlotRef1 = RequiredXMLAttr(alignAnnotXML, AlignableAnnotation.tsRef1AttrName)
  val timeSlotRef2 = RequiredXMLAttr(alignAnnotXML, AlignableAnnotation.tsRef2AttrName)
  val svgRef = OptionalXMLAttr(alignAnnotXML, AlignableAnnotation.svgRefAttrName)
  var text = alignAnnotXML.find(AlignableAnnotation.annotValueElName).text()

  def content = Utils.wrap(AlignableAnnotation.annotValueElName, text)
  override def toString = Utils.wrap(AlignableAnnotation.tagName, content,
    s"${super.toString} $timeSlotRef1 $timeSlotRef2 $svgRef")
}

object AlignableAnnotation {
  val (tagName, tsRef1AttrName, tsRef2AttrName, svgRefAttrName, annotValueElName) =
    ("ALIGNABLE_ANNOTATION", "TIME_SLOT_REF1", "TIME_SLOT_REF2", "SVG_REF", "ANNOTATION_VALUE")
}

class RefAnnotation(refAnnotXML: JQuery) extends AnnotationAttributeGroup(refAnnotXML)

object RefAnnotation {
  val (tagName) = ("REF_ANNOTATION")
}

// represents annotationAttribut attribute group
class AnnotationAttributeGroup(includedAnnotationXML: JQuery) {
  val annotationID = RequiredXMLAttr(includedAnnotationXML, AnnotationAttributeGroup.annotIDAttrName)
  val extRef = OptionalXMLAttr(includedAnnotationXML, AnnotationAttributeGroup.extRefAttrName)

  override def toString = s"$annotationID $extRef"
}

object AnnotationAttributeGroup {
  val (annotIDAttrName, extRefAttrName) = ("ANNOTATION_ID", "EXT_REF")
}

// this trait and two its descendants wrap XML attribute providing convenient toString method
trait XMLAttr { val name: String }

abstract class RequiredXMLAttr[T](var value: T) extends XMLAttr {
  override def toString = name + "=\"" + value + "\""
}

object RequiredXMLAttr {
  def apply[T](_name: String, _value: T) = new RequiredXMLAttr(_value) { val name = _name }

  // Read attribute's value from Jquery element
  def apply[T](jqEl: JQuery, name: String, defaultValue: Option[T] = None, converter: Option[String => T] = None): RequiredXMLAttr[T] = {
    // this is a required attr; if xml node doesn't have it, it must be provided as a default value
    val value = OptionalXMLAttr(jqEl, name, converter).value.getOrElse(defaultValue.get)
    RequiredXMLAttr(name, value)
  }
}

abstract class OptionalXMLAttr[T](var value: Option[T]) extends XMLAttr {
  override def toString = value.fold("") { name + "=\"" + _ + "\"" } // yes, it is just getOrElse :)
  // set attr2 value if it exists
  def updateValue(attr2: OptionalXMLAttr[T]) { value = attr2.value orElse value }
}

object OptionalXMLAttr {
  def apply[T](_name: String, _value: Option[T]) = new OptionalXMLAttr(_value) { val name = _name }

  // Read attribute's value from Jquery element
  def apply[T](jqEl: JQuery, name: String, converter: Option[String => T] = None): OptionalXMLAttr[T] = {
    val valOpt = jqEl.attr(name).toOption
    val valOptConverted = converter match {
      case Some(conv) => valOpt.map(v => conv(v))
      case None => valOpt.asInstanceOf[Option[T]] // No converter ~ the value is String
    }
    OptionalXMLAttr(name, valOptConverted)
  }
}