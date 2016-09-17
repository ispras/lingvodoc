package ru.ispras.lingvodoc.frontend.extras.elan.annotation

import org.scalajs.jquery.JQuery
import ru.ispras.lingvodoc.frontend.extras.elan.tier.{AlignableDependentTier, TimeSubdivisionTier}

/**
  * Created by ars on 8/31/16.
  */
class AlignableDependentAnnotation private(override val owner: AlignableDependentTier[AlignableDependentAnnotation],
                                           aao: AlignableAnnotationOpts,
                                           ao: AnnotationOpts) extends AlignableAnnotation(aao, ao)
  with DependentAnnotation {
  def this(alignAnnotXML: JQuery, owner: AlignableDependentTier[AlignableDependentAnnotation]) = this(
    owner,
    new AlignableAnnotationOpts(alignAnnotXML, owner),
    new AnnotationOpts(alignAnnotXML, owner)
  )

  lazy val getParentAnnotation = owner.findAnnotationParent(this)
}

object AlignableDependentAnnotation {
  def apply(annotXML: JQuery, owner: AlignableDependentTier[AlignableDependentAnnotation]) = {
    val includedAnnotationXML = Annotation.validateAnnotationType(annotXML, AlignableAnnotation.tagName,
      s"Only alignable annotations are allowed in this tier ${owner.getID}")
    new AlignableDependentAnnotation(includedAnnotationXML, owner)
  }
}
