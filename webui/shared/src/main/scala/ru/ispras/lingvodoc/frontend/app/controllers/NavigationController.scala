package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core._
import com.greencatsoft.angularjs.extensions.{ModalOptions, ModalService}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import ru.ispras.lingvodoc.frontend.app.model._
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
  var tasks: js.Array[Task] = js.native
}

@JSExport
@injectable("NavigationController")
class NavigationController(scope: NavigationScope,
                           rootScope: RootScope,
                           backend: BackendService,
                           userService: UserService,
                           modal: ModalService,
                           val timeout: Timeout,
                           val exceptionHandler: ExceptionHandler)
  extends AbstractController[NavigationScope](scope)
    with AngularExecutionContextProvider {


  scope.tasks = js.Array[Task]()

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
    } match {
      case Some(x) => x
      case None => scope.locales.head
    }
  }

  @JSExport
  def removeTask(task: Task): Unit = {
    backend.removeTask(task) map { _ =>
      scope.tasks = scope.tasks.filterNot(_.id == task.id)
    }
  }


  @JSExport
  def editProfile(): Unit = {
    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/userProfile.html"
    options.windowClass = "sm-modal-window"
    options.controller = "UserProfileController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal()
      }
    ).asInstanceOf[js.Dictionary[Any]]
    modal.open[Unit](options)
  }



  private[this] def loadTasks(): Unit = {
    backend.tasks map { tasks =>
      scope.tasks = tasks.sortBy(_.taskFamily).toJSArray
    }
    timeout(loadTasks _, 10000)
  }

  backend.getLocales map { locales =>
      scope.locales = locales.toJSArray
      scope.selectedLocale = locales.find(_.id == scope.locale) match {
        case Some(x) => x
        case None => locales.head
      }
  }

  loadTasks()
}
