package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.Scope
import ru.ispras.lingvodoc.frontend.app.services.ModalInstance
import com.greencatsoft.angularjs.{AbstractController, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.{UserService, BackendService}
import ru.ispras.lingvodoc.frontend.app.utils

import scala.scalajs.concurrent.JSExecutionContext.Implicits.runNow
import scala.scalajs.js
import scala.scalajs.js.Array
import scala.scalajs.js.annotation.{JSExportAll, JSExport}
import scala.scalajs.js.JSConverters._
import scala.util.{Failure, Success}
import scala.scalajs.js.Date


@js.native
trait NavigationScope extends Scope {
  var user: User = js.native
  var isLogged: Boolean = js.native
}

@JSExport
@injectable("NavigationController")
class NavigationController(scope: NavigationScope, backend: BackendService) extends AbstractController[NavigationScope](scope) {

  scope.user = null
  scope.isLogged = false

  @JSExport
  def isAuthenticated() = {
    scope.isLogged
  }

  @JSExport
  def getAuthenticatedUser() = {
    scope.user
  }

  backend.getCurrentUser onComplete {
    case Success(user) =>
      scope.user = user
      scope.isLogged = true

    case Failure(e) =>
      scope.user = null
      scope.isLogged = false
  }
}
