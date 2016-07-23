package ru.ispras.lingvodoc.frontend.app.controllers

import org.scalajs.dom
import ru.ispras.lingvodoc.frontend.app.services.{ModalInstance, ModalService}
import com.greencatsoft.angularjs.core.Scope
import com.greencatsoft.angularjs.{Angular, AbstractController, injectable}
import ru.ispras.lingvodoc.frontend.app.model.{Perspective, Language, Dictionary}
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import ru.ispras.lingvodoc.frontend.extras.facades.{WaveSurfer, WaveSurferOpts}
import ru.ispras.lingvodoc.frontend.extras.elan.{ELANPArserException, ELANDocumentJquery}
import org.scalajs.dom.console
import org.scalajs.jquery.jQuery
import ru.ispras.lingvodoc.frontend.app.utils.LingvodocExecutionContext.Implicits.executionContext

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
  var soundMarkup: Option[String] = None
  val soundAddress = params.get("soundAddress").map(_.toString)
  val dictionaryClientId = params.get("dictionaryClientId").map(_.toString.toInt)
  val dictionaryObjectId = params.get("dictionaryObjectId").map(_.toString.toInt)

  (dictionaryClientId, dictionaryObjectId).zipped.foreach((dictionaryClientId, dictionaryObjectId) => {
    backend.getSoundMarkup(dictionaryClientId, dictionaryObjectId) onSuccess {
    case markup => parseMarkup(markup)
    }
  })


  def parseMarkup(markup: String): Unit = {
    val test_markup =
      """<?xml version="1.0" encoding="UTF-8"?>
<ANNOTATION_DOCUMENT AUTHOR="TextGridTools" DATE="2016-07-11T14:44:15+00:00" FORMAT="2.7" VERSION="2.7" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.mpi.nl/tools/elan/EAFv2.7.xsd">
<HEADER TIME_UNITS="milliseconds">
  <MEDIA_DESCRIPTOR MEDIA_URL="ya.ru" MIME_TYPE="text" RELATIVE_MEDIA_URL="rmuuuuu" TIME_ORIGIN="1948"/>
  <MEDIA_DESCRIPTOR MEDIA_URL="yaya.ru" MIME_TYPE="text"/>
  <LINKED_FILE_DESCRIPTOR LINK_URL="foo.ru" MIME_TYPE="text" TIME_ORIGIN="20148" />
  <PROPERTY NAME="nextTimeSlotId">6</PROPERTY>
  <PROPERTY NAME="nextAnnotationId">5</PROPERTY>
</HEADER>
<TIME_ORDER>
<TIME_SLOT TIME_SLOT_ID="ts1" TIME_VALUE="0"/>
<TIME_SLOT TIME_SLOT_ID="ts2" TIME_VALUE="64"/>
<TIME_SLOT TIME_SLOT_ID="ts3" TIME_VALUE="135"/>
<TIME_SLOT TIME_SLOT_ID="ts4" TIME_VALUE="303"/>
<TIME_SLOT TIME_SLOT_ID="ts5" TIME_VALUE="389"/>
<TIME_SLOT TIME_SLOT_ID="ts6" TIME_VALUE="472"/>
<TIME_SLOT TIME_SLOT_ID="ts7" TIME_VALUE="574"/>
</TIME_ORDER>
<LINGUISTIC_TYPE GRAPHIC_REFERENCES="false" LINGUISTIC_TYPE_ID="default-lt" TIME_ALIGNABLE="true"/>
</ANNOTATION_DOCUMENT>
      """
      val elan = ELANDocumentJquery(test_markup)
      console.log(elan.toString)
//    val lt = xml.find("LINGUISTIC_TYPE")
////    val test = xml.find("test")
//    console.log(markup)
//    console.log("AAAA")
//    console.log(lt)
//    console.log(lt.attr("LINGUISTIC_TYPE_ID"))
//
//    val props = xml.find("PROPERTY")
//    props.each((el: dom.Element) => {
//      val jqEl = jQuery(el)
//      console.log(jqEl.text())
//    })

  }

  // hack to initialize controller after loading the view
  // see http://stackoverflow.com/questions/21715256/angularjs-event-to-call-after-content-is-loaded
  @JSExport
  def createWaveSurfer(): Unit = {
    if (waveSurfer.isEmpty) {
      val wso = WaveSurferOpts("#waveform", "violet", "purple")
      waveSurfer = Some(WaveSurfer.create(wso))
      (waveSurfer, soundAddress).zipped.foreach((ws, sa) => {
        ws.load(sa)
      })
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
