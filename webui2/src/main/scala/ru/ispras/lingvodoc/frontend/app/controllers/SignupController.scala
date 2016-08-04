package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{Location, Scope}
import com.greencatsoft.angularjs.{AbstractController, injectable}
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import ru.ispras.lingvodoc.frontend.app.utils.LingvodocExecutionContext.Implicits.executionContext

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.api.exceptions.BackendException


@js.native
trait SignupScope extends Scope {
  var login: String = js.native
  var fullName: String = js.native
  var email: String = js.native
  var password: String = js.native
  var month: String = js.native
  var day: String = js.native
  var year: String = js.native
  var error: Option[String] = js.native
}

@injectable("SignupController")
class SignupController(scope: SignupScope, location: Location, backend: BackendService) extends AbstractController[SignupScope](scope) {

  scope.login = ""
  scope.fullName = ""
  scope.email = ""
  scope.password = ""
  scope.month = "0"
  scope.day = "0"
  scope.year = "0"
  scope.error = None


  @JSExport
  def error(): Boolean = {
    scope.error.nonEmpty
  }

  @JSExport
  def errorMessage(): String = {
    scope.error.getOrElse("Unknown Error")
  }


  @JSExport
  def signup() = {
    backend.signup(scope.login, scope.fullName, scope.password, scope.email, scope.day, scope.month, scope.year) onComplete {
      case Success(()) => location.path("login")
      case Failure(e) => scope.error = Some("some error")
    }
  }
}

