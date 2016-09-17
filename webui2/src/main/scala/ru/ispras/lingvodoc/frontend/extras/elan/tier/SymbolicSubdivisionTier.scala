package ru.ispras.lingvodoc.frontend.extras.elan.tier

import org.scalajs.jquery.JQuery
import ru.ispras.lingvodoc.frontend.extras.elan.{RequiredXMLAttr, Utils, ELANDocumentJquery}
import ru.ispras.lingvodoc.frontend.extras.elan.annotation.{SymbolicSubdivisionAnnotation, Annotation, RefAnnotation}
import org.scalajs.dom.console

class SymbolicSubdivisionTier private(var annotations: List[SymbolicSubdivisionAnnotation], rto: DependentTierOpts,
                                      to: TierOpts) extends RefTier(rto, to) {
  def this(annotations: List[SymbolicSubdivisionAnnotation], parentRef: String, tierID: String, linguisticTypeRef: String,
           participant: Option[String], annotator: Option[String], defaultLocale: Option[String],
           owner: ELANDocumentJquery) = this(
    annotations,
    new DependentTierOpts(parentRef),
    new TierOpts(tierID, linguisticTypeRef, participant, annotator, defaultLocale, owner)
  )

  def this(SSTierXML: JQuery, owner: ELANDocumentJquery) = {
    this(List.empty, new DependentTierOpts(SSTierXML), new TierOpts(SSTierXML, owner))
    annotations = Utils.jQuery2List(SSTierXML.find(Annotation.tagName)).map(SymbolicSubdivisionAnnotation(_, this))
  }

  val stereotype = "Symbolic Subdivision"

  def getAnnotations = annotations
}
