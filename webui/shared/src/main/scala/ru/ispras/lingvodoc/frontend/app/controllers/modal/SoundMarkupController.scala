package ru.ispras.lingvodoc.frontend.app.controllers.modal

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.{ModalInstance, ModalOptions, ModalService}
import com.greencatsoft.angularjs.injectable
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseModalController
import ru.ispras.lingvodoc.frontend.app.model.CompositeId
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import ru.ispras.lingvodoc.frontend.extras.facades._

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport


@js.native
trait SoundMarkupScope extends Scope {

}

@injectable("SoundMarkupController")
class SoundMarkupController(scope: SoundMarkupScope,
                            instance: ModalInstance[Unit],
                            val modal: ModalService,
                            backend: BackendService,
                            timeout: Timeout,
                            val exceptionHandler: ExceptionHandler,
                            params: js.Dictionary[js.Function0[js.Any]])
  extends BaseModalController(scope, modal, instance, timeout, params) {


  private[this] var waveSurfer: Option[WaveSurfer] = None
  private[this] var spectrogram: Option[js.Dynamic] = None
  private[this] var timeline: Option[js.Dynamic] = None
  private[this] var elan: Option[js.Dynamic] = None

  private[this] var scale: Double = 100

  private[this] val soundAddress = params.get("soundAddress").map(_.toString)
  private[this] val markupAddress = params.get("markupAddress").map(_.toString)
  private[this] val markupData = params.get("markupData").map(_.asInstanceOf[String])

  private[this] val dictionaryClientId = params("dictionaryClientId").asInstanceOf[Int]
  private[this] val dictionaryObjectId = params("dictionaryObjectId").asInstanceOf[Int]


  @JSExport
  def hasSound(): Boolean = {
    soundAddress.nonEmpty
  }

  @JSExport
  def playPause(): Unit = {
    waveSurfer.foreach(_.playPause())
  }

  @JSExport
  def zoomIn(): Unit = {
    if (scale < 800) {
      scale = scale + 20
      setZoom(scale)
    }
  }

  @JSExport
  def zoomOut(): Unit = {
    if (scale > 50) {
      scale = scale - 20
      setZoom(scale)
    }
  }

  private[this] def setZoom(v: Double) = {
    soundAddress match {
      case Some(_) =>
        waveSurfer.foreach(_.zoom(v))
        elan.foreach(_.drawerSetup())
        elan.foreach(_.render())
      case None =>
        elan.foreach(_.setPxPerSec(v))
    }
  }

  @JSExport
  def save(): Unit = {
    instance.close(())
  }

  @JSExport
  def cancel(): Unit = {
    instance.close(())
  }

  @JSExport
  def convertToDictionary(): Unit = {

    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/convertEaf.html"
    options.windowClass = "sm-modal-window"
    options.controller = "ConvertEafController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          soundUrl = soundAddress.asInstanceOf[js.Object],
          markupUrl = markupAddress.asInstanceOf[js.Object],
          corpusId = CompositeId(dictionaryClientId, dictionaryObjectId).asInstanceOf[js.Object]
        )
      }
    ).asInstanceOf[js.Dictionary[Any]]
    modal.open[Unit](options)
  }

  override protected def onStartRequest(): Unit = {}

  override protected def onCompleteRequest(): Unit = {}

  override protected def onModalOpen(): Unit = {

    val wso = WaveSurferOpts(container = "#waveform",
      waveColor = "violet",
      progressColor = "purple",
      cursorWidth = 1,
      cursorColor = "red",
      fillParent = true,
      height = 64,
      barWidth = 0)

    waveSurfer = Some(WaveSurfer.create(wso))

    waveSurfer.foreach { w =>
      soundAddress.foreach { url =>
        w.load(url)
      }
    }

    spectrogram = Some(js.Object.create(WaveSurferSpectrogramPlugin).asInstanceOf[js.Dynamic])
    timeline = Some(js.Object.create(WaveSurferTimelinePlugin).asInstanceOf[js.Dynamic])
    elan = Some(js.Object.create(WaveSurferELAN).asInstanceOf[js.Dynamic])

    elan.foreach(_.on("select", (start: Double, end: Double) => {
      waveSurfer.foreach(_.play(start, end))
    }))

    waveSurfer.foreach(_.once("ready", () => {
      spectrogram.foreach(_.init(js.Dynamic.literal(wavesurfer = waveSurfer.get, container = "#wavespectrogram", fftSamples = 256)))
      timeline.foreach(_.init(js.Dynamic.literal(wavesurfer = waveSurfer.get, container = "#wavetimeline", primaryColor = "red")))
      elan.foreach(_.init(js.Dynamic.literal(wavesurfer = waveSurfer.get, container = "#elan", xml = markupData.get)))
    }))

    // If we have only markup, wavesurfer's "ready" event is never fired
    if (soundAddress.isEmpty) {
      elan.foreach(_.init(js.Dynamic.literal(container = "#elan", xml = markupData.get)))
    }

    waveSurfer.foreach(_.zoom(scale))

    super.onModalOpen()
  }

  override protected def onModalClose(): Unit = {

    spectrogram.foreach(_.destroy())
    timeline.foreach(_.destroy())
    waveSurfer.foreach(_.destroy())
    elan.foreach(_.destroy())

    super.onModalClose()
  }
}
