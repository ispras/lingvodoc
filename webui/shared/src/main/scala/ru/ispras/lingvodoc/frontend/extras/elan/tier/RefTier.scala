package ru.ispras.lingvodoc.frontend.extras.elan.tier

import org.scalajs.jquery.JQuery
import ru.ispras.lingvodoc.frontend.extras.elan.RequiredXMLAttr
import ru.ispras.lingvodoc.frontend.extras.elan.annotation.RefAnnotation
import org.scalajs.dom.console

abstract class RefTier(val dto: DependentTierOpts, to: TierOpts) extends Tier[RefAnnotation](to)
  with DependentTier[RefAnnotation] {
  val timeAlignable = false
  val parentRef = dto.parentRef
}
