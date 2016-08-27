package ru.ispras.lingvodoc.frontend.extras.elan.tier

import ru.ispras.lingvodoc.frontend.extras.elan.annotation.AlignableAnnotation

abstract class TimeAlignableTier[+AnnotType <: AlignableAnnotation](to: TierOpts) extends Tier[AnnotType](to) {
  val timeAlignable = true
}
