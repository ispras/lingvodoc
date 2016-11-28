package ru.ispras.lingvodoc.frontend.app.controllers.desktop

import com.greencatsoft.angularjs.core._
import com.greencatsoft.angularjs.extensions.ModalService
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import ru.ispras.lingvodoc.frontend.app.controllers.traits.{ErrorModalHandler, LoadingPlaceholder}
import ru.ispras.lingvodoc.frontend.app.services.BackendService

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport

@js.native
trait LoginScope extends Scope {
  var username: String = js.native
  var password: String = js.native
  var remember: Boolean = js.native
  var lastError: Boolean = js.native
  var pageLoaded: Boolean = js.native
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
    with LoadingPlaceholder {

  scope.username = ""
  scope.password = ""
  scope.remember = true
  scope.lastError = false
  scope.pageLoaded = true


  @JSExport
  def login() = {
    if (scope.username.nonEmpty && scope.password.nonEmpty) {

      doAjax(() => {
        backend.desktop_login(scope.username, scope.password) map { clientId =>
            scope.password = ""
            rootScope.$emit("user.login")
            location.path("/")
        } recover {
          case e: Throwable =>
            // Login failed
            scope.password = ""
            scope.lastError = true
            showError(e)
        }
      })
    }
  }

  override protected def onLoaded[T](result: T): Unit = {}

  override protected def onError(reason: Throwable): Unit = {}

  override protected def preRequestHook(): Unit = {
    scope.pageLoaded = false
  }

  override protected def postRequestHook(): Unit = {
    scope.pageLoaded = true
  }
}
