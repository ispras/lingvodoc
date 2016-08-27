package ru.ispras.lingvodoc.frontend.extras.elan.annotation

import org.scalajs.jquery.JQuery
import ru.ispras.lingvodoc.frontend.extras.elan.tier.{RefTier, Tier}
import ru.ispras.lingvodoc.frontend.extras.elan.{Utils, OptionalXMLAttr, RequiredXMLAttr}

class RefAnnotation private(val annotationRef: RequiredXMLAttr[String], val previousAnnotation: OptionalXMLAttr[String],
                            override val owner: RefTier,
                            ao: AnnotationOpts)
  extends Annotation(ao) {

  def this(refAnnotXML: JQuery, owner: RefTier) = this(
    RequiredXMLAttr(refAnnotXML, RefAnnotation.annotRefAttrName),
    OptionalXMLAttr(refAnnotXML, RefAnnotation.prevAnnotAttrName),
    owner,
    new AnnotationOpts(refAnnotXML, owner)
  )

  def start = parentAnnotation.start
  def end = parentAnnotation.end

  override def attrsToString = super.attrsToString + s"$annotationRef $previousAnnotation"
  protected def includedAnnotationToString = Utils.wrap(RefAnnotation.tagName, content, attrsToString)

  // will not work until all tiers are loaded
  private lazy val parentAnnotation = owner.getParentTier.getAnnotationByID(annotationRef.value)
}

object RefAnnotation {
  def apply(annotXML: JQuery, owner: RefTier) = {
    val includedAnnotationXML = Annotation.validateAnnotationType(annotXML, RefAnnotation.tagName,
      s"Only ref annotations are allowed in tier ${owner.tierID.value}")
    new RefAnnotation(includedAnnotationXML, owner)
  }
  val (tagName, annotRefAttrName, prevAnnotAttrName) = ("REF_ANNOTATION", "ANNOTATION_REF", "PREVIOUS_ANNOTATION")
}
