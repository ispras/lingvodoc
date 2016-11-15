package ru.ispras.lingvodoc.frontend.app.controllers.desktop

import com.greencatsoft.angularjs.core._
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.model.{Location => _, _}
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, UserService}
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}

@js.native
trait NavigationScope extends Scope {
  var locale: Int = js.native
  var locales: js.Array[Locale] = js.native
  var selectedLocale: Locale = js.native
  var syncEnabled: Boolean = js.native
}

@JSExport
@injectable("NavigationController")
class NavigationController(scope: NavigationScope, rootScope: RootScope, location: Location, backend: BackendService, userService: UserService, val timeout: Timeout, val exceptionHandler: ExceptionHandler) extends AbstractController[NavigationScope](scope) with AngularExecutionContextProvider {


  scope.syncEnabled = true
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
          rootScope.$emit("user.changeLocale")
        }
      case None =>
        Utils.setLocale(locale)
        rootScope.$emit("user.changeLocale")
    }
    scope.locale = locale

    scope.selectedLocale = scope.locales.find { locale =>
      locale.id == scope.locale
    }.getOrElse(scope.locales.head)
  }

  @JSExport
  def sync() = {
    scope.syncEnabled = false
    backend.syncAll() map { _ =>
      scope.syncEnabled = true
    } recover {
      case e: Throwable =>
        scope.syncEnabled = true
    }
  }


  // user logged in
  rootScope.$on("user.login", () => {
    backend.getCurrentUser onComplete {
      case Success(user) =>
        userService.setUser(user)
      case Failure(e) =>
        console.log("error: " + e.getMessage)
    }
  })

  // user logged out
  rootScope.$on("user.logout", () => {
    userService.removeUser()
  })

  // redirect all unauthenticated users to login page
  rootScope.$on("$locationChangeStart", (event: Event) => {
    backend.getCurrentUser onComplete {
      case Success(user) =>
        userService.setUser(user)
      case Failure(e) =>
        event.preventDefault()
        userService.removeUser()
        location.path("/login")
    }
  })

  // initial
  backend.getLocales onComplete {
    case Success(locales) =>
      scope.locales = locales.toJSArray
      scope.selectedLocale = locales.find { locale =>
        locale.id == scope.locale
      }.getOrElse(locales.head)
    case Failure(e) => console.log(e.getMessage)
  }
}

