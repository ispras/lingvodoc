package ru.ispras.lingvodoc.frontend.extras.elan.annotation

import org.scalajs.jquery.JQuery
import ru.ispras.lingvodoc.frontend.extras.elan.{OptionalXMLAttr, RequiredXMLAttr}
import ru.ispras.lingvodoc.frontend.extras.elan.tier.RefTier


class SymbolicSubdivisionAnnotation(val previousAnnotation: OptionalXMLAttr[String], rao: RefAnnotationOpts,
                                    ao: AnnotationOpts) extends RefAnnotation(rao, ao) {
  def this(ssAnnotXML: JQuery, owner: RefTier) = this(
    OptionalXMLAttr(ssAnnotXML, SymbolicSubdivisionAnnotation.prevAnnotAttrName),
    new RefAnnotationOpts(ssAnnotXML, owner),
    new AnnotationOpts(ssAnnotXML, owner)
  )

  override def attrsToString = super.attrsToString + s" $previousAnnotation"
}

object SymbolicSubdivisionAnnotation {
  def apply(ssAnnotXML: JQuery, owner: RefTier) = {
    val includedAnnotationXML = Annotation.validateAnnotationType(ssAnnotXML, RefAnnotation.tagName,
      s"Only ref annotations are allowed in tier ${owner.tierID.value}")
    new SymbolicSubdivisionAnnotation(includedAnnotationXML, owner)
  }
  val prevAnnotAttrName = "PREVIOUS_ANNOTATION"
}
