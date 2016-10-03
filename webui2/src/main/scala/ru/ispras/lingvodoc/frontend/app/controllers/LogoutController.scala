package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{Location, RootScope, Scope, Timeout}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import ru.ispras.lingvodoc.frontend.app.services.BackendService

import scala.scalajs.js
import scala.util.{Failure, Success}


@js.native
trait LogoutScope extends Scope {

}

@injectable("LogoutController")
class LogoutController(scope: LogoutScope, location: Location, rootScope: RootScope, backend: BackendService, val timeout: Timeout) extends AbstractController[LogoutScope](scope) with AngularExecutionContextProvider {



  backend.logout() onComplete {
    case Success(_) =>

      rootScope.$emit("user.logout")
      location.path("/")

    case Failure(e) =>
      // failed to logout?
  }
}
