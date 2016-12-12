package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.Scope
import com.greencatsoft.angularjs.extensions.ModalInstance
import com.greencatsoft.angularjs.{AbstractController, injectable}

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

  params("exception") match {
    case e: Throwable =>
      scope.message = e.getMessage

      e.getCause match {
        case cause: Throwable =>
          scope.causeMessage = e.getCause.getMessage
          scope.stackTrace = e.getCause.getStackTrace.mkString("\n")
        case _ =>
          scope.causeMessage = e.getMessage
          scope.stackTrace = e.getStackTrace.mkString("\n")
      }

    case _ =>
      scope.message = ""
      scope.causeMessage = ""
      scope.stackTrace = ""

  }

  @JSExport
  def ok() = {
    instance.dismiss(())
  }

  @JSExport
  def report() = {
    instance.dismiss(())
  }
}

