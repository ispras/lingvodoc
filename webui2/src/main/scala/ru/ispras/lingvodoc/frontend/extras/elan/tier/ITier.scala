package ru.ispras.lingvodoc.frontend.extras.elan.tier

import org.scalajs.jquery.JQuery
import ru.ispras.lingvodoc.frontend.extras.elan._
import ru.ispras.lingvodoc.frontend.extras.elan.annotation.{RefAnnotation, AlignableAnnotation, IAnnotation}
import ru.ispras.lingvodoc.frontend.extras.elan.XMLAttrConversions._

import scala.collection.mutable
import scala.scalajs.js
import scala.scalajs.js.annotation.{JSExportAll, JSExportDescendentObjects, JSExport}
import scala.scalajs.js.JSConverters._
import org.scalajs.dom.console

@JSExportDescendentObjects
trait ITier[+AnnotType <: IAnnotation] {
  // is this tier time alignable?
  @JSExport
  val timeAlignable: Boolean
  // human readable stereotype name
  @JSExport
  val stereotype: String

  // get linguistic type name (id)
  @JSExport
  def getLT: String

  // get tier name
  @JSExport
  def getID: String

  // get JS array of Annotations (js doesn't work with Scala collections directly)
  // I would write js.Array[AnnotType] here, but Array is invariant, so it won't work
  @JSExport
  def annotationsToJSArray: js.Dynamic

  def toJS: js.Dynamic

  // get root document
  val owner: ELANDocumentJquery
  def getAnnotations: List[AnnotType]
  def getAnnotationByID(id: String): Option[AnnotType]
  // throws exception if annotation not found
  def getAnnotationByIDChecked(id: String): AnnotType
}

abstract class Tier[+AnnotType <: IAnnotation] (to: TierOpts) extends ITier[AnnotType] {
  val tierID = to.tierID
  val linguisticTypeRef = to.linguisticTypeRef
  val participant = to.participant
  val annotator = to.annotator
  val defaultLocale = to.defaultLocale
  val owner = to.owner

  def getLT = linguisticTypeRef
  def getID = tierID
  def annotationsToJSArray = getAnnotations.toJSArray.asInstanceOf[js.Dynamic]
  def getAnnotationByID(id: String) = getAnnotations.find(_.getID == id)

  def getAnnotationByIDChecked(id: String) = try {
    getAnnotationByID(id).get
  } catch {
    case e: java.util.NoSuchElementException => throw ELANPArserException(s"Annotation with id $id not found in tier $getID")
  }

  def toJS = {
    val tierJS = mutable.Map.empty[String, js.Dynamic]
    tierJS("ID") = getID.asInstanceOf[js.Dynamic]
    tierJS("timeAlignable") = timeAlignable.asInstanceOf[js.Dynamic]
    tierJS("stereotype") = stereotype.asInstanceOf[js.Dynamic]
    tierJS("annotations") = getAnnotations.map(_.toJS).toJSArray.asInstanceOf[js.Dynamic]
    tierJS.toJSDictionary.asInstanceOf[js.Dynamic]
  }

  private def attrsToString = s"$tierID $linguisticTypeRef $participant $annotator $defaultLocale"
  override def toString = Utils.wrap(Tier.tagName, getAnnotations.mkString("\n"), attrsToString)
}

object Tier {
  // read sequence of XML Tier elements and return list of them
  def fromXMLs(tierXMLs: JQuery, owner: ELANDocumentJquery) = Utils.jQuery2List(tierXMLs).map(fromXML(_, owner))
  // factory method, chooses right tier type and creates it
  def fromXML(tierXML: JQuery, owner: ELANDocumentJquery): Tier[IAnnotation] = {
    val ltRef = RequiredXMLAttr(tierXML, Tier.lTypeRefAttrName)
    owner.getLinguisticTypeChecked(ltRef).getStereotypeID match {
      case None => new TopLevelTier(tierXML, owner)
      case Some(Constraint.timeSubdivID) => new TimeSubdivisionTier(tierXML, owner)
      case Some(Constraint.includedInID) => new IncludedInTier(tierXML, owner)
      case Some(Constraint.symbolSubdivID) => new SymbolicSubdivisionTier(tierXML, owner)
      case Some(Constraint.symbolAssocID) => new SymbolicAssociationTier(tierXML, owner)
      case _ => ??? // impossible
    }
  }

  val (tagName, tIDAttrName, lTypeRefAttrName, partAttrName, annotAttrName, defLocAttrName) = (
    "TIER", "TIER_ID", "LINGUISTIC_TYPE_REF", "PARTICIPANT", "ANNOTATOR", "DEFAULT_LOCALE"
    )
}

private[tier] class TierOpts(val tierID: RequiredXMLAttr[String], val linguisticTypeRef: RequiredXMLAttr[String],
               val participant: OptionalXMLAttr[String], val annotator: OptionalXMLAttr[String],
               val defaultLocale: OptionalXMLAttr[String], val owner: ELANDocumentJquery) {
  def this(tierXML: JQuery, owner: ELANDocumentJquery) = this(
    RequiredXMLAttr(tierXML, Tier.tIDAttrName),
    RequiredXMLAttr(tierXML, Tier.lTypeRefAttrName),
    OptionalXMLAttr(tierXML, Tier.partAttrName),
    OptionalXMLAttr(tierXML, Tier.annotAttrName),
    OptionalXMLAttr(tierXML, Tier.defLocAttrName),
    owner
  )
  def this(tierID: String, linguisticTypeRef: String, participant: Option[String], annotator: Option[String],
           defaultLocale: Option[String], owner: ELANDocumentJquery) = this(
    RequiredXMLAttr(Tier.tIDAttrName, tierID),
    RequiredXMLAttr(Tier.lTypeRefAttrName, linguisticTypeRef),
    OptionalXMLAttr(Tier.partAttrName, participant),
    OptionalXMLAttr(Tier.annotAttrName, annotator),
    OptionalXMLAttr(Tier.defLocAttrName, defaultLocale),
    owner
  )
}
