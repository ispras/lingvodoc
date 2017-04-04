package ru.ispras.lingvodoc.frontend.app.controllers.modal

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.{ModalInstance, ModalService}
import com.greencatsoft.angularjs.injectable
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseModalController
import ru.ispras.lingvodoc.frontend.app.controllers.common.DictionaryTable
import ru.ispras.lingvodoc.frontend.app.model.Entity
import ru.ispras.lingvodoc.frontend.app.services.BackendService

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport



@js.native
trait DownloadEmbeddedBlobScope extends Scope {
  var title: String = js.native
  var fileName: String = js.native
  var fileType: String = js.native
  var blob: String = js.native
}

@injectable("DownloadEmbeddedBlobController")
class DownloadEmbeddedBlobController(scope: DownloadEmbeddedBlobScope,
                                     val modal: ModalService,
                                     instance: ModalInstance[Seq[Entity]],
                                     backend: BackendService,
                                     timeout: Timeout,
                                     val exceptionHandler: ExceptionHandler,
                                     params: js.Dictionary[js.Function0[js.Any]])
  extends BaseModalController(scope, modal, instance, timeout, params) {


  params.get("title") foreach { t =>
    scope.title = t.asInstanceOf[String]
  }

  params.get("blob") foreach { b =>
    scope.blob = b.asInstanceOf[String]
  }

  params.get("fileName") foreach { f =>
    scope.fileName = f.asInstanceOf[String]
  }

  params.get("fileType") foreach { f =>
    scope.fileType = f.asInstanceOf[String]
  }

  @JSExport
  def close(): Unit = {
    instance.dismiss(())
  }

  override protected def onStartRequest(): Unit = {}
  override protected def onCompleteRequest(): Unit = {}
}
