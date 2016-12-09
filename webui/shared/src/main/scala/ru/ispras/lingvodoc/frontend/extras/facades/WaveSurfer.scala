package ru.ispras.lingvodoc.frontend.extras.facades

import scala.scalajs.js
import scala.scalajs.js.annotation.JSName

@js.native
trait WaveSurferOpts extends js.Object {
  val container: String = js.native
  val waveColor: String = js.native
  val progressColor: String = js.native
  val cursorWidth: Int = js.native
  val cursorColor: String = js.native
  val scrollParent: Boolean = js.native
  val minPxPerSec: Double = js.native
  val fillParent: Boolean = js.native
  val height: Int = js.native
}

object WaveSurferOpts {
  def apply(container: js.Any, waveColor: String = "#999", progressColor: String = " #555",
            cursorWidth: Int = 1, cursorColor: String = "#333", scrollParent: Boolean = false,
            minPxPerSec: Double = 50, fillParent: Boolean = true, height: Int = 128): WaveSurferOpts = {
    js.Dynamic.literal(
      container = container,
      waveColor = waveColor,
      progressColor = progressColor,
      cursorWidth = cursorWidth,
      cursorColor = cursorColor,
      scrollParent = scrollParent,
      minPxPerSec = minPxPerSec,
      fillParent = fillParent,
      height = height,
      mediaControls = false,
      autoplay = false
    ).asInstanceOf[WaveSurferOpts]
  }
}

@js.native
trait WaveSurfer extends js.Object {
  def destroy(): js.Any = js.native
  def getCurrentTime(): Double = js.native
  def getDuration(): Double = js.native
  def load(url: String): js.Dynamic = js.native
  def playPause(): js.Any = js.native
  def play(start: Double = 0, end: Double = Double.MaxValue): js.Any = js.native
  def on(event: String, callback: js.Function0[Unit]): js.Any = js.native
  def once(event: String, callback: js.Function0[Unit]): js.Any = js.native
  def on[T](event: String, callback: js.Function1[T, Unit]): js.Any = js.native
  def seekTo(progress: Double): js.Any = js.native
  def seekAndCenter(progress: Double): js.Any = js.native
  def drawer: js.Dynamic = js.native
  def zoom(pxPerSec: Double): js.Any = js.native
}


@js.native
object WaveSurfer extends js.Object {
  def create(options: WaveSurferOpts): WaveSurfer = js.native
}

@JSName("WaveSurfer.Spectrogram")
@js.native
object WaveSurferSpectrogramPlugin extends js.Object {
  def init(opts: js.Dynamic): js.Any = js.native
}

@JSName("WaveSurfer.Timeline")
@js.native
object WaveSurferTimelinePlugin extends js.Object {
  def init(opts: js.Dynamic): js.Any = js.native
}
