package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{Location, Scope, Timeout}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import ru.ispras.lingvodoc.frontend.app.services.BackendService

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}



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
class SignupController(scope: SignupScope, location: Location, backend: BackendService, val timeout: Timeout) extends AbstractController[SignupScope](scope) with AngularExecutionContextProvider {

  scope.login = ""
  scope.fullName = ""
  scope.email = ""
  scope.password = ""
  scope.month = "1"
  scope.day = "1"
  scope.year = "1980"
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
    backend.signup(scope.login, scope.fullName, scope.password, scope.email, scope.day.toInt, scope.month.toInt, scope.year.toInt) onComplete {
      case Success(()) => location.path("login")
      case Failure(e) => scope.error = Some("some error")
    }
  }
}

