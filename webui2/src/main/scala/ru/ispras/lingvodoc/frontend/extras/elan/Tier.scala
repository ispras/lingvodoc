package ru.ispras.lingvodoc.frontend.extras.elan

import org.scalajs.jquery.JQuery

import scala.scalajs.js.annotation.JSExportAll
import scala.scalajs.js.JSConverters._
import org.scalajs.dom.console


// Represents Tier element
@JSExportAll
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
    // If Tier is time alignable, only alignable annotations can present and only ref annotations otherwise, see
    // comment to LinguisticType's isTimeAlignable method
    annotations = Utils.jQuery2List(tierXML.find(AbstractAnnotation.tagName)).map(
      if (isTimeAlignable) AlignableAnnotation(_, this) else RefAnnotation(_, this))
  }

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

  def annotationsToJSArray = annotations.toJSArray

  def attrsToString = s"$tierID $linguisticTypeRef $participant $annotator $defaultLocale $parentRef"
  override def toString = Utils.wrap(Tier.tagName, annotations.mkString("\n"), attrsToString)
}

object Tier {
  // read sequence of XML Tier elements and return list of them
  def fromXMLs(tierXMLs: JQuery, parent: ELANDocumentJquery) = Utils.jQuery2List(tierXMLs).map(new Tier(_, parent))
  val (tagName, tIDAttrName, lTypeRefAttrName, partAttrName, annotAttrName, defLocAttrName, parRefAttrName) = (
    "TIER", "TIER_ID", "LINGUISTIC_TYPE_REF", "PARTICIPANT", "ANNOTATOR", "DEFAULT_LOCALE", "PARENT_REF"
    )
}

trait AbstractAnnotation {
  val parent: Tier
//  def start: Long
//  def end: Long
  var text: String
  def includedAnnotationToString: String
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

//// Represents Annotation element
//@JSExportAll
//class Annotation private(val annotation: Either[AlignableAnnotation, RefAnnotation]) {
//  override def toString = Utils.wrap(Annotation.tagName, annotation.fold(identity, identity).toString)
//}

//object Annotation {
//  // ANNOTATION contains only one element, it is either alignable or ref annotation
//  def apply(annotationXML: JQuery) = {
//    val includedAnnotationXML = annotationXML.children().first()
//    val annotation = includedAnnotationXML.prop("tagName").toString match {
//      case AlignableAnnotation.tagName => Left(new AlignableAnnotation(includedAnnotationXML))
//      case RefAnnotation.tagName => Right(new RefAnnotation(includedAnnotationXML))
//    }
//    new Annotation(annotation)
//  }
//  val tagName = "ANNOTATION"
//}

@JSExportAll
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

  override def attrsToString = super.attrsToString + s"$timeSlotRef1 $timeSlotRef2 $svgRef"
  def includedAnnotationToString = Utils.wrap(AlignableAnnotation.tagName, content, attrsToString)
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

@JSExportAll
class RefAnnotation(val annotationRef: RequiredXMLAttr[String], val previousAnnotation: OptionalXMLAttr[String],
                    aag: AnnotationAttributeGroup, val parent: Tier)
  extends AnnotationAttributeGroup(aag) with AbstractAnnotation {
  private def this(refAnnotXML: JQuery, parent: Tier) = this(
    RequiredXMLAttr(refAnnotXML, RefAnnotation.annotRefAttrName),
    OptionalXMLAttr(refAnnotXML, RefAnnotation.prevAnnotAttrName),
    new AnnotationAttributeGroup(refAnnotXML),
    parent
  )

  override def attrsToString = super.attrsToString + s"$annotationRef $previousAnnotation"
  def includedAnnotationToString = Utils.wrap(RefAnnotation.tagName, content, attrsToString)
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
@JSExportAll
class AnnotationAttributeGroup(val annotationID: RequiredXMLAttr[String], val extRef: OptionalXMLAttr[String],
                               var text: String) {
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