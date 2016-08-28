package ru.ispras.lingvodoc.frontend.app.controllers

import org.scalajs.dom
import org.scalajs.dom.raw.MouseEvent
import scala.collection.mutable
import scala.scalajs.js
import ru.ispras.lingvodoc.frontend.app.services.{ModalInstance, ModalService}
import com.greencatsoft.angularjs.core.{Timeout, Scope}
import com.greencatsoft.angularjs.{Angular, AbstractController, injectable}
import ru.ispras.lingvodoc.frontend.app.model.{Perspective, Language, Dictionary}
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import ru.ispras.lingvodoc.frontend.extras.facades.{WaveSurfer, WaveSurferOpts}
import ru.ispras.lingvodoc.frontend.extras.elan.{ELANPArserException, ELANDocumentJquery}
import org.scalajs.dom.{EventTarget, console}
import org.singlespaced.d3js.{Selection, d3}
import scala.scalajs.js.JSConverters._
import ru.ispras.lingvodoc.frontend.app.utils.LingvodocExecutionContext.Implicits.executionContext
import org.scalajs.jquery._

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport

@js.native
trait SoundMarkupScope extends Scope {
  var ruler: Double = js.native // coordinate of wavesurfer ruler
  var elan: ELANDocumentJquery = js.native
  var ws: WaveSurfer = js.native // for debugging, remove later
  var tierWidth: Int = js.native // displayed tier width in pixels
  var tiersNameWidth: Int = js.native // column with tier names width in pixels
}

@injectable("SoundMarkupController")
class SoundMarkupController(scope: SoundMarkupScope,
                            timeout: Timeout,
                            instance: ModalInstance[Unit],
                            modal: ModalService,
                            backend: BackendService,
                            params: js.Dictionary[js.Function0[js.Any]])
  extends AbstractController[SoundMarkupScope](scope) {
  scope.tierWidth = 40
  scope.tiersNameWidth = 100

  var waveSurfer: Option[WaveSurfer] = None
  var soundMarkup: Option[String] = None
//  val soundAddress = params.get("soundAddress").map(_.toString)
  val soundAddress = Some("http://localhost/getting_closer.wav")
  val dictionaryClientId = params.get("dictionaryClientId").map(_.toString.toInt)
  val dictionaryObjectId = params.get("dictionaryObjectId").map(_.toString.toInt)

  // hack to distinguish situation when ws is sought by human or by us
  var isWSSeeked = false
  // listen to svg mouseover while true, ignore it when false
  var svgIsMouseDown = false
  // true after first drag event, false after dragend
  var isDragging = false
  // true when we move right border of selection rectangle, false when left
  var rightBorderIsMoving = true

  // d3 selection rectangle element
  var selectionRectangle: Option[Selection[EventTarget]] = None


  // add scope to window for debugging
  dom.window.asInstanceOf[js.Dynamic].myScope = scope

  // hack to initialize controller after loading the view
  // see http://stackoverflow.com/questions/21715256/angularjs-event-to-call-after-content-is-loaded
  @JSExport
  def createWaveSurfer(): Unit = {
    if (waveSurfer.isEmpty) {
      // params should be synchronized with sm-ruler css
      val wso = WaveSurferOpts("#waveform", waveColor = "violet", progressColor = "purple",
                               cursorWidth = 1, cursorColor = "red")
      waveSurfer = Some(WaveSurfer.create(wso))
      (waveSurfer, soundAddress).zipped.foreach((ws, sa) => {
        ws.load(sa)
      })
      waveSurfer.foreach(_.on("seek", onWSSeek _)) // bind seek event
      waveSurfer.foreach(_.on("audioprocess", onWSPlaying _)) // bind playing event
      scope.ws = waveSurfer.get
      init()
    } // do not write anything here, outside if!
  }

  // In contract to the constructor, this method is called when waversurfer is already loaded
  def init(): Unit = {
    //  (dictionaryClientId, dictionaryObjectId).zipped.foreach((dictionaryClientId, dictionaryObjectId) => {
    //    backend.getSoundMarkup(dictionaryClientId, dictionaryObjectId) onSuccess {
    //      case markup => parseMarkup(markup)
    //    }
    //  })
    parseMarkup("fff", waveSurfer.map(_.getDuration().toLong * 1000).getOrElse(Long.MaxValue))

    selectionRectangle = Some(d3.select("#selectionRect"))
  }

  def parseMarkup(markup: String, duration: Long): Unit = {
    val test_markup =
      """<?xml version="1.0" encoding="UTF-8"?>
         <ANNOTATION_DOCUMENT AUTHOR="" DATE="2016-08-28T15:55:36+03:00" FORMAT="2.8" VERSION="2.8" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.mpi.nl/tools/elan/EAFv2.8.xsd">
             <HEADER MEDIA_FILE="" TIME_UNITS="milliseconds">
                 <MEDIA_DESCRIPTOR MEDIA_URL="file:///home/ars/tmp/tmp/Six_Degrees_Of_Inner_Turbulence.wav" MIME_TYPE="audio/x-wav" RELATIVE_MEDIA_URL="./Six_Degrees_Of_Inner_Turbulence.wav"/>
                 <PROPERTY NAME="URN">urn:nl-mpi-tools-elan-eaf:a0e42b2b-d6a1-47a7-92ed-f54285fb6186</PROPERTY>
                 <PROPERTY NAME="lastUsedAnnotationId">11</PROPERTY>
             </HEADER>
             <TIME_ORDER>
                 <TIME_SLOT TIME_SLOT_ID="ts1" TIME_VALUE="1110"/>
                 <TIME_SLOT TIME_SLOT_ID="ts2" TIME_VALUE="1270"/>
                 <TIME_SLOT TIME_SLOT_ID="ts3" TIME_VALUE="2080"/>
                 <TIME_SLOT TIME_SLOT_ID="ts4" TIME_VALUE="2760"/>
                 <TIME_SLOT TIME_SLOT_ID="ts5" TIME_VALUE="2760"/>
                 <TIME_SLOT TIME_SLOT_ID="ts6" TIME_VALUE="3110"/>
                 <TIME_SLOT TIME_SLOT_ID="ts7" TIME_VALUE="3380"/>
                 <TIME_SLOT TIME_SLOT_ID="ts8" TIME_VALUE="3690"/>
                 <TIME_SLOT TIME_SLOT_ID="ts9" TIME_VALUE="3690"/>
                 <TIME_SLOT TIME_SLOT_ID="ts10" TIME_VALUE="3690"/>
                 <TIME_SLOT TIME_SLOT_ID="ts11" TIME_VALUE="4770"/>
             </TIME_ORDER>
             <TIER DEFAULT_LOCALE="en" LINGUISTIC_TYPE_REF="top_level" TIER_ID="toplevel">
                 <ANNOTATION>
                     <ALIGNABLE_ANNOTATION ANNOTATION_ID="a1" TIME_SLOT_REF1="ts1" TIME_SLOT_REF2="ts3">
                         <ANNOTATION_VALUE>грузите</ANNOTATION_VALUE>
                     </ALIGNABLE_ANNOTATION>
                 </ANNOTATION>
                 <ANNOTATION>
                     <ALIGNABLE_ANNOTATION ANNOTATION_ID="a2" TIME_SLOT_REF1="ts4" TIME_SLOT_REF2="ts8">
                         <ANNOTATION_VALUE>бочки апельсины</ANNOTATION_VALUE>
                     </ALIGNABLE_ANNOTATION>
                 </ANNOTATION>
                 <ANNOTATION>
                     <ALIGNABLE_ANNOTATION ANNOTATION_ID="a3" TIME_SLOT_REF1="ts9" TIME_SLOT_REF2="ts11">
                         <ANNOTATION_VALUE>командовать</ANNOTATION_VALUE>
                     </ALIGNABLE_ANNOTATION>
                 </ANNOTATION>
             </TIER>
             <TIER DEFAULT_LOCALE="en" LINGUISTIC_TYPE_REF="time_subdivision" PARENT_REF="toplevel" TIER_ID="time_subdivision">
                 <ANNOTATION>
                     <ALIGNABLE_ANNOTATION ANNOTATION_ID="a4" TIME_SLOT_REF1="ts1" TIME_SLOT_REF2="ts2">
                         <ANNOTATION_VALUE>г</ANNOTATION_VALUE>
                     </ALIGNABLE_ANNOTATION>
                 </ANNOTATION>
                 <ANNOTATION>
                     <ALIGNABLE_ANNOTATION ANNOTATION_ID="a5" TIME_SLOT_REF1="ts2" TIME_SLOT_REF2="ts3">
                         <ANNOTATION_VALUE>рузите</ANNOTATION_VALUE>
                     </ALIGNABLE_ANNOTATION>
                 </ANNOTATION>
             </TIER>
             <TIER DEFAULT_LOCALE="en" LINGUISTIC_TYPE_REF="included_in" PARENT_REF="toplevel" TIER_ID="included_in">
                 <ANNOTATION>
                     <ALIGNABLE_ANNOTATION ANNOTATION_ID="a6" TIME_SLOT_REF1="ts5" TIME_SLOT_REF2="ts6">
                         <ANNOTATION_VALUE>бочки</ANNOTATION_VALUE>
                     </ALIGNABLE_ANNOTATION>
                 </ANNOTATION>
                 <ANNOTATION>
                     <ALIGNABLE_ANNOTATION ANNOTATION_ID="a7" TIME_SLOT_REF1="ts7" TIME_SLOT_REF2="ts10">
                         <ANNOTATION_VALUE>апельсины</ANNOTATION_VALUE>
                     </ALIGNABLE_ANNOTATION>
                 </ANNOTATION>
             </TIER>
             <TIER DEFAULT_LOCALE="en" LINGUISTIC_TYPE_REF="symbolic_subdivision" PARENT_REF="toplevel" TIER_ID="symbolic_association">
                 <ANNOTATION>
                     <REF_ANNOTATION ANNOTATION_ID="a8" ANNOTATION_REF="a1">
                         <ANNOTATION_VALUE>load</ANNOTATION_VALUE>
                     </REF_ANNOTATION>
                 </ANNOTATION>
                 <ANNOTATION>
                     <REF_ANNOTATION ANNOTATION_ID="a9" ANNOTATION_REF="a2">
                         <ANNOTATION_VALUE>barrels oranges</ANNOTATION_VALUE>
                     </REF_ANNOTATION>
                 </ANNOTATION>
             </TIER>
             <TIER DEFAULT_LOCALE="en" LINGUISTIC_TYPE_REF="symbolic_subdivision" PARENT_REF="toplevel" TIER_ID="symbolic_subdivision">
                 <ANNOTATION>
                     <REF_ANNOTATION ANNOTATION_ID="a10" ANNOTATION_REF="a2">
                         <ANNOTATION_VALUE>barrels</ANNOTATION_VALUE>
                     </REF_ANNOTATION>
                 </ANNOTATION>
                 <ANNOTATION>
                     <REF_ANNOTATION ANNOTATION_ID="a11" ANNOTATION_REF="a2" PREVIOUS_ANNOTATION="a10">
                         <ANNOTATION_VALUE>oranges</ANNOTATION_VALUE>
                     </REF_ANNOTATION>
                 </ANNOTATION>
             </TIER>
             <LINGUISTIC_TYPE GRAPHIC_REFERENCES="false" LINGUISTIC_TYPE_ID="top_level" TIME_ALIGNABLE="true"/>
             <LINGUISTIC_TYPE CONSTRAINTS="Symbolic_Subdivision" GRAPHIC_REFERENCES="false" LINGUISTIC_TYPE_ID="symbolic_subdivision" TIME_ALIGNABLE="false"/>
             <LINGUISTIC_TYPE CONSTRAINTS="Symbolic_Association" GRAPHIC_REFERENCES="false" LINGUISTIC_TYPE_ID="symbolic_association" TIME_ALIGNABLE="false"/>
             <LINGUISTIC_TYPE CONSTRAINTS="Time_Subdivision" GRAPHIC_REFERENCES="false" LINGUISTIC_TYPE_ID="time_subdivision" TIME_ALIGNABLE="true"/>
             <LINGUISTIC_TYPE CONSTRAINTS="Included_In" GRAPHIC_REFERENCES="false" LINGUISTIC_TYPE_ID="included_in" TIME_ALIGNABLE="true"/>
             <LOCALE COUNTRY_CODE="US" LANGUAGE_CODE="en"/>
             <CONSTRAINT DESCRIPTION="Time subdivision of parent annotation's time interval, no time gaps allowed within this interval" STEREOTYPE="Time_Subdivision"/>
             <CONSTRAINT DESCRIPTION="Symbolic subdivision of a parent annotation. Annotations refering to the same parent are ordered" STEREOTYPE="Symbolic_Subdivision"/>
             <CONSTRAINT DESCRIPTION="1-1 association with a parent annotation" STEREOTYPE="Symbolic_Association"/>
             <CONSTRAINT DESCRIPTION="Time alignable annotations within the parent annotation's time interval, gaps are allowed" STEREOTYPE="Included_In"/>
         </ANNOTATION_DOCUMENT>
      """
      scope.elan = ELANDocumentJquery(test_markup, duration)
      console.log(scope.elan.toString)
      scope.ruler = 0
  }

  @JSExport
  def getWaveSurferWidth = js.Dynamic.global.document.getElementById("waveform").scrollWidth.toString.toDouble

  @JSExport
  def getWaveSurferHeight = js.Dynamic.global.document.getElementById("waveform").scrollHeight.toString.toDouble

  def svgSeek(offset: Double, forceApply: Boolean = false): Unit = {
    isWSSeeked = true
    setRulerOffset(offset, forceApply)
    val progress = offset / getWaveSurferWidth
    waveSurfer.foreach(_.seekTo(progress))
  }

  def setRulerProgress(progress: Double, forceApply: Boolean = false, applyTimeout: Boolean = false): Unit =
    setRulerOffset(progress * getWaveSurferWidth, forceApply, applyTimeout)

  def setRulerOffset(offset: Double, forceApply: Boolean = false, applyTimeout: Boolean = false): Unit = {
    val action = () => { scope.ruler = offset }
    if (applyTimeout)
      timeout(action)
    else if (forceApply)
      scope.$apply({
        action()
      })
    else
      action()
  }

  // not needed
  @JSExport
  def getDrawerWidth: Double = {
    waveSurfer.map(_.drawer.width.toString.toDouble).getOrElse(0)
  }
  @JSExport
  def getDrawerHeight: Double = {
    waveSurfer.map(_.drawer.height.toString.toDouble).getOrElse(0)
  }

  @JSExport
  def playPause() = waveSurfer.foreach(_.playPause())

  @JSExport
  def play(start: Int, end: Int) = waveSurfer.foreach(_.play(start, end))

  @JSExport
  def save(): Unit = {
    instance.close(())
  }

  @JSExport
  def cancel(): Unit = {
    instance.close(())
  }

  def onWSSeek(progress: Double): Unit = {
    console.log("ws seeked")
    if (isWSSeeked)
      isWSSeeked = false
    else
      setRulerProgress(progress, forceApply = true)
  }

  def onWSPlaying(): Unit = {
    val progress = waveSurfer.map(ws => ws.getCurrentTime() / ws.getDuration())
    progress.foreach(p => setRulerProgress(p, applyTimeout = true))
  }

  // called when user clicks on svg, sets ruler to this place
  @JSExport
  def onSVGSeek(event: js.Dynamic): Unit = {
    console.log("svg seeking")
    svgSeek(event.offsetX.asInstanceOf[Double])
  }

  // called on svg mouse down, prepares for dragging
  @JSExport
  def onSVGMouseDown(event: js.Dynamic): Unit = {
    console.log("svg mouse down")
    svgIsMouseDown = true
    isDragging = false
  }

  @JSExport
  // called on svg mouse up, finished dragging
  def onSVGMouseUp(event: js.Dynamic): Unit = {
    console.log("svg mouse up")
    svgIsMouseDown = false
  }

  @JSExport
  // called on svg mouse moving and extends/shrinks the selection rectangle if mouse down event happened earlier
  def onSVGMouseMove(event: js.Dynamic): Unit = {
    if (!svgIsMouseDown)
      return

//    console.log(s"mouse moving at offset ${event.offsetX}")
    val cursorX = Math.min(getWaveSurferWidth, Math.max(0, event.offsetX.toString.toDouble))
    if (!isDragging) { // executed on first mouse move event
      selectionRectangle.foreach(_.attr("x", cursorX).attr("width", 0))
      isDragging = true
    }
    else { // executed on every subsequent mouse move event
      val oldX = selectionRectangle.get.attr("x").toString.toDouble
      val oldWidth = selectionRectangle.get.attr("width").toString.toDouble

      if ((rightBorderIsMoving && cursorX > oldX) ||
          (!rightBorderIsMoving && cursorX >= oldX + oldWidth)) {
        if (!rightBorderIsMoving) // first event with right border moving, just after changing left to right
          selectionRectangle.foreach(_.attr("x", oldX + oldWidth).attr("width", cursorX - oldX - oldWidth))
        else // right border is still moving
          selectionRectangle.foreach(_.attr("width", cursorX - oldX))
        rightBorderIsMoving = true
      }
      else {
        if (rightBorderIsMoving) // first event after right -> left border moving
          selectionRectangle.foreach(_.attr("x", cursorX).attr("width", oldX - cursorX))
        else // left border is still moving
          selectionRectangle.foreach(_.attr("x", cursorX).attr("width", oldX + oldWidth - cursorX))
        rightBorderIsMoving = false
      }

      svgSeek(cursorX)
    }
  }

  def onSelectionDragStart() = {
    console.log("starting dragging")
  }

  def onSelectionDragging() = {
    console.log("dragging")
    if (!isDragging) { // executed on first drag event
      selectionRectangle.foreach(_.remove())
      selectionRectangle = Some(d3.select("#soundSVG").append("rect")
        .attr("x", d3.event.asInstanceOf[js.Dynamic].x.toString.toDouble)
        .attr("y", 0)
        .attr("width", 0)
        .attr("height", getWaveSurferHeight)
        .attr("class", "sm-selecton-rectangle"))
      isDragging = true
    }
    else { // executed on every subsequent drag event
      val (oldx, cursorx) = (selectionRectangle.get.attr("x").toString.toDouble,
        Math.min(getWaveSurferWidth, Math.max(0, d3.event.asInstanceOf[js.Dynamic].x.toString.toDouble)))
      val oldWidth = selectionRectangle.get.attr("width").toString.toDouble

      if ((rightBorderIsMoving && cursorx > oldx) || (!rightBorderIsMoving && cursorx >= oldx + oldWidth)) {
        selectionRectangle.foreach(_.attr("width", cursorx - oldx))
        rightBorderIsMoving = true
      }
      else {
        selectionRectangle.foreach(_.attr("x", cursorx).attr("width", oldx + oldWidth - cursorx))
        rightBorderIsMoving = false
      }

      svgSeek(cursorx, forceApply = true)
    }
  }
  def onSelectionDragEnd() = {
    console.log("ending dragging")
    isDragging = false
  }

  @JSExport
  def md(event: js.Dynamic) = {
    console.log("hi from md")
  }
  @JSExport
  def mm(event: js.Dynamic) = {
    console.log("hi from mm")
  }
  @JSExport
  def mu(event: js.Dynamic) = {
    console.log("hi from mu")
  }
}

