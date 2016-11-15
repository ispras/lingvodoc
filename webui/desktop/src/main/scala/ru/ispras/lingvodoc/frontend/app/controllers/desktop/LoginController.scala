package ru.ispras.lingvodoc.frontend.app.controllers.desktop

import com.greencatsoft.angularjs.core._
import com.greencatsoft.angularjs.extensions.ModalService
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import ru.ispras.lingvodoc.frontend.app.controllers.traits.ErrorModalHandler
import ru.ispras.lingvodoc.frontend.app.services.BackendService

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}

@js.native
trait LoginScope extends Scope {
  var username: String = js.native
  var password: String = js.native
  var remember: Boolean = js.native
  var lastError: Boolean = js.native
}


@injectable("LoginController")
class LoginController(scope: LoginScope,
                      val rootScope: RootScope,
                      val location: Location,
                      val backend: BackendService,
                      val modalService: ModalService,
                      val timeout: Timeout,
                      val exceptionHandler: ExceptionHandler)
  extends AbstractController(scope)
    with AngularExecutionContextProvider
    with ErrorModalHandler
{
  scope.username = ""
  scope.password = ""
  scope.remember = true
  scope.lastError = false


  @JSExport
  def login() = {
    if (scope.username.nonEmpty && scope.password.nonEmpty) {

      backend.desktop_login(scope.username, scope.password) onComplete {

        case Success(clientId) =>
          scope.password = ""
          rootScope.$emit("user.login")
          location.path("/")

        case Failure(e) =>
          // Login failed
          scope.password = ""
          scope.lastError = true
          showError(e)
      }
    }
  }
}
