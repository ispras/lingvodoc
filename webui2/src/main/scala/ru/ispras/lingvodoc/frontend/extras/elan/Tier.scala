package ru.ispras.lingvodoc.frontend.extras.elan

import org.scalajs.jquery.JQuery

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
  // read sequence of XML Tier elements and return list of them
  def fromXMLs(tierXMLs: JQuery) = Utils.jQuery2List(tierXMLs).map(new Tier(_))
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

  override def toString = Utils.wrap(AlignableAnnotation.tagName, content,
    s"${super.toString} $timeSlotRef1 $timeSlotRef2 $svgRef")
}

object AlignableAnnotation {
  val (tagName, tsRef1AttrName, tsRef2AttrName, svgRefAttrName) =
    ("ALIGNABLE_ANNOTATION", "TIME_SLOT_REF1", "TIME_SLOT_REF2", "SVG_REF")
}

class RefAnnotation(refAnnotXML: JQuery) extends AnnotationAttributeGroup(refAnnotXML) {
  val annotationRef = RequiredXMLAttr(refAnnotXML, RefAnnotation.annotRefAttrName)
  val previousAnnotation = OptionalXMLAttr(refAnnotXML, RefAnnotation.prevAnnotAttrName)

  override def toString = Utils.wrap(RefAnnotation.tagName, content,
    s"${super.toString} $annotationRef $previousAnnotation")
}

object RefAnnotation {
  val (tagName, annotRefAttrName, prevAnnotAttrName) = ("REF_ANNOTATION", "ANNOTATION_REF", "PREVIOUS_ANNOTATION")
}

// represents annotationAttribut attribute group and additionally adds ANNOTATION_VALUE element which is the same
// in both ref annotation and alignable annotations too
class AnnotationAttributeGroup(includedAnnotationXML: JQuery) {
  val annotationID = RequiredXMLAttr(includedAnnotationXML, AnnotationAttributeGroup.annotIDAttrName)
  val extRef = OptionalXMLAttr(includedAnnotationXML, AnnotationAttributeGroup.extRefAttrName)
  var text = includedAnnotationXML.find(AnnotationAttributeGroup.annotValueElName).text()

  def content = Utils.wrap(AnnotationAttributeGroup.annotValueElName, text)
  override def toString = s"$annotationID $extRef"
}

object AnnotationAttributeGroup {
  val (annotIDAttrName, extRefAttrName, annotValueElName) = ("ANNOTATION_ID", "EXT_REF", "ANNOTATION_VALUE")
}