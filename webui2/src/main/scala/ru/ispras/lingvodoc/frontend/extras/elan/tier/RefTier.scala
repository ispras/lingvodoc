package ru.ispras.lingvodoc.frontend.extras.elan.tier

import org.scalajs.jquery.JQuery
import ru.ispras.lingvodoc.frontend.extras.elan.RequiredXMLAttr
import ru.ispras.lingvodoc.frontend.extras.elan.annotation.RefAnnotation
import org.scalajs.dom.console

abstract class RefTier(val rto: RefTierOpts, to: TierOpts) extends Tier[RefAnnotation](to) with DependentTier[RefAnnotation] {
  val timeAlignable = false
  val parentRef = rto.parentRef
}

private[tier] class RefTierOpts(val parentRef: RequiredXMLAttr[String]) {
  def this(tierXML: JQuery) = this(RequiredXMLAttr(tierXML, DependentTier.parentRefAttrName))
  def this(parentRef: String) = this(RequiredXMLAttr(DependentTier.parentRefAttrName, parentRef))
}
