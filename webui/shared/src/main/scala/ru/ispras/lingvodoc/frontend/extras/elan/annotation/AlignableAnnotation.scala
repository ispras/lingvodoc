package ru.ispras.lingvodoc.frontend.extras.elan.annotation

import org.scalajs.jquery.JQuery
import ru.ispras.lingvodoc.frontend.extras.elan.tier.AlignableTier
import ru.ispras.lingvodoc.frontend.extras.elan.{Utils, OptionalXMLAttr, RequiredXMLAttr}

class AlignableAnnotation protected(aao: AlignableAnnotationOpts, ao: AnnotationOpts) extends Annotation(ao) {
  val timeSlotRef1 = aao.timeSlotRef1
  val timeSlotRef2 = aao.timeSlotRef2
  val svgRef = aao.svgRef
  override val owner = aao.owner

  def this(alignAnnotXML: JQuery, owner: AlignableTier[AlignableAnnotation]) = this(
    new AlignableAnnotationOpts(alignAnnotXML, owner),
    new AnnotationOpts(alignAnnotXML, owner)
  )

  def start = owner.owner.getTimeSlotValue(timeSlotRef1.value)
  def end = owner.owner.getTimeSlotValue(timeSlotRef2.value)

  override def attrsToString = super.attrsToString + s"$timeSlotRef1 $timeSlotRef2 $svgRef"
  protected def includedAnnotationToString = Utils.wrap(AlignableAnnotation.tagName, content, attrsToString)
}

object AlignableAnnotation {
  def apply(annotXML: JQuery, owner: AlignableTier[AlignableAnnotation]) = {
    val includedAnnotationXML = Annotation.validateAnnotationType(annotXML, AlignableAnnotation.tagName,
      s"Only alignable annotations are allowed in this tier ${owner.getID}")
    new AlignableAnnotation(includedAnnotationXML, owner)
  }
  val (tagName, tsRef1AttrName, tsRef2AttrName, svgRefAttrName) =
    ("ALIGNABLE_ANNOTATION", "TIME_SLOT_REF1", "TIME_SLOT_REF2", "SVG_REF")
}

private[annotation] class AlignableAnnotationOpts(val timeSlotRef1: RequiredXMLAttr[String],
                                                  val timeSlotRef2: RequiredXMLAttr[String],
                                                  val svgRef: OptionalXMLAttr[String],
                                                  val owner: AlignableTier[AlignableAnnotation]) {
  def this(aaXML: JQuery, owner: AlignableTier[AlignableAnnotation]) = this(
    RequiredXMLAttr(aaXML, AlignableAnnotation.tsRef1AttrName),
    RequiredXMLAttr(aaXML, AlignableAnnotation.tsRef2AttrName),
    OptionalXMLAttr(aaXML, AlignableAnnotation.svgRefAttrName),
    owner
  )
  def this(timeSlotRef1: String, timeSlotRef2: String, svgRef: Option[String],
           owner: AlignableTier[AlignableAnnotation]) = this(
    RequiredXMLAttr(AlignableAnnotation.tsRef1AttrName, timeSlotRef1),
    RequiredXMLAttr(AlignableAnnotation.tsRef2AttrName, timeSlotRef2),
    OptionalXMLAttr(AlignableAnnotation.svgRefAttrName, svgRef),
    owner
  )
}