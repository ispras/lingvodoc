package ru.ispras.lingvodoc.frontend.app.controllers.base

import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider}
import com.greencatsoft.angularjs.core.{Event, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.{ModalOptions, ModalService}
import org.scalajs.dom.{Event, document}

import scala.concurrent.Future
import scala.scalajs.js

import ru.ispras.lingvodoc.frontend.app.controllers.traits.{ErrorModalHandler}

abstract class BaseController[ScopeClass <: Scope](scope: ScopeClass, modal: ModalService, val timeout: Timeout)
  extends AbstractController[ScopeClass](scope)
    with AngularExecutionContextProvider
    with ErrorModalHandler {


  protected def onStartRequest()

  protected def onCompleteRequest()

  protected def onOpen(): Unit = {}

  protected def onClose(): Unit = {}

  protected def error(exception: Throwable): Unit = { showError(exception) }

  protected def load(loadFunction: () => Future[_]): Future[Any] = {
    onStartRequest()
    loadFunction() map { result =>
      onCompleteRequest()
    } recover {
      case e: Throwable =>
        onCompleteRequest()
    }
  }


  scope.$on("route.changeSuccess", () => {
    onOpen()
  })

  scope.$on("route.changeStart", () => {
    onClose()
  })


}
