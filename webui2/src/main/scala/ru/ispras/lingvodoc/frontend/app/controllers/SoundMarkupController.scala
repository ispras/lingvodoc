package ru.ispras.lingvodoc.frontend.app.controllers

import ru.ispras.lingvodoc.frontend.app.services.{ModalInstance, ModalService}
import com.greencatsoft.angularjs.core.Scope
import com.greencatsoft.angularjs.{Angular, AbstractController, injectable}
import ru.ispras.lingvodoc.frontend.app.model.{Perspective, Language, Dictionary}
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import ru.ispras.lingvodoc.frontend.extras.facades.{WaveSurfer, WaveSurferOpts}
import org.scalajs.dom.console
import scala.scalajs.concurrent.JSExecutionContext.Implicits.runNow

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport

@js.native
trait SoundMarkupScope extends Scope {
  var blabla: String = js.native
  var blabla2: String = js.native
}

@injectable("SoundMarkupController")
class SoundMarkupController(scope: SoundMarkupScope,
                            instance: ModalInstance[Unit],
                            modal: ModalService,
                            backend: BackendService,
                            params: js.Dictionary[js.Function0[js.Any]])
  extends AbstractController[SoundMarkupScope](scope) {
  var waveSurfer: Option[WaveSurfer] = None
  val soundAddress = params.get("soundAddress").map(_.toString).get
  val dictionaryClientId = params.get("dictionaryClientId").map(_.toString.toInt).get
  val dictionaryObjectId = params.get("dictionaryObjectId").map(_.toString.toInt).get
  console.log(dictionaryClientId)
  console.log(dictionaryObjectId)
  backend.getSoundMarkup(dictionaryClientId, dictionaryObjectId) onSuccess {
    case markup => console.log(markup)
  }

  // hack to initialize controller after loading the view
  // see http://stackoverflow.com/questions/21715256/angularjs-event-to-call-after-content-is-loaded
  @JSExport
  def createWaveSurfer(): Unit = {
    if (waveSurfer.isEmpty) {
      console.log("FFFFFFFFFFFFFFFFFf")
      val wso = WaveSurferOpts("#waveform", "violet", "purple")
      waveSurfer = Some(WaveSurfer.create(wso))
      waveSurfer.foreach(_.load(soundAddress))
    }
  }

  @JSExport
  def save(): Unit = {
    val wso = WaveSurferOpts("#waveform", "violet", "purple")
    val ws = WaveSurfer.create(wso)
    ws.load("audio.wav")
//    instance.dismiss(())
  }

  @JSExport
  def cancel(): Unit = {
    instance.close(())
  }
}

object SoundMarkupController {
  def displayWaveSurfer(): Unit = {

  }
}
