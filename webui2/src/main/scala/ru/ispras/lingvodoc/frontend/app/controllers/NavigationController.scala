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
import ru.ispras.lingvodoc.frontend.app.utils.Utils

@js.native
trait NavigationScope extends Scope {
  var locale: Int = js.native
}

@JSExport
@injectable("NavigationController")
class NavigationController(scope: NavigationScope, rootScope: RootScope, backend: BackendService, userService: UserService) extends AbstractController[NavigationScope](scope) {

  // get locale. fallback to english if no locale received from backend
  scope.locale = Utils.getLocale() match {
    case Some(serverLocale) => serverLocale
    case None =>
      Utils.setLocale(2)
      2 // english locale
  }

  @JSExport
  def isAuthenticated() = {
    userService.hasUser()
  }

  @JSExport
  def getAuthenticatedUser() = {
    userService.getUser()
  }

  @JSExport
  def getLocale(): Int = {
    scope.locale
  }

  @JSExport
  def setLocale(locale: Int) = {
    Utils.getLocale() match {
      case Some(serverLocale) =>
        if (serverLocale != locale) {
          Utils.setLocale(locale)
        }
      case None => Utils.setLocale(locale)
    }
    scope.locale = locale
  }

  // user logged in
  rootScope.$on("user.login", () => {
    backend.getCurrentUser onComplete {
      case Success(user) =>
        userService.setUser(user)
      case Failure(e) =>
    }
  })

  // user logged out
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
