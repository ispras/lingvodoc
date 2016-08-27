package ru.ispras.lingvodoc.frontend.extras.elan.annotation

import org.scalajs.jquery.JQuery
import ru.ispras.lingvodoc.frontend.extras.elan.tier.TimeAlignableTier
import ru.ispras.lingvodoc.frontend.extras.elan.{Utils, OptionalXMLAttr, RequiredXMLAttr}

class AlignableAnnotation private(val timeSlotRef1: RequiredXMLAttr[String], val timeSlotRef2: RequiredXMLAttr[String],
                                  val svgRef: OptionalXMLAttr[String],
                                  override val owner: TimeAlignableTier[AlignableAnnotation],
                                  ao: AnnotationOpts) extends Annotation(ao) {
  def this(alignAnnotXML: JQuery, owner: TimeAlignableTier[AlignableAnnotation]) = this(
    RequiredXMLAttr(alignAnnotXML, AlignableAnnotation.tsRef1AttrName),
    RequiredXMLAttr(alignAnnotXML, AlignableAnnotation.tsRef2AttrName),
    OptionalXMLAttr(alignAnnotXML, AlignableAnnotation.svgRefAttrName),
    owner,
    new AnnotationOpts(alignAnnotXML, owner)
  )

  def start = owner.owner.getTimeSlotValue(timeSlotRef1.value)
  def end = owner.owner.getTimeSlotValue(timeSlotRef2.value)

  override def attrsToString = super.attrsToString + s"$timeSlotRef1 $timeSlotRef2 $svgRef"
  protected def includedAnnotationToString = Utils.wrap(AlignableAnnotation.tagName, content, attrsToString)
}

object AlignableAnnotation {
  def apply(annotXML: JQuery, owner: TimeAlignableTier[AlignableAnnotation]) = {
    val includedAnnotationXML = Annotation.validateAnnotationType(annotXML, AlignableAnnotation.tagName,
      s"Only alignable annotations are allowed in this tier ${owner.getID}")
    new AlignableAnnotation(includedAnnotationXML, owner)
  }
  val (tagName, tsRef1AttrName, tsRef2AttrName, svgRefAttrName) =
    ("ALIGNABLE_ANNOTATION", "TIME_SLOT_REF1", "TIME_SLOT_REF2", "SVG_REF")
}