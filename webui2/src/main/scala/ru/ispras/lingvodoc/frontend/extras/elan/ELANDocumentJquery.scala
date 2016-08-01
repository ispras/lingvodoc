package ru.ispras.lingvodoc.frontend.extras.elan

import org.scalajs.dom
import org.scalajs.jquery._
import org.scalajs.dom.console

import scala.collection.immutable.HashMap

/**
  * Mutable data is used everywhere since it is more handy for user interaction
  */

case class ELANPArserException(message: String) extends Exception(message)

// Represents ELAN (EAF) document
class ELANDocumentJquery private(annotDocXML: JQuery) {
  // attributes
  val date = RequiredXMLAttr(annotDocXML, ELANDocumentJquery.dateAttrName)
  val author = RequiredXMLAttr(annotDocXML, ELANDocumentJquery.authorAttrName)
  val version = RequiredXMLAttr(annotDocXML, ELANDocumentJquery.versionAttrName)
  val format = RequiredXMLAttr(annotDocXML, ELANDocumentJquery.formatAttrName, Some("2.7"))

  val header = new Header(annotDocXML.find(Header.tagName))

  val timeOrder = new TimeOrder(annotDocXML.find(TimeOrder.tagName))
  var tiers = Tier.fromXMLs(annotDocXML.find(Tier.tagName))
  var linguisticTypes = LinguisticType.fromXMLs(annotDocXML.find(LinguisticType.tagName))
  val locales = Locale.fromXMLs(annotDocXML.find(Locale.tagName))
  val constraints = Constraint.predefinedConstraints
  // the following 3 elements are not supported yet; we will just save them unchanged as a String
  val controlledVocabulary = Utils.jQuery2XML(annotDocXML.find(ELANDocumentJquery.controlledVocTagName))
  val lexiconRef = Utils.jQuery2XML(annotDocXML.find(ELANDocumentJquery.lexRefTagName))
  val externalRef = Utils.jQuery2XML(annotDocXML.find(ELANDocumentJquery.extRefTagName))

  def content = s"$header $timeOrder ${tiers.mkString("\n")} ${linguisticTypes.values.mkString("\n")} " +
                s"${locales.mkString("\n")} ${constraints.mkString("\n")}" +
                s"$controlledVocabulary $lexiconRef  $externalRef"
  def attrsToString = s"$date $author $version $format ${ELANDocumentJquery.xmlnsXsi} ${ELANDocumentJquery.schemaLoc}"

  override def toString =
    s"""|<?xml version="1.0" encoding="UTF-8"?>
        |${Utils.wrap(ELANDocumentJquery.annotDocTagName, content, attrsToString)}
    """.stripMargin
}

object ELANDocumentJquery {
  val annotDocTagName = "ANNOTATION_DOCUMENT"
  val (dateAttrName, authorAttrName, versionAttrName, formatAttrName) = ("DATE", "AUTHOR", "VERSION", "FORMAT")
  val (controlledVocTagName, lexRefTagName, extRefTagName) = ("CONTROLLED_VOCABULARY", "LEXICON_REF", "EXTERNAL_REF")
  // hardcoded, expected not to change
  val xmlnsXsi = RequiredXMLAttr("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
  val schemaLoc = RequiredXMLAttr("xsi:noNamespaceSchemaLocation", "http://www.mpi.nl/tools/elan/EAFv2.7.xsd")
  // see http://www.mpi.nl/tools/elan/EAF_Annotation_Format.pdf for format specification
  // JQuery is used for parsing.
  // WARNING: it is assumed that the xmlString is a valid ELAN document matching xsd scheme.
  // Otherwise the result is undefined.
  def apply(xmlString: String) = new ELANDocumentJquery(jQuery(jQuery.parseXML(xmlString)).find(annotDocTagName))
}

// Represents TIME_ORDER element
class TimeOrder(timeOrderXML: JQuery) {
  var timeSlots = Utils.jQuery2List(timeOrderXML.find(TimeOrder.tsTagName)).map(tsJquery => {
    tsJquery.attr(TimeOrder.tsIdAttrName).get -> tsJquery.attr(TimeOrder.tvAttrName).toOption
  }).toMap // timeslots without values are allowed
  def content = timeSlots.map{ case (id, value) =>
      s"<${TimeOrder.tsTagName} ${RequiredXMLAttr(TimeOrder.tsIdAttrName, id)} ${OptionalXMLAttr(TimeOrder.tvAttrName, value)} />"}
  override def toString = Utils.wrap(TimeOrder.tagName, content.mkString("\n"))
}

object TimeOrder {
  val (tagName, tsTagName, tsIdAttrName, tvAttrName) = ("TIME_ORDER", "TIME_SLOT", "TIME_SLOT_ID", "TIME_VALUE")
}

//class LinguisticType(id: String, graphicReferences: Boolean, typeAlignable: Boolean) {
//  def toXMLString: String =
//    s"""|<LINGUISTIC_TYPE GRAPHIC_REFERENCES="${graphicReferences.toString}"
//        |  LINGUISTIC_TYPE_ID=$id TIME_ALIGNABLE="${typeAlignable.toString}"/>
//    """.stripMargin
//}

// Represents LINGUISTIC_TYPE element
class LinguisticType(linguisticTypeXML: JQuery) {
  val linguisticTypeID = RequiredXMLAttr(linguisticTypeXML, LinguisticType.ltIDAttrName)
  val timeAlignable = OptionalXMLAttr(linguisticTypeXML, LinguisticType.timeAlignAttrName, _.toBoolean)
  val constraints = OptionalXMLAttr(linguisticTypeXML, LinguisticType.constraintsAttrName)
  val graphicReferences = OptionalXMLAttr(linguisticTypeXML, LinguisticType.graphicReferencesAttrName, _.toBoolean)
  val controlledVocabularyRef = OptionalXMLAttr(linguisticTypeXML, LinguisticType.controlledVocRefAttrName)
  val extRef = OptionalXMLAttr(linguisticTypeXML, LinguisticType.extRefAttrName)
  val lexiconRef = OptionalXMLAttr(linguisticTypeXML, LinguisticType.lexRefAttrName)

  override def toString =
  s"<${LinguisticType.tagName} $linguisticTypeID $timeAlignable $constraints $graphicReferences " +
  s"$controlledVocabularyRef $extRef $lexiconRef/>"
}

object LinguisticType {
  // read sequence of XML linguisticTypeXML elements and return map of them with ID as a key
  def fromXMLs(linguisticTypeXMLs: JQuery) = Utils.jQuery2List(linguisticTypeXMLs).map(ltXML => {
    val lt = new LinguisticType(ltXML)
    lt.linguisticTypeID.value -> lt
  }).toMap
  val (tagName, ltIDAttrName, timeAlignAttrName, constraintsAttrName, graphicReferencesAttrName) =
    ("LINGUISTIC_TYPE", "LINGUISTIC_TYPE_ID", "TIME_ALIGNABLE", "CONSTRAINTS", "GRAPHIC_REFERENCES")
  val (controlledVocRefAttrName, extRefAttrName, lexRefAttrName) =
    ("CONTROLLED_VOCABULARY_REF", "EXT_REF", "LEXICON_REF")
}

// Represents LOCALE element
class Locale(val langCode: RequiredXMLAttr[String], val countCode: OptionalXMLAttr[String],
             val variant: OptionalXMLAttr[String]) {
  override def toString = s"<${Locale.tagName} $langCode $countCode $variant/>"
}

object Locale {
  // read sequence of XML Locale elements and return list of them
  def fromXMLs(locXMLs: JQuery) = Utils.jQuery2List(locXMLs).map(Locale(_))
  def apply(locXML: JQuery) = new Locale(
    RequiredXMLAttr(locXML, langCodeAttrName),
    OptionalXMLAttr(locXML, countCodeAttrName),
    OptionalXMLAttr(locXML, variantAttrName)
  )
  val (tagName, langCodeAttrName, countCodeAttrName, variantAttrName) =
    ("LOCALE", "LANGUAGE_CODE", "COUNTRY_CODE", "VARIANT")
}

// Represents CONSTRAINT element. There are 4 predefined CONSTRAINT values and ELAN doesn't support anything else.
// So we will always add these 4 constraint and ignore ones written in an incoming document completely
class Constraint(val stereotype: RequiredXMLAttr[String], val description: OptionalXMLAttr[String]) {
  def this(stereotype: String, description: Option[String]) =
    this(RequiredXMLAttr(Constraint.stereotypeAttrName, stereotype), OptionalXMLAttr(Constraint.descrAttrName, description))
  override def toString = s"<${Constraint.tagName} $stereotype $description/>"
}

object Constraint {
  // Four predefined constraints
  def predefinedConstraints = List(
    new Constraint("Time_Subdivision", Some("Time subdivision of parent annotation's time interval, no time gaps allowed within this interval")),
    new Constraint("Symbolic_Subdivision", Some("Symbolic subdivision of a parent annotation. Annotations refering to the same parent are ordered")),
    new Constraint("Symbolic_Association", Some("1-1 association with a parent annotation")),
    new Constraint("Included_In", Some("Time alignable annotations within the parent annotation's time interval, gaps are allowed"))
  )

  val (tagName, stereotypeAttrName, descrAttrName) = ("CONSTRAINT", "STEREOTYPE", "DESCRIPTION")
}


