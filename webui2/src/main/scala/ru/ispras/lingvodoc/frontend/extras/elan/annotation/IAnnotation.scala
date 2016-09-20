package ru.ispras.lingvodoc.frontend.extras.elan.annotation

import org.scalajs.jquery.JQuery
import ru.ispras.lingvodoc.frontend.extras.elan.tier.{ITier, AlignableTier, Tier}
import ru.ispras.lingvodoc.frontend.extras.elan.{ELANPArserException, Utils, OptionalXMLAttr, RequiredXMLAttr}

import scala.collection.mutable
import scala.scalajs.js
import scala.scalajs.js.annotation.{JSExportAll, JSExportDescendentObjects, JSExport}
import scala.scalajs.js.JSConverters._

@JSExportDescendentObjects
trait IAnnotation {
  @JSExport
  var text: String

  // Format start, end and duration as a human-readable string for displaying.
  // BTW Long is opaque to scala.js, so we can give only Strings anyway; however, don't use them as numbers.
  @JSExport
  def startToString = f"$startSec%.2f"
  @JSExport
  def endToString = f"$endSec%.2f"
  @JSExport
  def durationToString = f"$durationSec%.2f"
  // convert start, end and duration in seconds to displayed pixels using pxPerSec
  @JSExport
  var startOffset: Double
  @JSExport
  var endOffset: Double
  @JSExport
  var durationOffset: Double
  // recalculate offsets
  def setPxPerSec(pxPerSec: Double)

  @JSExport
  def getID = annotationID.value

  def toJS: js.Dynamic

  val annotationID: RequiredXMLAttr[String]
  val extRef: OptionalXMLAttr[String]
  val owner: ITier[IAnnotation]

  // for ref annotations start and end makes sense only for displaying. Measured in milliseconds.
  def start: Long
  def end: Long
  def duration: Long = end - start

  def startSec = Utils.millis2Sec(start)
  def endSec = Utils.millis2Sec(end)
  def durationSec = Utils.millis2Sec(duration)


  // xml representation of content inside <ANNOTATION></ANNOTATION>
  protected def includedAnnotationToString: String
}

// represents annotationAttribute attribute group and additionally adds ANNOTATION_VALUE element which is the same
// in both ref annotation and alignable annotations too
abstract class Annotation(ao: AnnotationOpts) extends IAnnotation {
  val annotationID = ao.annotationID
  val extRef = ao.extRef
  var text = ao.text
  val owner = ao.owner

  // we will calculate offsets (setPxPerSec method) as soon as whole document will be parsed
  var startOffset: Double = _
  var endOffset: Double = _
  var durationOffset: Double = _

  def toJS = {
    val annotationJS = mutable.Map.empty[String, js.Dynamic]
    annotationJS("text") = text.asInstanceOf[js.Dynamic]
    annotationJS("startOffset") = startOffset.asInstanceOf[js.Dynamic]
    annotationJS("endOffset") = endOffset.asInstanceOf[js.Dynamic]
    annotationJS("durationOffset") = durationOffset.asInstanceOf[js.Dynamic]
    annotationJS("startToString") = startToString.asInstanceOf[js.Dynamic]
    annotationJS("endToString") = endToString.asInstanceOf[js.Dynamic]
    annotationJS("durationToString") = durationToString.asInstanceOf[js.Dynamic]
    annotationJS.toJSDictionary.asInstanceOf[js.Dynamic]
  }

  override def toString = Utils.wrap(Annotation.tagName, includedAnnotationToString)
  // <ANNOTATION_VALUE> tag
  protected final def content = Utils.wrap(Annotation.annotValueElName, text)
  protected def attrsToString = s"$annotationID $extRef"

  def setPxPerSec(pxPerSec: Double) = {
    startOffset = Utils.millis2Sec(start) * pxPerSec
    endOffset = Utils.millis2Sec(end) * pxPerSec
    durationOffset = Utils.millis2Sec(duration) * pxPerSec
  }
}

object Annotation {
  // strip off <ANNOTATION> tag and check first tag inside
  def validateAnnotationType(annotXML: JQuery, allowedAnnot: String, errorMsg: String): JQuery = {
    val includedAnnotationXML = annotXML.children().first
    if (includedAnnotationXML.prop("tagName").toString != allowedAnnot)
      throw new ELANPArserException(errorMsg)
    includedAnnotationXML
  }

  val tagName = "ANNOTATION"
  val (annotIDAttrName, extRefAttrName, annotValueElName) = ("ANNOTATION_ID", "EXT_REF", "ANNOTATION_VALUE")
}

private[annotation] class AnnotationOpts(val annotationID: RequiredXMLAttr[String], val extRef: OptionalXMLAttr[String],
                     var text: String, val owner: ITier[IAnnotation]) {
  def this(includedAnnotationXML: JQuery, owner: ITier[IAnnotation]) = this(
    RequiredXMLAttr(includedAnnotationXML, Annotation.annotIDAttrName),
    OptionalXMLAttr(includedAnnotationXML, Annotation.extRefAttrName),
    includedAnnotationXML.find(Annotation.annotValueElName).text(),
    owner
  )
  def this(annotationID: String, extRef: Option[String], text: String, owner: ITier[IAnnotation]) = this(
    RequiredXMLAttr(Annotation.annotIDAttrName, annotationID),
    OptionalXMLAttr(Annotation.extRefAttrName, extRef),
    text,
    owner
  )
}
