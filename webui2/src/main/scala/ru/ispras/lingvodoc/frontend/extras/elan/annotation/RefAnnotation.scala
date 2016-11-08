package ru.ispras.lingvodoc.frontend.extras.elan.annotation

import org.scalajs.jquery.JQuery
import ru.ispras.lingvodoc.frontend.extras.elan.tier.{RefTier, Tier}
import ru.ispras.lingvodoc.frontend.extras.elan.{Utils, OptionalXMLAttr, RequiredXMLAttr}

class RefAnnotation protected(rao: RefAnnotationOpts, ao: AnnotationOpts)
  extends Annotation(ao) with DependentAnnotation {
  val annotationRef = rao.annotationRef
  override val owner = rao.owner

  def this(refAnnotXML: JQuery, owner: RefTier) = this(
    new RefAnnotationOpts(RequiredXMLAttr(refAnnotXML, RefAnnotation.annotRefAttrName), owner),
    new AnnotationOpts(refAnnotXML, owner)
  )

  def start = getParentAnnotation.start
  def end = getParentAnnotation.end

  override def attrsToString = super.attrsToString + s"$annotationRef"
  protected def includedAnnotationToString = Utils.wrap(RefAnnotation.tagName, content, attrsToString)

  // will not work until all tiers are loaded
  lazy val getParentAnnotation = owner.getParentTier.getAnnotationByIDChecked(annotationRef.value)
}

object RefAnnotation {
  def apply(annotXML: JQuery, owner: RefTier) = {
    val includedAnnotationXML = Annotation.validateAnnotationType(annotXML, RefAnnotation.tagName,
      s"Only ref annotations are allowed in tier ${owner.tierID.value}")
    new RefAnnotation(includedAnnotationXML, owner)
  }
  val (tagName, annotRefAttrName) = ("REF_ANNOTATION", "ANNOTATION_REF")
}

class RefAnnotationOpts(val annotationRef: RequiredXMLAttr[String], val owner: RefTier) {
  def this(raXML: JQuery, owner: RefTier) = this(
    RequiredXMLAttr(raXML, RefAnnotation.annotRefAttrName),
    owner
  )
  def this(annotationRef: String, owner: RefTier) = this(
    RequiredXMLAttr(RefAnnotation.annotRefAttrName, annotationRef),
    owner
  )
}
