package ru.ispras.lingvodoc.frontend.app.controllers.traits

import com.greencatsoft.angularjs.Controller
import ru.ispras.lingvodoc.frontend.extras.facades.{WaveSurfer, WaveSurferOpts}

import scala.scalajs.js.annotation.JSExport
import com.greencatsoft.angularjs.core.{Scope, Timeout}


trait SimplePlay {

  protected var waveSurfer: Option[WaveSurfer] = None
  protected var _pxPerSec = 50 // minimum pxls per second, all timing is bounded to it
  protected val pxPerSecStep = 30 // zooming step
  // zoom in/out step; fake value to avoid division by zero; on ws load, it will be set correctly
  protected var fullWSWidth = 0.0 // again, will be known after audio load
  protected var wsHeight = 128
  protected var soundMarkup: Option[String] = None

  import org.scalajs.dom.console

  @JSExport
  def createWaveSurfer(): Unit = {
    if (waveSurfer.isEmpty) {

      console.log("wave surfer created")

      // params should be synchronized with sm-ruler css
      val wso = WaveSurferOpts("#waveform", waveColor = "violet", progressColor = "purple",
        cursorWidth = 1, cursorColor = "red",
        fillParent = true, minPxPerSec = pxPerSec, scrollParent = false,
        height = wsHeight)
      waveSurfer = Some(WaveSurfer.create(wso))
    } else {
      console.log("alread created")
    }
  }

  def pxPerSec = _pxPerSec

  def pxPerSec_=(mpps: Int) = {
    _pxPerSec = mpps
    waveSurfer.foreach(_.zoom(mpps))
  }

  @JSExport
  def play(soundAddress: String) = {
    (waveSurfer, Some(soundAddress)).zipped.foreach((ws, sa) => {
      ws.load(sa)
    })
  }

  @JSExport
  def playPause() = waveSurfer.foreach(_.playPause())

  @JSExport
  def play(start: Int, end: Int) = waveSurfer.foreach(_.play(start, end))

  @JSExport
  def zoomIn() = { pxPerSec += pxPerSecStep; }

  @JSExport
  def zoomOut() = { pxPerSec -= pxPerSecStep; }

  @JSExport
  def onReady(w: WaveSurfer) = {
    waveSurfer = Some(w)
  }
}
