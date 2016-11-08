package ru.ispras.lingvodoc.frontend.extras.elan.annotation

// Each annotation of non-top-level tier is a dependent annotation -- it is bind to one of the parent tier's
// annotation. In case of alignable annotations this reference is implicit, i.e. it is not reflected in XML.
// In this case, we have to calculate it ourselves.
trait DependentAnnotation extends Annotation {
  def getParentAnnotation: IAnnotation
}
