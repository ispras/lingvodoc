package ru.ispras.lingvodoc.frontend.extras.elan.tier

import org.scalajs.jquery.JQuery
import ru.ispras.lingvodoc.frontend.extras.elan.{Utils, ELANDocumentJquery}
import ru.ispras.lingvodoc.frontend.extras.elan.annotation.{Annotation, AlignableAnnotation}

class TopLevelTier private(var annotations: List[AlignableAnnotation], to: TierOpts)
  extends AlignableTier[AlignableAnnotation](to) {
  def this(annotations: List[AlignableAnnotation], tierID: String, linguisticTypeRef: String,
           participant: Option[String], annotator: Option[String], defaultLocale: Option[String],
           owner: ELANDocumentJquery) =
    this(annotations,
         new TierOpts(tierID, linguisticTypeRef, participant, annotator, defaultLocale, owner)
    )

  def this(topLevelTierXML: JQuery, owner: ELANDocumentJquery) = {
    this(List.empty, new TierOpts(topLevelTierXML, owner))
    annotations = Utils.jQuery2List(topLevelTierXML.find(Annotation.tagName)).map(AlignableAnnotation(_, this))
  }

  val stereotype = "Top-level"

  def getAnnotations = annotations
}
