package ru.ispras.lingvodoc.frontend.extras.elan.annotation

import org.scalajs.jquery.JQuery
import ru.ispras.lingvodoc.frontend.extras.elan.tier.{ITier, AlignableTier, Tier}
import ru.ispras.lingvodoc.frontend.extras.elan.{ELANPArserException, Utils, OptionalXMLAttr, RequiredXMLAttr}

import scala.scalajs.js.annotation.{JSExportAll, JSExportDescendentObjects, JSExport}

@JSExportDescendentObjects
trait IAnnotation {
  @JSExport
  var text: String

  // Long is opaque to scala.js, so we can give only these
  @JSExport
  def startToString = start.toString
  @JSExport
  def endToString = end.toString

  @JSExport
  def getID = annotationID.value

  val annotationID: RequiredXMLAttr[String]
  val extRef: OptionalXMLAttr[String]
  val owner: ITier[IAnnotation]

  // for ref annotations start and end makes sense only for displaying. Measured in milliseconds.
  def start: Long
  def end: Long

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

  override def toString = Utils.wrap(Annotation.tagName, includedAnnotationToString)
  // <ANNOTATION_VALUE> tag
   protected final def content = Utils.wrap(Annotation.annotValueElName, text)
  protected def attrsToString = s"$annotationID $extRef"
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