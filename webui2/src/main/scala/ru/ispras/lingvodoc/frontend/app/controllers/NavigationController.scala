package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{RootScope, Scope}
import ru.ispras.lingvodoc.frontend.app.services.ModalInstance
import com.greencatsoft.angularjs.{AbstractController, injectable}
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, UserService}
import ru.ispras.lingvodoc.frontend.app.utils
import ru.ispras.lingvodoc.frontend.app.utils.LingvodocExecutionContext.Implicits.executionContext

import scala.scalajs.js
import scala.scalajs.js.Array
import scala.scalajs.js.annotation.{JSExport, JSExportAll}
import scala.scalajs.js.JSConverters._
import scala.util.{Failure, Success}
import scala.scalajs.js.Date
import org.scalajs.dom.console

@js.native
trait NavigationScope extends Scope {

}

@JSExport
@injectable("NavigationController")
class NavigationController(scope: NavigationScope, rootScope: RootScope, backend: BackendService, userService: UserService) extends AbstractController[NavigationScope](scope) {

  @JSExport
  def isAuthenticated() = {
    userService.hasUser()
  }

  @JSExport
  def getAuthenticatedUser() = {
    userService.getUser()
  }


  rootScope.$on("user.login", () => {

    backend.getCurrentUser onComplete {
      case Success(user) =>
        userService.setUser(user)
      case Failure(e) =>
    }
  })

  rootScope.$on("user.logout", () => {
    userService.removeUser()
  })

  // initial
  backend.getCurrentUser onComplete {
    case Success(user) =>
      userService.setUser(user)

    case Failure(e) =>
      userService.removeUser()
  }
}
