package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.Scope
import ru.ispras.lingvodoc.frontend.app.services.ModalInstance
import com.greencatsoft.angularjs.{AbstractController, injectable}

import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.{UserService, BackendService}
import ru.ispras.lingvodoc.frontend.app.utils

import ru.ispras.lingvodoc.frontend.app.utils.LingvodocExecutionContext.Implicits.executionContext
import scala.scalajs.js
import scala.scalajs.js.Array
import scala.scalajs.js.annotation.{JSExportAll, JSExport}
import scala.scalajs.js.JSConverters._
import scala.util.{Failure, Success}
import scala.scalajs.js.Date
import org.scalajs.dom.console

@js.native
trait NavigationScope extends Scope {
  var user: Option[User] = js.native
}

@JSExport
@injectable("NavigationController")
class NavigationController(scope: NavigationScope, backend: BackendService) extends AbstractController[NavigationScope](scope) {

  scope.user = None



  @JSExport
  def isAuthenticated() = {
    scope.user.nonEmpty
  }

  @JSExport
  def getAuthenticatedUser() = {
    scope.user.get
  }

  backend.getCurrentUser onComplete {
    case Success(user) =>
      scope.user = Some(user)

    case Failure(e) =>
      scope.user = None
  }
}
