//package ru.ispras.lingvodoc.frontend.extras.elan
//
//case class ELANPArserException(message: String) extends Exception(message)

//case class LinguisticType(id: String, graphicReferences: Boolean, typeAlignable: Boolean) {
//  def toXML: xml.Elem = <LINGUISTIC_TYPE GRAPHIC_REFERENCES={graphicReferences.toString}
//                                         LINGUISTIC_TYPE_ID={id} TIME_ALIGNABLE={typeAlignable.toString}/>
//}
//// there are some more currently unsupported elements
//case class Locale(countryCode: String, languageCode: String, variant: String) {
//  def toXML: xml.Elem = <LOCALE COUNTRY_CODE={countryCode} LANGUAGE_CODE={languageCode}/>
//}
//
//// see http://www.mpi.nl/tools/elan/EAF_Annotation_Format.pdf for format specification
//class ELANDocument(xmlstring: String) {
//  var author, date, version = ""
//  var timeSlots =  Map[Int, String]()
//  var linguisticType = LinguisticType("", false, false)
//  var locale = Locale("", "", "")
//  var tiers = List[Tier]()
//  // users can add timeslots, so we will need new ids. Points to smallest available id
//  private var _nextTimeSlotId = 0
//  // global for all tiers -- it is more convenient since we can store custom fields only in HEAD->PROPERTIES
//  private var _nextAnnotationId = 0
//
//  importXML(xml.XML.loadString(xmlstring))
//
//  def addTier(id: String, lingTypeRef: String, participant: String = "", annotator: String = "",
//              defaultLocale: String = "", parentRef: String = ""): Tier = {
//    val tier = new Tier(this, List[Annotation](), (id, lingTypeRef, participant, annotator, defaultLocale, parentRef))
//    tiers ::= tier; tier
//  }
//
//  override def toString = "ELAN document tiers:\n" + tiers.toString
//
//  def exportXML(): xml.Elem = {
//    <ANNOTATION_DOCUMENT AUTHOR={author} DATE={date} VERSION={version}>
//      {headerToXML}
//      {timeSlotsToXML}
//      { for (tier <- tiers) yield
//      tier.toXML
//      }
//      {linguisticType.toXML}
//      {locale.toXML}
//    </ANNOTATION_DOCUMENT>
//  }
//
//  private [elan] def findTimeSlotByValue(value: String): Option[Int] =
//    (for (ts <- timeSlots if ts._2 == value) yield ts._1).headOption
//  private [elan] def addTimeSlot(value: String): Int = {val ref = issueTimeSlotId(); timeSlots += ref -> value; ref}
//  private [elan] def findOrAddTimeSlot(value: String): Int = findTimeSlotByValue(value) match {
//    case Some(ref) => ref
//    case None => addTimeSlot(value)
//  }
//
//  private [elan] def issueTimeSlotId(): Int = {val t = _nextTimeSlotId; _nextTimeSlotId += 1; t}
//  private [elan] def issueAnnotationId(): Int = {val t = _nextAnnotationId; _nextAnnotationId += 1; t}
//
//
//  private def headerToXML: xml.Elem = {
//    <HEADER TIME_UNITS="milliseconds">
//      <PROPERTY NAME="nextTimeSlotId">{_nextTimeSlotId}</PROPERTY>
//      <PROPERTY NAME="nextAnnotationId">{_nextAnnotationId}</PROPERTY>
//    </HEADER>
//  }
//
//  private def timeSlotsToXML: xml.Elem = {
//    <TIME_ORDER>
//      { for (ts <- timeSlots) yield
//        <TIME_SLOT TIME_SLOT_ID={ts._1.toString} TIME_VALUE={ts._2.toString}/>
//      }
//    </TIME_ORDER>
//  }
//
//  private def importXML(x: xml.Elem): Unit = {
//    author = x \@ "AUTHOR"
//    date = x \@ "DATE"
//    version = x \@ "VERSION"
//
//    val header = x \ "HEADER"
//    if ((header \ "@TIME_UNITS").text != "milliseconds")
//      throw ELANPArserException("TIME_UNITS must be milliseconds in ELAN")
//
//    val properties = header \ "PROPERTY"
//    val nextTimeSlotIdNode = properties.findElementbyAttrValue("NAME", "nextTimeSlotId")
//    val nextTimeAnnotationIdNode = properties.findElementbyAttrValue("NAME", "nextAnnotationId")
//    // true, if we have previously imported this xml at least once
//    val ourXML = nextTimeSlotIdNode.nonEmpty && nextTimeAnnotationIdNode.nonEmpty
//    if (ourXML) {
//      _nextTimeSlotId = nextTimeSlotIdNode.get.text.toInt
//      _nextAnnotationId = nextTimeAnnotationIdNode.get.text.toInt
//    }
//
//    val ltNode = x \ "LINGUISTIC_TYPE"
//    linguisticType = LinguisticType(ltNode \@ "LINGUISTIC_TYPE_ID", (ltNode \@ "GRAPHIC_REFERENCES") == "true", (ltNode \@ "TIME_ALIGNABLE") == "true")
//    val localeNode = x \ "LOCALE"
//    locale = Locale(localeNode \@ "COUNTRY_CODE", localeNode \@ "LANGUAGE_CODE", localeNode \@ "VARIANT")
//
//    val timeSlotsFromXML = parseTimeSlots(x \ "TIME_ORDER")
//    var stringTimeSlotIdsToInts = Map[String, Int]()
//    if (ourXML)
//      timeSlots = timeSlotsFromXML.map { case (tsId, tsValue) => tsId.toInt -> tsValue }
//    else
//      timeSlotsFromXML.foreach{ ts =>
//        val timeSlotId = issueTimeSlotId()
//        timeSlots += timeSlotId -> ts._2
//        stringTimeSlotIdsToInts += ts._1 -> timeSlotId
//      }
//
//    (x \ "TIER").foreach { tierNode =>
//      tiers ::= Tier(tierNode, this, ourXML, stringTimeSlotIdsToInts)
//    }
//  }
//
//  private def parseTimeSlots(x: xml.NodeSeq): Map[String, String] = {
//    (x \ "TIME_SLOT" map{tsNode => tsNode \@ "TIME_SLOT_ID" -> tsNode \@ "TIME_VALUE"}).toMap
//  }
//}
//
//class Tier private[elan] (val parent: ELANDocument, var annotations: List[Annotation],
//           attrs: Tuple6[String, String, String, String, String, String]) {
//  val (id, lingTypeRef, participant, annotator, defaultLocale, parentRef) = attrs
//  override def toString = s"Tier id $id, annotations:\n" + (for (a <- annotations) yield a.toString).mkString
//
//  def addAnnotation(timeSlot1: String, timeSlot2: String, value: String): Annotation = {
//    val timeSlotRef1 = parent.findOrAddTimeSlot(timeSlot1)
//    val timeSlotRef2 = parent.findOrAddTimeSlot(timeSlot2)
//    val annotation = Annotation(parent.issueAnnotationId(), timeSlotRef1, timeSlotRef2, value)
//    annotations ::= annotation; annotation
//  }
//
//  def toXML: xml.Elem = {
//    <TIER DEFAULT_LOCALE={defaultLocale} LINGUISTIC_TYPE_REF={lingTypeRef} TIER_ID={id} PARTICIPANT={participant}
//          ANNOTATOR={annotator} PARENT_REF={parentRef}>
//      { for (annotation <- annotations) yield
//      annotation.toXML
//      }
//    </TIER>
//  }
//}
//
//object Tier {
//  private [elan] def apply(x: xml.Node, parent: ELANDocument,
//            oursXML: Boolean, stringTimeSlotIdsToInts: Map[String, Int] = Map[String, Int]()): Tier = {
//    val (id, locale, participant) = (x \@ "TIER_ID", x \@ "DEFAULT_LOCALE", x \@ "PARTICIPANT")
//    val (annotator, lingTypeRef, parentRef) = (x \@ "ANNOTATOR", x \@ "LINGUISTIC_TYPE_REF", x \@ "PARENT_REF")
//    val tier = new Tier(parent, List[Annotation](), (id, lingTypeRef, participant, annotator, locale, parentRef))
//    (x \ "ANNOTATION").foreach { annotationNode =>
//      tier.annotations ::= Annotation(annotationNode, tier, oursXML, stringTimeSlotIdsToInts)
//    }
//    tier
//  }
//}
//
//case class Annotation(id: Int, timeSlotRef1: Int, timeSlotRef2: Int, value: String) {
//  def toXML: xml.Elem = {
//    <ANNOTATION>
//      <ALIGNABLE_ANNOTATION ANNOTATION_ID={id.toString} TIME_SLOT_REF1={timeSlotRef1.toString}
//                            TIME_SLOT_REF2={timeSlotRef2.toString}>
//        <ANNOTATION_VALUE>{value}</ANNOTATION_VALUE>
//      </ALIGNABLE_ANNOTATION>
//    </ANNOTATION>
//  }
//
//  override def toString = s"AnnotationId=$id, timeSlotRef1=$timeSlotRef1, timeSlotRef2=$timeSlotRef2, value=$value\n"
//}
//
//object Annotation {
//  private [elan] def apply(annotationNode: xml.Node, parent: Tier,
//            oursXML: Boolean, stringTimeSlotIdsToInts: Map[String, Int] = Map[String, Int]()): Annotation = {
//    if ((annotationNode \ "REF_ANNOTATION").nonEmpty)
//      throw ELANPArserException("REF_ANNOTATION not supported at the moment")
//    val alignAnnotNode = annotationNode \ "ALIGNABLE_ANNOTATION"
//    if (alignAnnotNode.isEmpty)
//      throw ELANPArserException("Annotation is empty!")
//    val (idXML, timeSlotRef1XML) = (alignAnnotNode \@ "ANNOTATION_ID", alignAnnotNode \@ "TIME_SLOT_REF1" )
//    val (timeSlotRef2XML, value) = (alignAnnotNode \@ "TIME_SLOT_REF2", (alignAnnotNode \ "ANNOTATION_VALUE").text)
//    if (oursXML)
//      Annotation(idXML.toInt, timeSlotRef1XML.toInt, timeSlotRef2XML.toInt, value)
//    else {
//      val (timeSlotRef1, timeSlotRef2) = (stringTimeSlotIdsToInts(timeSlotRef1XML), stringTimeSlotIdsToInts(timeSlotRef2XML))
//      Annotation(parent.parent.issueAnnotationId(), timeSlotRef1, timeSlotRef2, value)
//    }
//  }
//}
