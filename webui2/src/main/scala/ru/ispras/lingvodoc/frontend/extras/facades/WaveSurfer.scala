package ru.ispras.lingvodoc.frontend.extras.facades

import scala.scalajs.js

@js.native
trait WaveSurferOpts extends js.Object {
  val container: String = js.native
  val waveColor: String = js.native
  val progressColor: String = js.native
  val cursorWidth: Int = js.native
  val cursorColor: String = js.native
  val scrollParent: Boolean = js.native
  val minPxPerSec: Int = js.native
  val fillParent: Boolean = js.native
}

object WaveSurferOpts {
  def apply(container: String, waveColor: String = "#999", progressColor: String = " #555",
            cursorWidth: Int = 1, cursorColor: String = "#333", scrollParent: Boolean = false,
            minPxPerSec: Int = 50, fillParent: Boolean = true): WaveSurferOpts = {
    js.Dynamic.literal(
      container = container,
      waveColor = waveColor,
      progressColor = progressColor,
      cursorWidth = cursorWidth,
      cursorColor = cursorColor,
      scrollParent = scrollParent,
      minPxPerSec = minPxPerSec,
      fillParent = fillParent
    ).asInstanceOf[WaveSurferOpts]
  }
}

@js.native
trait WaveSurfer extends js.Object {
  def getCurrentTime(): Double = js.native
  def getDuration(): Double = js.native
  def load(url: String): js.Any = js.native
  def playPause(): js.Any = js.native
  def play(start: Int = 0, end: Int = Int.MaxValue): js.Any = js.native
  def on(event: String, callback: js.Function0[Unit]): js.Any = js.native
  def on[T](event: String, callback: js.Function1[T, Unit]): js.Any = js.native
  def seekTo(progress: Double): js.Any = js.native
  def seekAndCenter(progress: Double): js.Any = js.native
  def drawer: js.Dynamic = js.native
}


@js.native
object WaveSurfer extends js.Object {
  def create(options: WaveSurferOpts): WaveSurfer = js.native
}
