package ru.ispras.lingvodoc.frontend.extras.elan.tier

import ru.ispras.lingvodoc.frontend.extras.elan.annotation.{AlignableDependentAnnotation, AlignableAnnotation}

abstract class AlignableTier[+AnnotType <: AlignableAnnotation](to: TierOpts) extends Tier[AnnotType](to) {
  val timeAlignable = true
}

abstract class AlignableDependentTier[+AnnotType <: AlignableDependentAnnotation](to: TierOpts)
  extends AlignableTier[AnnotType](to) with DependentTier[AnnotType] {
}
