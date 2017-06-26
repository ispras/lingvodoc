package ru.ispras.lingvodoc.frontend.app.controllers.webui.modal

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.{ModalInstance, ModalService}
import com.greencatsoft.angularjs.{AngularExecutionContextProvider, injectable}
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseModalController
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.BackendService

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport



@js.native
trait CreateOrganizationModalScope extends Scope {
  var organizationName: String = js.native
  var organizationAbout: String = js.native
}

@injectable("CreateOrganizationModalController")
class CreateOrganizationModalController(scope: CreateOrganizationModalScope,
                                 val modal: ModalService,
                                 instance: ModalInstance[Grant],
                                 backend: BackendService,
                                 timeout: Timeout,
                                 val exceptionHandler: ExceptionHandler,
                                 params: js.Dictionary[js.Function0[js.Any]])
  extends BaseModalController(scope, modal, instance, timeout, params)
    with AngularExecutionContextProvider {

  scope.organizationName = ""
  scope.organizationAbout = ""


  @JSExport
  def save(): Unit = {
    backend.createOrganization(scope.organizationName, scope.organizationAbout) map { _ =>
      instance.dismiss(())
    }
  }

  @JSExport
  def cancel(): Unit = {
    instance.dismiss(())
  }

  override protected def onStartRequest(): Unit = {}

  override protected def onCompleteRequest(): Unit = {}
}
