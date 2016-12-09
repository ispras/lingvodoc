package ru.ispras.lingvodoc.frontend.app.controllers.traits

import ru.ispras.lingvodoc.frontend.extras.facades.{WaveSurfer, WaveSurferSpectrogramPlugin}

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport


trait SimplePlay {

  protected var waveSurfer: Option[WaveSurfer] = None
  protected var _pxPerSec = 50 // minimum pxls per second, all timing is bounded to it
  protected val pxPerSecStep = 30 // zooming step
  // zoom in/out step; fake value to avoid division by zero; on ws load, it will be set correctly
  //protected var fullWSWidth = 0.0 // again, will be known after audio load
  //protected var wsHeight = 128
  protected var soundMarkup: Option[String] = None


  protected def spectrogramId = "#spectrogram"


  def pxPerSec = _pxPerSec

  def pxPerSec_=(mpps: Int) = {
    _pxPerSec = mpps
    waveSurfer.foreach(_.zoom(mpps))
  }

  @JSExport
  def play(soundAddress: String): Unit = {
    (waveSurfer, Some(soundAddress)).zipped.foreach((ws, sa) => {
      ws.load(sa)
      ws.once("ready", () => {
        ws.playPause()
        drawSpectrogram(ws)
      }: Unit)
    })
  }

  @JSExport
  def playPause(): Unit = waveSurfer.foreach(_.playPause())

  @JSExport
  def play(start: Int, end: Int): Unit = waveSurfer.foreach(_.play(start, end))

  @JSExport
  def zoomIn(): Unit = { pxPerSec += pxPerSecStep; }

  @JSExport
  def zoomOut(): Unit = { pxPerSec -= pxPerSecStep; }

  @JSExport
  def onReady(w: WaveSurfer): Unit = {
    waveSurfer = Some(w)
  }


  private[this] def drawSpectrogram(waveSurfer: WaveSurfer) = {
    val spectrogram = Some(js.Object.create(WaveSurferSpectrogramPlugin).asInstanceOf[js.Dynamic])
    spectrogram.foreach(_.init(js.Dynamic.literal(wavesurfer = waveSurfer, container = spectrogramId, fftSamples = 128)))
  }



}
