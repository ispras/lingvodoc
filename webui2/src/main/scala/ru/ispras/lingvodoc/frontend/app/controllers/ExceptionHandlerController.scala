package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.Scope
import com.greencatsoft.angularjs.{AbstractController, injectable}
import ru.ispras.lingvodoc.frontend.app.services.ModalInstance
import org.scalajs.dom.console


import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport

@js.native
trait ExceptionHandlerScope extends Scope {
  var message: String = js.native
  var causeMessage: String = js.native
  var stackTrace: String = js.native
}

@injectable("ExceptionHandlerController")
class ExceptionHandlerController(scope: ExceptionHandlerScope,
                                 instance: ModalInstance[Unit],
                                 params: js.Dictionary[js.Function0[js.Any]]) extends AbstractController[ExceptionHandlerScope](scope) {

  private[this] val exception: Throwable = params("exception").asInstanceOf[Throwable]

  scope.message = exception.getMessage
  scope.causeMessage = exception.getCause.getMessage
  scope.stackTrace = exception.getCause.getStackTrace.mkString("\n")

  @JSExport
  def ok() = {
    instance.dismiss(())
  }

  @JSExport
  def report() = {
    instance.dismiss(())
  }
}

