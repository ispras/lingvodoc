package ru.ispras.lingvodoc.frontend.extras.elan

import org.scalajs.dom
import org.scalajs.jquery._
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.extras.elan.annotation.{IAnnotation, AlignableAnnotation}
import ru.ispras.lingvodoc.frontend.extras.elan.tier.{ITier, RefTier, TimeAlignableTier, Tier}
import ru.ispras.lingvodoc.frontend.extras.elan.XMLAttrConversions._

import scala.collection.immutable.{ListMap, HashMap}
import scala.scalajs.js
import scala.scalajs.js.annotation.JSExportAll
import scala.scalajs.js.JSConverters._

/**
  * Mutable data is used everywhere since it is more handy for user interaction
  */

case class ELANPArserException(message: String) extends Exception(message)

// Represents ELAN (EAF) document
@JSExportAll
class ELANDocumentJquery private(annotDocXML: JQuery) {
  // attributes
  val date = RequiredXMLAttr(annotDocXML, ELANDocumentJquery.dateAttrName)
  val author = RequiredXMLAttr(annotDocXML, ELANDocumentJquery.authorAttrName)
  val version = RequiredXMLAttr(annotDocXML, ELANDocumentJquery.versionAttrName)
  val format = RequiredXMLAttr(annotDocXML, ELANDocumentJquery.formatAttrName, Some("2.7"))

  val header = new Header(annotDocXML.find(Header.tagName))

  val timeOrder = new TimeOrder(annotDocXML.find(TimeOrder.tagName))
  val constraints = Constraint.predefinedConstraints
  private var linguisticTypes = LinguisticType.fromXMLs(annotDocXML.find(LinguisticType.tagName), this)
  var tiers: List[ITier[IAnnotation]] = Tier.fromXMLs(annotDocXML.find(Tier.tagName), this)
  val locales = Locale.fromXMLs(annotDocXML.find(Locale.tagName))
  // the following 3 elements are not supported yet; we will just save them unchanged as a String
  val controlledVocabulary = Utils.jQuery2XML(annotDocXML.find(ELANDocumentJquery.controlledVocTagName))
  val lexiconRef = Utils.jQuery2XML(annotDocXML.find(ELANDocumentJquery.lexRefTagName))
  val externalRef = Utils.jQuery2XML(annotDocXML.find(ELANDocumentJquery.extRefTagName))

  private var lastUsedTimeSlotID: Long = 0
  private var lastUsedAnnotationID: Long = 0
  reindex()

  /**
    * We cannot reliably say whether this XML last time was modified via lingvodoc, ELAN or something else,
    * and there is no unified way of counting time slot and annotations IDs in the specification.
    * Because of that we are forced to reindex time slot and annotation IDs every time we read a EAF file.
    * This function does the job: it counts IDs, renames them and sets two counters
    */
  private def reindex(): Unit = {
      // reindex time slots
      var oldTimeSlotIDsToNew: Map[String, String] = Map.empty
      timeOrder.timeSlots = for ((id, value) <- timeOrder.timeSlots) yield {
        lastUsedTimeSlotID += 1 // it doesn't matter, but ELAN indexes from 1, so we too
        val newTimeSlot = tsIDFromNumber(lastUsedTimeSlotID)
        oldTimeSlotIDsToNew += (id -> newTimeSlot)
        (newTimeSlot, value)
      }
      // now substitute references to time slots in all alignable annotations
    getTimeAlignableTiers.flatMap(_.getAnnotations).foreach(annotation => {
        annotation.timeSlotRef1.value = oldTimeSlotIDsToNew(annotation.timeSlotRef1.value)
        annotation.timeSlotRef2.value = oldTimeSlotIDsToNew(annotation.timeSlotRef2.value)
      })

      // reindex annotations
      var oldAnnotationIDstoNew: Map[String, String] = Map.empty
      tiers.foreach(_.getAnnotations.foreach(annotation => {
        lastUsedAnnotationID += 1
        val newAnnotationID = annotIDFromNumber(lastUsedAnnotationID)
        oldAnnotationIDstoNew += (annotation.annotationID.value -> newAnnotationID)
        annotation.annotationID.value = newAnnotationID
      }))
      // now substitute all references to them: they encounter in ANNOTATION_REF and
      // in PREVIOUS_ANNOTATION of ref annotations
      getRefTiers.flatMap(_.getAnnotations).foreach(annotation => {
        annotation.annotationRef.value = oldAnnotationIDstoNew(annotation.annotationRef.value)
        annotation.previousAnnotation.value.foreach(v =>
          annotation.previousAnnotation.value = Some(oldAnnotationIDstoNew(v)))
      })
  }

  // xsd:ID can't start with a digit
  private def tsIDFromNumber(id: Long) = "ts" + id
  private def annotIDFromNumber(id: Long) = "a" + id

  def issueTimeSlotID(): String = {
    lastUsedTimeSlotID += 1
    tsIDFromNumber(lastUsedTimeSlotID)
  }

  def issueAnnotationID(): String = {
    lastUsedAnnotationID += 1
    annotIDFromNumber(lastUsedAnnotationID)
  }

  def getTierByID(id: String) = try {
    tiers.filter(_.getID == id).head
  } catch {
    case e: java.util.NoSuchElementException => throw ELANPArserException(s"Tier with id $id not found")
  }

  def getTimeAlignableTiers = tiers.filter(_.isInstanceOf[TimeAlignableTier[_]]).
    map(_.asInstanceOf[TimeAlignableTier[AlignableAnnotation]])
  def getRefTiers = tiers.filter(_.isInstanceOf[RefTier]).map(_.asInstanceOf[RefTier])

  // fails if time slot has no value or doesn't exists
  def getTimeSlotValue(id: String) = timeOrder.getTimeSlotValue(id)

  // get Linguistic Type by id
  def getLinguisticType(ltRef: String) = {
    val errorMsg = s"Linguistic type $ltRef not found; loaded linguistic types are " +
      linguisticTypes.values.map(_.linguisticTypeID.value).mkString(", ")
    try {
      linguisticTypes(ltRef)
    } catch {
      case e: java.util.NoSuchElementException => throw ELANPArserException(errorMsg)
    }
  }


  // How could we access them from html templates otherwise?
  def tiersToJSArray = tiers.toJSArray

  private def content = s"$header $timeOrder ${tiers.mkString("\n")} ${linguisticTypes.values.mkString("\n")} " +
                s"${locales.mkString("\n")} ${constraints.values.mkString("\n")}" +
                s"$controlledVocabulary $lexiconRef  $externalRef"
  private def attrsToString = s"$date $author $version $format ${ELANDocumentJquery.xmlnsXsi} ${ELANDocumentJquery.schemaLoc}"

  override def toString =
    s"""|<?xml version="1.0" encoding="UTF-8"?>
        |${Utils.wrap(ELANDocumentJquery.annotDocTagName, content, attrsToString)}
    """.stripMargin
}

object ELANDocumentJquery {
  val annotDocTagName = "ANNOTATION_DOCUMENT"
  val (dateAttrName, authorAttrName, versionAttrName, formatAttrName) = ("DATE", "AUTHOR", "VERSION", "FORMAT")
  val (controlledVocTagName, lexRefTagName, extRefTagName) = ("CONTROLLED_VOCABULARY", "LEXICON_REF", "EXTERNAL_REF")
  // hardcoded, expected not to change
  val xmlnsXsi = RequiredXMLAttr("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
  val schemaLoc = RequiredXMLAttr("xsi:noNamespaceSchemaLocation", "http://www.mpi.nl/tools/elan/EAFv2.7.xsd")
  // see http://www.mpi.nl/tools/elan/EAF_Annotation_Format.pdf for format specification
  // JQuery is used for parsing.
  // WARNING: it is assumed that the xmlString is a valid ELAN document matching xsd scheme.
  // Otherwise the result is undefined.
  def apply(xmlString: String) = new ELANDocumentJquery(jQuery(jQuery.parseXML(xmlString)).find(annotDocTagName))
}

// Represents TIME_ORDER element
@JSExportAll
class TimeOrder(timeOrderXML: JQuery) {
  // Scala.js doesn't support Long, we are forced to use Int instead
  var timeSlots = Utils.jQuery2List(timeOrderXML.find(TimeOrder.tsTagName)).map(tsJquery => {
    tsJquery.attr(TimeOrder.tsIdAttrName).get -> tsJquery.attr(TimeOrder.tvAttrName).toOption.map(_.toLong)
  }).toMap // timeslots without values are allowed by the specification

  // In principle timeslots without value are allowed, but this particular method will throw an exception, if
  // timeslot has no value or timeslot with such id doesn't exists at all
  def getTimeSlotValue(id: String): Long = {
    try {
      timeSlots(id).get
    } catch {
      case e: java.util.NoSuchElementException => throw ELANPArserException(s"TimeSlot with id $id doesn't exists or has no value")
    }
  }

  private def content = timeSlots.map{ case (id, value) =>
      s"<${TimeOrder.tsTagName} ${RequiredXMLAttr(TimeOrder.tsIdAttrName, id)} ${OptionalXMLAttr(TimeOrder.tvAttrName, value)} />"}
  override def toString = Utils.wrap(TimeOrder.tagName, content.mkString("\n"))
}

object TimeOrder {
  val (tagName, tsTagName, tsIdAttrName, tvAttrName) = ("TIME_ORDER", "TIME_SLOT", "TIME_SLOT_ID", "TIME_VALUE")
}


// Represents LINGUISTIC_TYPE element
// TODO: check constraints value on manual creation
@JSExportAll
class LinguisticType(val linguisticTypeID: RequiredXMLAttr[String], val timeAlignable: OptionalXMLAttr[Boolean],
                     val constraints: OptionalXMLAttr[String], val graphicReferences: OptionalXMLAttr[Boolean],
                     val controlledVocabularyRef: OptionalXMLAttr[String], val extRef: OptionalXMLAttr[String],
                     val lexiconRef: OptionalXMLAttr[String], owner: ELANDocumentJquery) {
  def this(linguisticTypeXML: JQuery, owner: ELANDocumentJquery) = this(
    RequiredXMLAttr(linguisticTypeXML, LinguisticType.ltIDAttrName),
    OptionalXMLAttr(linguisticTypeXML, LinguisticType.timeAlignAttrName, _.toBoolean),
    OptionalXMLAttr(linguisticTypeXML, LinguisticType.constraintsAttrName),
    OptionalXMLAttr(linguisticTypeXML, LinguisticType.graphicReferencesAttrName, _.toBoolean),
    OptionalXMLAttr(linguisticTypeXML, LinguisticType.controlledVocRefAttrName),
    OptionalXMLAttr(linguisticTypeXML, LinguisticType.extRefAttrName),
    OptionalXMLAttr(linguisticTypeXML, LinguisticType.lexRefAttrName),
    owner
  )

  if (!constraints.map(owner.constraints.keys.toSeq.contains).getOrElse(true))
    throw ELANPArserException(s"Wrong constraint ${constraints.value} for LT ${linguisticTypeID.value}")

  /**
    * If yes, a tier with such linguistic type can have only alignable annotations. Otherwise it can have only ref
    * annotations. Note that EAF format specification doesn't forbid explicitly mixing alignable and ref annotations,
    * at least I didn't found that. However, it seems that it is impossible to do that in ELAN program, and it doesn't
    * make much sense anyway, so we will forbid it.
    * According to the spec, CONSTRAINT should have precedence over TIME_ALIGNABLE field. Following this, we will
    * determine "alignability" of a tier like this:
    * 1) If LT has no CONSTRAINT field, alignable is true
    * 2) If CONSTRAINT field exists and it is Time_Subdivision or Included_In, true
    * 3) If CONSTRAINT field exists and it is Symbolic_Subdivision or Symbolic_Association, false
    *
    * Well, I see no need in TIME_ALIGNABLE field since it is rather exhaustive classification. We will just ignore it
    * and give a warning in case of inconsistency.
    * 2)
    * */
  def isTimeAlignable = {
    val result = constraints.value match {
      case None | Some(Constraint.`timeSubdivID`) | Some(Constraint.`includedInID`) => true
      case Some(Constraint.`symbolAssocID`) | Some(Constraint.`symbolSubdivID`) => false
      case x => throw ELANPArserException(s"Wrong constraint id $x")
    }
    timeAlignable.foreach(ta => if (ta != result) console.warn("Ignored TIME_ALIGNABLE value is not consistent with CONSTRAINTS"))
    result
  }

  def getStereotypeID: Option[String] = constraints

  override def toString =
  s"<${LinguisticType.tagName} $linguisticTypeID $timeAlignable $constraints $graphicReferences " +
  s"$controlledVocabularyRef $extRef $lexiconRef/>"
}

object LinguisticType {
  // read sequence of XML linguisticTypeXML elements and return map of them with ID as a key
  def fromXMLs(linguisticTypeXMLs: JQuery, owner: ELANDocumentJquery) = Utils.jQuery2List(linguisticTypeXMLs).map(ltXML => {
    val lt = new LinguisticType(ltXML, owner)
    lt.linguisticTypeID.value -> lt
  }).toMap
  val (tagName, ltIDAttrName, timeAlignAttrName, constraintsAttrName, graphicReferencesAttrName) =
    ("LINGUISTIC_TYPE", "LINGUISTIC_TYPE_ID", "TIME_ALIGNABLE", "CONSTRAINTS", "GRAPHIC_REFERENCES")
  val (controlledVocRefAttrName, extRefAttrName, lexRefAttrName) =
    ("CONTROLLED_VOCABULARY_REF", "EXT_REF", "LEXICON_REF")
}

// Represents LOCALE element
@JSExportAll
class Locale(val langCode: RequiredXMLAttr[String], val countCode: OptionalXMLAttr[String],
             val variant: OptionalXMLAttr[String]) {
  override def toString = s"<${Locale.tagName} $langCode $countCode $variant/>"
}

object Locale {
  // read sequence of XML Locale elements and return list of them
  def fromXMLs(locXMLs: JQuery) = Utils.jQuery2List(locXMLs).map(Locale(_))
  def apply(locXML: JQuery) = new Locale(
    RequiredXMLAttr(locXML, langCodeAttrName),
    OptionalXMLAttr(locXML, countCodeAttrName),
    OptionalXMLAttr(locXML, variantAttrName)
  )
  val (tagName, langCodeAttrName, countCodeAttrName, variantAttrName) =
    ("LOCALE", "LANGUAGE_CODE", "COUNTRY_CODE", "VARIANT")
}
/**
  * Represents CONSTRAINT element. There are 4 predefined CONSTRAINT elements (stereotypes)
  * and ELAN doesn't support anything else.
  * So we will always add these 4 constraints and ignore ones written in an incoming document completely. Every
  * tier must have linguistic type, which, in turn, may or may not have one stereotype.
  *
  * Now I will explain meaning of each of them. Basically, there are 5 Tier types: 4 stereotypes + absent stereotype.
  * 1) None stereotype.
  *   Called top-level tier. Means independent aka time alignable tier, gaps are allowed,
  *   annotations overlap is not allowed, and "there is no sharing of time slots between annotations on the same tier"
  *   It looks like that the last statement aims for easy deletion of annotations since gaps are allowed.
  *   Of course, reference to parent tier is not required, and moreover it is impossible to create one in ELAN.
  *   We will forbid that too.
  * 2) Time Subdivision tier stereotype.
  *   It divides parent tier (it is strictly required, yes) into smaller segments directly linked to time slots
  *   (so it is time alignable). These segments must immediately follow each other on one annotation of parent tier,
  *   so that end time slot of the previous annotation is start time slot of the next. The annotation of parent tier
  *   shares start time slot with the first annotation of the time subdivisioned tier, and end time slot is shared with
  *   the last annotation of the time subdivisioned tier.
  *
  *   No gaps are allowed inside subdivisioned annotation of parent tier: the annotation is either subdivisioned fully
  *   or not subdivisioned at all.
  *   Well, I think we need some examples here.
  *
  *   Say, this is the top-level tier named parentTier:
  *
  *     ts1               ts2     ts3     ts4 ts5           ts6
  *      |-----------------|.......|--------||---------------|
  *
  *   Dashes are annotations, dots are gaps. Time slots 4 and 5 point to the same time, but, as we remember, there is
  *   no sharing of time slots between annotations of the same top-level tier. So we have here 3 time-aligned
  *   annotations: ts1-ts2, ts3-ts4, ts5-ts6
  *   The following Time Subdivision tier named subdivisionedTier is allowed:
  *
  *     ts1    ts7   ts8   ts2     ts3    ts4 ts5           ts6
  *      |------|-----|-----|.......|........||--------------|
  *
  *   It has four time-aligned annotations: ts1-ts7, ts7-ts8, ts8-ts2 and ts5-ts6. Note that
  *   * Tiers share ts1 and ts2 time slots
  *   * Start and end time slots of subdivisionedTier are shared (ts7 and ts8), unlike in parentTier
  *   * Annotations ts1-ts2 and ts5-ts6 of the parent tier are fully subdivisioned, there is no gaps
  *   * Annotation ts3-ts4 of the parent tier is not subdivisioned at all, which is allowed
  *   * Of course, we can't have any subdivisionedTier's annotations outside parentTier's annotations.
  *
  *   If we will delete, say, annotation ts7-ts8, the remained annotations must expand to fill the space. ELAN does
  *   it left to right, so ts1-ts7 annotation will expand to ts1-ts8.
  *   On the other hand, if we create a little annotation inside ts3-ts4, it must immediately expand to ts3-s4 to avoid
  *   gaps.
  *
  *   As we can see here, each Time Subdivision's tier annotation clearly has not just parent tier, but a parent
  *   annotation in this tier which it divides. However, EAF format has no means to show that, so we should compute it
  *   ourselves.
  * 3) Included In stereotype.
  *   Like Time Subdivision, but gaps are allowed. It is time alignable, parent tier is
  *   required. Time slots are NOT shared nor with parent tier annotation, neither among Included In tier annotations.
  *   Annotations outside parent tier's annotations are not allowed.
  *   Honestly, I didn't find any real-world example on the internet. It seems that it is not a very popular type.
  *
  *   From implementation point of view, we should only track that new annotations are inserted (old expanded) inside
  *   parent tier's annotations. Nothing is expanded on deletion.
  *   The curious moment is what is happening when we insert an annotation spanning two neighbor annotations of the
  *   parent tier: say, we insert annotation ts3-tsx where tsx lays between ts5 and ts6 on the example above.
  *   Despite the fact that we haven't gone out of parent tier's annotation space, ELAN will cut it down to ts3-ts4.
  *   It means that again, although EAF supports no explicit reference from Included In tier's annotation to the
  *   parent tier's annotation, in fact it always exists.
  * 4) Symbolic Subdivision.
  *   Like Time Subdivision in a sense that it divides parent tier's annotations, but now these dividing annotations
  *   have no time interval, they just point to parent's annotation. The order is provided (and enforced, it is not
  *   optional for non-first annotations) via PREVIOUS_ANNOTATION attribute. Parent tier is required, tier is not time
  *   alignable, each annotation is a ref annotation and thus has an explicit reference to some parent tier's
  *   annotation.
  *
  *   Example, parentTier:
  *     ts1               ts2     ts3     ts4 ts5           ts6
  *      |-----------------|.......|--------||---------------|
  *
  *   Symbolic Subdivision tier:
  *
  *      ts1              ts2     ts3    ts4 ts5           ts6
  *      |--an1-|-an2------|.......|........||------an3------|
  *
  *   Annotations an1 and an2 point to parent's ts1-ts2 annotation. Annotation an2 has an1 as PREVIOUS_ANNOTATION.
  * 5) Symbolic Association
  *   Like Symbolic Subdivision, but only one child annotation per parent's annotation is allowed. Parent tier is
  *   required, tier is not time alignable, each annotation is a ref annotation and has an explicit reference to
  *   parent tier's annotation.
  *
  *   Example, Symbolic Association tier:
  *
  *      ts1              ts2     ts3    ts4 ts5           ts6
  *      |-----an1----------|.......|........||------an2------|
  *
  *
  * Now, who can be who's parent? Top-level tier (without parent) can be only top-level, i.e. without stereotype.
  * Then, any parenting is allowed except for the case when time alignable tier inherits from non time alignable --
  * -- obviously, it doesn't make much sense.
  *
  * Useful links:
  * http://www.mpi.nl/tools/elan/EAF_Annotation_Format.pdf -- EAF format specification
  * http://www.mpi.nl/corpus/html/elan/ch02.html#Fig_Tier_dependencies_in_the_timeline_viewer -- chapter on Annotations
  *   in ELAN's users guide
  * http://www.hrelp.org/events/workshops/aaken2013/assets/aj_elan.pdf
  *
  * @param stereotype
  * @param description
  */

@JSExportAll
class Constraint(val stereotype: RequiredXMLAttr[String], val description: OptionalXMLAttr[String]) {
  def this(stereotype: String, description: Option[String]) =
    this(RequiredXMLAttr(Constraint.stereotypeAttrName, stereotype), OptionalXMLAttr(Constraint.descrAttrName, description))
  override def toString = s"<${Constraint.tagName} $stereotype $description/>"
}

object Constraint {
  // Four predefined constraints
  def predefinedConstraints = Map(
    timeSubdivID -> new Constraint(timeSubdivID, Some(timeSubdivDescr)),
    symbolSubdivID ->new Constraint(symbolSubdivID, Some(symbolSubdivDescr)),
    symbolAssocID -> new Constraint(symbolAssocID, Some(symbolAssocDescr)),
    includedInID -> new Constraint(includedInID, Some(includedInDescr))
  )

  val (tagName, stereotypeAttrName, descrAttrName) = ("CONSTRAINT", "STEREOTYPE", "DESCRIPTION")

  val (timeSubdivID, timeSubdivDescr) = ("Time_Subdivision", "Time subdivision of parent annotation's time interval, no time gaps allowed within this interval")
  val (symbolSubdivID, symbolSubdivDescr) = ("Symbolic_Subdivision", "Symbolic subdivision of a parent annotation. Annotations refering to the same parent are ordered")
  val (symbolAssocID, symbolAssocDescr) = ("Symbolic_Association", "1-1 association with a parent annotation")
  val (includedInID, includedInDescr) = ("Included_In", "Time alignable annotations within the parent annotation's time interval, gaps are allowed")
}


