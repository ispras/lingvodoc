package ru.ispras.lingvodoc.frontend.extras.facades

import scala.scalajs.js

@js.native
trait WaveSurferOpts extends js.Object {
  val container: String = js.native
  val waveColor: String = js.native
  val progressColor: String = js.native
}

object WaveSurferOpts {
  def apply(container: String, waveColor: String, progressColor: String): WaveSurferOpts = {
    js.Dynamic.literal(
      container = container,
      waveColor = waveColor,
      progressColor = progressColor
    ).asInstanceOf[WaveSurferOpts]
  }
}

@js.native
trait WaveSurfer extends js.Object {
  def load(url: String): js.Any = js.native
  def playPause(): js.Any = js.native
  def play(start: Int = 0, end: Int = Int.MaxValue): js.Any = js.native
}

@js.native
object WaveSurfer extends js.Object {
  def create(options: WaveSurferOpts): WaveSurfer = js.native
}
