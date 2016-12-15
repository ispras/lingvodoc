package ru.ispras.lingvodoc.frontend.app.controllers.base

import com.greencatsoft.angularjs.AngularExecutionContextProvider
import com.greencatsoft.angularjs.core.{Event, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.{ModalInstance, ModalService}

import scala.scalajs.js


abstract class BaseModalController[ScopeClass <: Scope, ResultType](scope: ScopeClass,
                                                                    modalService: ModalService,
                                                                    modalInstance: ModalInstance[ResultType],
                                                                    timeout: Timeout,
                                                                    params: js.Dictionary[js.Function0[js.Any]])
  extends BaseController[ScopeClass](scope, modalService, timeout)
    with AngularExecutionContextProvider
{
  protected def onModalOpen(): Unit = {}

  protected def onModalClose(): Unit = {}

  // bind on open event handler
  modalInstance.rendered map { f =>
    onModalOpen()
  }

  // bind on close event handler
  scope.$on("modal.closing", (event: Event, reason: js.Any, closed: Boolean) => {
    onModalClose()
  })
}
