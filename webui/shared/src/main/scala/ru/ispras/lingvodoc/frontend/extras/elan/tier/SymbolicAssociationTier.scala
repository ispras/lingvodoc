package ru.ispras.lingvodoc.frontend.extras.elan.tier

import org.scalajs.jquery.JQuery
import ru.ispras.lingvodoc.frontend.extras.elan.{RequiredXMLAttr, Utils, ELANDocument}
import ru.ispras.lingvodoc.frontend.extras.elan.annotation.{Annotation, RefAnnotation}
import org.scalajs.dom.console

class SymbolicAssociationTier private(var annotations: List[RefAnnotation], rto: DependentTierOpts,
                                      to: TierOpts) extends RefTier(rto, to) {
  def this(annotations: List[RefAnnotation], parentRef: String, tierID: String, linguisticTypeRef: String,
           participant: Option[String], annotator: Option[String], defaultLocale: Option[String],
           owner: ELANDocument) =  this(
      annotations,
      new DependentTierOpts(parentRef),
      new TierOpts(tierID, linguisticTypeRef, participant, annotator, defaultLocale, owner)
    )

  def this(SATierXML: JQuery, owner: ELANDocument) = {
    this(List.empty, new DependentTierOpts(SATierXML), new TierOpts(SATierXML, owner))
    annotations = Utils.jQuery2List(SATierXML.find(Annotation.tagName)).map(RefAnnotation(_, this))
  }

  val stereotype = "Symbolic Association"

  def getAnnotations = annotations
}
