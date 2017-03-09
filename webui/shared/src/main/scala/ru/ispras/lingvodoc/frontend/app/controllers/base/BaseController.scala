package ru.ispras.lingvodoc.frontend.app.controllers.base

import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider}
import com.greencatsoft.angularjs.core.{Event, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.{ModalOptions, ModalService}
import org.scalajs.dom.{Event, document}

import scala.concurrent.Future
import scala.scalajs.js

abstract class BaseController[ScopeClass <: Scope](scope: ScopeClass, modalService: ModalService, val timeout: Timeout)
  extends AbstractController[ScopeClass](scope)
    with AngularExecutionContextProvider {


  protected def onStartRequest()

  protected def onCompleteRequest()

  protected def onOpen(): Unit = {}

  protected def onClose(): Unit = {}

  protected def error(exception: Throwable): Unit = {
    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/exceptionHandler.html"
    options.controller = "ExceptionHandlerController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(exception = exception.asInstanceOf[js.Any])
      }
    ).asInstanceOf[js.Dictionary[Any]]
    modalService.open[Unit](options)
  }

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
