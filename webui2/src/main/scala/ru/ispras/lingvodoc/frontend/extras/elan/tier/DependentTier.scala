package ru.ispras.lingvodoc.frontend.extras.elan.tier

import org.scalajs.jquery.JQuery
import ru.ispras.lingvodoc.frontend.extras.elan.RequiredXMLAttr
import ru.ispras.lingvodoc.frontend.extras.elan.annotation.IAnnotation
import ru.ispras.lingvodoc.frontend.extras.elan.XMLAttrConversions._


// tier which have a parent tier
trait DependentTier[+AnnotType <: IAnnotation] extends ITier[AnnotType] {
  val parentRef: RequiredXMLAttr[String]

  def getParentTier = owner.getTierByIDChecked(parentRef)

  // TODO: implement it for II and TS tiers
  def findAnnotationParent(annot: IAnnotation): IAnnotation = ???
}

object DependentTier {
  val parentRefAttrName = "PARENT_REF"
}

private[tier] class DependentTierOpts(val parentRef: RequiredXMLAttr[String]) {
  def this(tierXML: JQuery) = this(RequiredXMLAttr(tierXML, DependentTier.parentRefAttrName))
  def this(parentRef: String) = this(RequiredXMLAttr(DependentTier.parentRefAttrName, parentRef))
}