package ru.ispras.lingvodoc.frontend.app.controllers

import org.scalajs.dom
import org.scalajs.dom.raw.MouseEvent
import ru.ispras.lingvodoc.frontend.extras.elan.annotation.IAnnotation
import ru.ispras.lingvodoc.frontend.extras.elan.tier.ITier
import scala.collection.mutable
import scala.scalajs.js
import ru.ispras.lingvodoc.frontend.app.services.{ModalInstance, ModalService}
import com.greencatsoft.angularjs.core.{Timeout, Scope}
import com.greencatsoft.angularjs.{Angular, AbstractController, injectable}
import ru.ispras.lingvodoc.frontend.app.model.{Perspective, Language, Dictionary}
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import ru.ispras.lingvodoc.frontend.extras.facades.{MenuOption, BootstrapContextMenu, WaveSurfer, WaveSurferOpts}
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
  var elan: ELANDocumentJquery = js.native // elan document itself
  var ws: WaveSurfer = js.native // for debugging, remove later

  var tierWidth: Int = js.native // displayed tier width in pixels
  var tiersNameWidth: Int = js.native // column with tier names width in pixels
  var fullWSWidth: Double = js.native // full width of displayed wavesurfer canvas
  var menuOptions: js.Array[js.Any] = js.native

  var tmp: js.Dynamic = js.native
}

@injectable("SoundMarkupController")
class SoundMarkupController(scope: SoundMarkupScope,
                            timeout: Timeout,
                            instance: ModalInstance[Unit],
                            modal: ModalService,
                            backend: BackendService,
                            params: js.Dictionary[js.Function0[js.Any]])
  extends AbstractController[SoundMarkupScope](scope) {
  scope.tierWidth = 50
  scope.tiersNameWidth = 140

  scope.menuOptions = new BootstrapContextMenu(
    MenuOption("New Annotation Here", (itemScope: js.Dynamic) => {console.log("new annotation here")})
  ).toJS
  var waveSurfer: Option[WaveSurfer] = None
  private var _minPxPerSec=50
  val pxPerSecStep = 30 // zoom in/out step
  // fake value to avoid division by zero; on ws load, it will be set correctly
  private var _duration: Double = 42.0
  scope.fullWSWidth = 0.0

  var soundMarkup: Option[String] = None
//  val soundAddress = params.get("soundAddress").map(_.toString)
  val soundAddress = Some("http://localhost/getting_closer.wav")
  val dictionaryClientId = params.get("dictionaryClientId").map(_.toString.toInt)
  val dictionaryObjectId = params.get("dictionaryObjectId").map(_.toString.toInt)

  // listen to svg mouseover while true, ignore it when false
  var svgIsMouseDown = false
  // true after first drag event, false after dragend
  var isDragging = false
  // true when we move right border of selection rectangle, false when left
  var rightBorderIsMoving = true
  // true when ws finished loading
  var isWSReady = false
  // When wsSeek is called because user clicked on it, we must manually call apply, because it is not ng-click.
  // However, in ome other cases, e.g. when user clicks on svg and then we update WS ruler, apply must not be called --
  // set this flag to false in such situations.
  var isWSNeedsToForceAngularRefresh = true

  // d3 selection rectangle element
  var selectionRectangle: Option[Selection[EventTarget]] = None


  // add scope to window for debugging
  dom.window.asInstanceOf[js.Dynamic].myScope = scope

  def minPxPerSec = _minPxPerSec
  def minPxPerSec_=(mpps: Int) = {
    _minPxPerSec = mpps
    scope.elan.setPxPerSec(minPxPerSec)
    isWSNeedsToForceAngularRefresh = false
    waveSurfer.foreach(_.zoom(mpps))
    updateFullWSWidth()
  }
  def duration = _duration
  def duration_=(dur: Double) = {
    _duration = dur
    updateFullWSWidth()
  }
  def updateFullWSWidth() = { scope.fullWSWidth = minPxPerSec * duration }

  /**
    * Loading process requires a bit of explanation.
    * 1) We can't load wavesurfer instance until the view is loaded, because WS will not find it's div element
    *   otherwise
    * 2) On the other hand, we can't fully render template without WS instance because we need sound's duration to
    *   calculate right distances.
    * 3) So, loading goes like this:
    *   a) View is loaded with dummy distances, WS width is not known at the moment, scope.elan doesn't exists, etc
    *   b) createWaveSurfer is called, it creates WS instance and binds WS `ready` event to wsReady method. Then markup
    *     is parsed.
    *   c) After that, Angular reloads the view, showing WaveSurfer and tiers/annotations; however, distances are still
    *     dummy, because sound duration is not known
    *   d) When sound is fully loaded, wsReady is triggered and executed. Angular is forced to update the view, and final
    */

  // hack to initialize controller after loading the view
  // see http://stackoverflow.com/questions/21715256/angularjs-event-to-call-after-content-is-loaded
  @JSExport
  def createWaveSurfer(): Unit = {
    if (waveSurfer.isEmpty) {
      // params should be synchronized with sm-ruler css
      val wso = WaveSurferOpts("#waveform", waveColor = "violet", progressColor = "purple",
                               cursorWidth = 1, cursorColor = "red",
                               fillParent=false, minPxPerSec=minPxPerSec, scrollParent=false)
      waveSurfer = Some(WaveSurfer.create(wso))
      (waveSurfer, soundAddress).zipped.foreach((ws, sa) => {
        ws.load(sa)
      })
      waveSurfer.foreach(_.on("seek", onWSSeek _)) // bind seek event
      waveSurfer.foreach(_.on("audioprocess", onWSPlaying _)) // bind playing event
      waveSurfer.foreach(_.on("ready", wsReady _)) // bind playing event
      scope.ws = waveSurfer.get
      init()
    } // do not write anything here, outside if!
  }

  def wsReady(event: js.Dynamic): Unit = {
    console.log("ws ready!")
    isWSReady = true
    duration = getDuration
    scope.$apply({})
  }

  // In contract to the constructor, this method is called when waversurfer is already loaded
  def init(): Unit = {
    //  (dictionaryClientId, dictionaryObjectId).zipped.foreach((dictionaryClientId, dictionaryObjectId) => {
    //    backend.getSoundMarkup(dictionaryClientId, dictionaryObjectId) onSuccess {
    //      case markup => parseMarkup(markup)
    //    }
    //  })
    parseMarkup("fff")

    selectionRectangle = Some(d3.select("#selectionRect"))
  }

  def parseMarkup(markup: String): Unit = {
    val action = (data: js.Dynamic, textStatus: String, jqXHR: js.Dynamic) => {
      console.log(s"got ${textStatus.toString} from jquery get")
      val test_markup = data.toString
      try {
        scope.elan = ELANDocumentJquery(test_markup, minPxPerSec)
        console.log(scope.elan.toString)
      } catch {
        case e: Exception =>
          console.error(e.getStackTrace.mkString("\n"))
          throw e
      }
      scope.ruler = 0
    }

    jQuery.get("http://localhost/test.eaf", success = action, dataType = "text")
  }

  @JSExport
  def getWaveSurferWidth = {
//    console.log(s"width ${js.Dynamic.global.document.getElementById("waveform").scrollWidth.toString} is called");
    js.Dynamic.global.document.getElementById("waveform").scrollWidth.toString.toDouble}

  @JSExport
  def getWaveSurferHeight = {
//    console.log("height is called")
    js.Dynamic.global.document.getElementById("waveform").scrollHeight.toString.toDouble}

  @JSExport
  def getDuration = { if (isWSReady) waveSurfer.get.getDuration() else 42.0 }

  @JSExport
  def getCurrentTime = { if (isWSReady) waveSurfer.get.getCurrentTime() else 42.0 }

  /**
    * We have several metrics fully characterizing point in time:
    * 1) Offset in pxs from svg left border
    * 2) Progress in [0..1] of full sound duration
    * 3) Time in seconds, double
    * 4) Time in milliseconds, Long or String, if called from JS
    */

  // millis is Long number
  @JSExport
  def millisecToOffset(millis: String) = millis.toLong / 1000.0 / getDuration * getWaveSurferWidth

  def offsetToProgress(offset: Double) = offset / getWaveSurferWidth

  def progressToOffset(progress: Double) = progress * getWaveSurferWidth


  // set wavesurfer & svg rulers to @offset pixels from start
  def svgSeek(offset: Double): Unit = {
    // no need to call setRulerOffset here; it will be called automatically because WS will invoke wsSeek itself.
    isWSNeedsToForceAngularRefresh = false // ng-click will call apply
    val progress = offsetToProgress(offset)
    waveSurfer.foreach(_.seekTo(progress))
  }

  def setRulerProgress(progress: Double, forceApply: Boolean = false, applyTimeout: Boolean = false): Unit =
    setRulerOffset(progressToOffset(progress), forceApply, applyTimeout)

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

  @JSExport
  def playPause() = waveSurfer.foreach(_.playPause())

  @JSExport
  def play(start: Int, end: Int) = waveSurfer.foreach(_.play(start, end))

  @JSExport
  def zoomIn(): Unit = { minPxPerSec += pxPerSecStep; }

  @JSExport
  def zoomOut(): Unit = { minPxPerSec -= pxPerSecStep; }

  @JSExport
  def save(): Unit = {
    instance.close(())
  }

  @JSExport
  def cancel(): Unit = {
    instance.close(())
  }

  def onWSSeek(progress: Double): Unit = {
    setRulerProgress(progress, forceApply = isWSNeedsToForceAngularRefresh)
    isWSNeedsToForceAngularRefresh = true
  }

  def onWSPlaying(): Unit = {
    val progress = waveSurfer.map(ws => ws.getCurrentTime() / getDuration)
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
    if (event.which.asInstanceOf[Int] == 1) {
      console.log("svg mouse down")
      svgIsMouseDown = true
      isDragging = false
    }
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
}

