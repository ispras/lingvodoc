package ru.ispras.lingvodoc.frontend.app.controllers.modal

import com.greencatsoft.angularjs.{AngularExecutionContextProvider, injectable}
import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.{ModalInstance, ModalService}
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseModalController
import ru.ispras.lingvodoc.frontend.app.services.BackendService

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport



trait MessageScope extends Scope {
  var title: String = js.native
  var message: String = js.native
}



@injectable("MessageController")
class MessageController(scope: MessageScope,
                        modal: ModalService,
                        instance: ModalInstance[Unit],
                        backend: BackendService,
                        timeout: Timeout,
                        val exceptionHandler: ExceptionHandler,
                        params: js.Dictionary[js.Function0[js.Any]])
  extends BaseModalController(scope, modal, instance, timeout, params)
    with AngularExecutionContextProvider {

  scope.title = ""
  scope.message = ""
  params.get("title") foreach { title =>
    scope.title = title.asInstanceOf[String]
  }

  params.get("message") foreach { message =>
    scope.message = message.asInstanceOf[String]
  }

  @JSExport
  def close(): Unit = {
    instance.dismiss(())
  }

  override protected def onStartRequest(): Unit = {}

  override protected def onCompleteRequest(): Unit = {}
}
