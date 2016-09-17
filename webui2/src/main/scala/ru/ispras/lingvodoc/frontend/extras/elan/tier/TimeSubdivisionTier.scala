package ru.ispras.lingvodoc.frontend.extras.elan.tier

import org.scalajs.jquery.JQuery
import ru.ispras.lingvodoc.frontend.extras.elan.{Utils, ELANDocumentJquery}
import ru.ispras.lingvodoc.frontend.extras.elan.annotation.{AlignableAnnotation, Annotation, AlignableDependentAnnotation}


class TimeSubdivisionTier private(var annotations: List[AlignableDependentAnnotation], val dto: DependentTierOpts, to: TierOpts)
  extends AlignableDependentTier[AlignableDependentAnnotation](to) {
  val parentRef = dto.parentRef
  def this(annotations: List[AlignableDependentAnnotation], parentRef: String, tierID: String, linguisticTypeRef: String,
           participant: Option[String], annotator: Option[String], defaultLocale: Option[String],
           owner: ELANDocumentJquery) = this(
    annotations,
    new DependentTierOpts(parentRef),
    new TierOpts(tierID, linguisticTypeRef, participant, annotator, defaultLocale, owner)
  )

  def this(TSTierXML: JQuery, owner: ELANDocumentJquery) = {
    this(List.empty, new DependentTierOpts(TSTierXML), new TierOpts(TSTierXML, owner))
    annotations = Utils.jQuery2List(TSTierXML.find(Annotation.tagName)).map(AlignableDependentAnnotation(_, this))
  }

  val stereotype = "Time Subdivision"

  def getAnnotations = annotations
}
