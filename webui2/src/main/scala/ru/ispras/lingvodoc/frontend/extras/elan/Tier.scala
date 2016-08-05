package ru.ispras.lingvodoc.frontend.extras.elan

import org.scalajs.jquery.JQuery

import scala.annotation.meta.field
import scala.scalajs.js.annotation.{JSExportDescendentObjects, JSExport, JSExportAll}
import scala.scalajs.js.JSConverters._
import org.scalajs.dom.console


// Represents Tier element
class Tier(val tierID: RequiredXMLAttr[String], val linguisticTypeRef:RequiredXMLAttr[String],
           val participant: OptionalXMLAttr[String], val annotator: OptionalXMLAttr[String],
           val defaultLocale: OptionalXMLAttr[String], val parentRef: OptionalXMLAttr[String],
           var annotations: List[AbstractAnnotation], val parent: ELANDocumentJquery) {
  def this(tierXML: JQuery, parent: ELANDocumentJquery) { this(
    RequiredXMLAttr(tierXML, Tier.tIDAttrName),
    RequiredXMLAttr(tierXML, Tier.lTypeRefAttrName),
    OptionalXMLAttr(tierXML, Tier.parRefAttrName),
    OptionalXMLAttr(tierXML, Tier.annotAttrName),
    OptionalXMLAttr(tierXML, Tier.defLocAttrName),
    OptionalXMLAttr(tierXML, Tier.parRefAttrName),
    List.empty,
    parent
  )
    annotations = Utils.jQuery2List(tierXML.find(AbstractAnnotation.tagName)).map(
      if (isTimeAlignable) AlignableAnnotation(_, this) else RefAnnotation(_, this))
  }

  @JSExport
  def annotationsToJSArray = annotations.toJSArray
  @JSExport
  def refAnnotationsToJSArray = getRefAnnotations.toJSArray
  @JSExport
  def getID = tierID.value

  // If Tier is time alignable, only alignable annotations can present and only ref annotations otherwise, see
  // comment to LinguisticType's isTimeAlignable method
  @JSExport
  def isTimeAlignable = getLinguisticType.isTimeAlignable
  def getLinguisticType = { parent.getLinguisticType(linguisticTypeRef.value) }

  /**
    * If this tier is time alignable, return annotations as alignable ones, otherwise empty list
    * */
  def getAlignableAnnotations: List[AlignableAnnotation] = if (isTimeAlignable) {
    annotations.asInstanceOf[List[AlignableAnnotation]]
  }
  else {
    List.empty
  }

  /**
    * If this tier is not time alignable, return annotations as ref ones, otherwise empty list
    * */
  def getRefAnnotations: List[RefAnnotation] = if (!isTimeAlignable) {
    annotations.asInstanceOf[List[RefAnnotation]]
  }
  else {
    List.empty
  }

  private def attrsToString = s"$tierID $linguisticTypeRef $participant $annotator $defaultLocale $parentRef"
  override def toString = Utils.wrap(Tier.tagName, annotations.mkString("\n"), attrsToString)
}

object Tier {
  // read sequence of XML Tier elements and return list of them
  def fromXMLs(tierXMLs: JQuery, parent: ELANDocumentJquery) = Utils.jQuery2List(tierXMLs).map(new Tier(_, parent))
  val (tagName, tIDAttrName, lTypeRefAttrName, partAttrName, annotAttrName, defLocAttrName, parRefAttrName) = (
    "TIER", "TIER_ID", "LINGUISTIC_TYPE_REF", "PARTICIPANT", "ANNOTATOR", "DEFAULT_LOCALE", "PARENT_REF"
    )
}

// Functionality which either alignable and ref annotations have
trait AbstractAnnotation {
  val annotationID: RequiredXMLAttr[String]
  val extRef: OptionalXMLAttr[String]
  val parent: Tier
  def start: Long
  def end: Long
  // Long is opaque to scala.js, so we need these
  @JSExport
  def startToString = start.toString
  @JSExport
  def endToString = end.toString
  var text: String
  protected def includedAnnotationToString: String
  override def toString = Utils.wrap(AbstractAnnotation.tagName, includedAnnotationToString)
}

object AbstractAnnotation {
  // strip off <ANNOTATION> tag and check first tag inside
  def validateAnnotationType(annotXML: JQuery, allowedAnnot: String, errorMsg: String): JQuery = {
    val includedAnnotationXML = annotXML.children().first
    if (includedAnnotationXML.prop("tagName").toString != allowedAnnot)
      throw new ELANPArserException(errorMsg)
    includedAnnotationXML
  }
  val tagName = "ANNOTATION"
}

class AlignableAnnotation(val timeSlotRef1: RequiredXMLAttr[String], val timeSlotRef2: RequiredXMLAttr[String],
                          val svgRef: OptionalXMLAttr[String], aag: AnnotationAttributeGroup, val parent: Tier)
  extends AnnotationAttributeGroup(aag) with AbstractAnnotation {
  private def this(alignAnnotXML: JQuery, parent: Tier) = this(
    RequiredXMLAttr(alignAnnotXML, AlignableAnnotation.tsRef1AttrName),
    RequiredXMLAttr(alignAnnotXML, AlignableAnnotation.tsRef2AttrName),
    OptionalXMLAttr(alignAnnotXML, AlignableAnnotation.svgRefAttrName),
    new AnnotationAttributeGroup(alignAnnotXML),
    parent
  )

  def start = parent.parent.getTimeSlotValue(timeSlotRef1.value)
  def end = parent.parent.getTimeSlotValue(timeSlotRef2.value)

  override def attrsToString = super.attrsToString + s"$timeSlotRef1 $timeSlotRef2 $svgRef"
  protected def includedAnnotationToString = Utils.wrap(AlignableAnnotation.tagName, content, attrsToString)
}

object AlignableAnnotation {
  def apply(annotXML: JQuery, parent: Tier) = {
    val includedAnnotationXML = AbstractAnnotation.validateAnnotationType(annotXML, AlignableAnnotation.tagName,
      s"Only alignable annotations are allowed in this tier ${parent.tierID.value}")
    new AlignableAnnotation(includedAnnotationXML, parent)
  }
  val (tagName, tsRef1AttrName, tsRef2AttrName, svgRefAttrName) =
    ("ALIGNABLE_ANNOTATION", "TIME_SLOT_REF1", "TIME_SLOT_REF2", "SVG_REF")
}

class RefAnnotation(val annotationRef: RequiredXMLAttr[String], val previousAnnotation: OptionalXMLAttr[String],
                    aag: AnnotationAttributeGroup, val parent: Tier)
  extends AnnotationAttributeGroup(aag) with AbstractAnnotation {
  // will not work until all tiers are loaded
  private lazy val parentAnnotation = parent.parent.getAlignableAnnotationByID(annotationRef.value)

  private def this(refAnnotXML: JQuery, parent: Tier) = this(
    RequiredXMLAttr(refAnnotXML, RefAnnotation.annotRefAttrName),
    OptionalXMLAttr(refAnnotXML, RefAnnotation.prevAnnotAttrName),
    new AnnotationAttributeGroup(refAnnotXML),
    parent
  )

  def start = parentAnnotation.start
  def end = parentAnnotation.end

  override def attrsToString = super.attrsToString + s"$annotationRef $previousAnnotation"
  protected def includedAnnotationToString = Utils.wrap(RefAnnotation.tagName, content, attrsToString)
}

object RefAnnotation {
  def apply(annotXML: JQuery, parent: Tier) = {
    val includedAnnotationXML = AbstractAnnotation.validateAnnotationType(annotXML, RefAnnotation.tagName,
      s"Only ref annotations are allowed in tier ${parent.tierID.value}")
    new RefAnnotation(includedAnnotationXML, parent)
  }
  val (tagName, annotRefAttrName, prevAnnotAttrName) = ("REF_ANNOTATION", "ANNOTATION_REF", "PREVIOUS_ANNOTATION")
}

// represents annotationAttribute attribute group and additionally adds ANNOTATION_VALUE element which is the same
// in both ref annotation and alignable annotations too
class AnnotationAttributeGroup(val annotationID: RequiredXMLAttr[String], val extRef: OptionalXMLAttr[String],
                               @(JSExport @field) var text: String) {
  def this(includedAnnotationXML: JQuery) = this(
    RequiredXMLAttr(includedAnnotationXML, AnnotationAttributeGroup.annotIDAttrName),
    OptionalXMLAttr(includedAnnotationXML, AnnotationAttributeGroup.extRefAttrName),
    includedAnnotationXML.find(AnnotationAttributeGroup.annotValueElName).text()
  )
  def this(aag: AnnotationAttributeGroup) = this(aag.annotationID, aag.extRef, aag.text)

  def content = Utils.wrap(AnnotationAttributeGroup.annotValueElName, text)
  def attrsToString = s"$annotationID $extRef"
}

object AnnotationAttributeGroup {
  val (annotIDAttrName, extRefAttrName, annotValueElName) = ("ANNOTATION_ID", "EXT_REF", "ANNOTATION_VALUE")
}