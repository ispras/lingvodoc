package ru.ispras.lingvodoc.frontend.app.controllers.webui

import com.greencatsoft.angularjs.{AngularExecutionContextProvider, injectable}
import com.greencatsoft.angularjs.core.{ExceptionHandler, Location, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.{ModalOptions, ModalService}
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseController
import ru.ispras.lingvodoc.frontend.app.model.{Grant, Organization, User, UserListEntry}
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, UserService}

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.UndefOr
import scala.scalajs.js.annotation.JSExport


@js.native
trait OrganizationsScope extends Scope {
  var organizations: js.Array[Organization] = js.native
}

@injectable("OrganizationsController")
class OrganizationsController(scope: OrganizationsScope,
                             val modal: ModalService,
                             location: Location,
                             userService: UserService,
                             backend: BackendService,
                             timeout: Timeout,
                             val exceptionHandler: ExceptionHandler) extends
  BaseController(scope, modal, timeout) with AngularExecutionContextProvider {

  private[this] var users = Seq[UserListEntry]()
  private[this] var currentUser: UndefOr[User] = Option.empty[User].orUndefined



  @JSExport
  def join(organization: Organization): Unit = {
    userService.get() foreach { user =>
      backend.joinOrganization(organization.id)
    }
  }

  @JSExport
  def joinAdmin(organization: Organization): Unit = {
    userService.get() foreach { user =>
      backend.joinOrganizationAdmin(organization.id)
    }
  }

  @JSExport
  def isCurrentUserOrganizationAdmin(organization: Organization): Boolean = {
    val user = userService.getUser()
    organization.admin.contains(user.id)
  }

  @JSExport
  def isCurrentUserOrganizationMember(organization: Organization): Boolean = {
    val user = userService.getUser()
    organization.users.contains(user.id)
  }

  @JSExport
  def isEditDisabled(organization: Organization): Boolean = {
    currentUser.toOption match {
      case Some(user) =>
        user.id != 1 && !organization.admin.contains(user.id)
      case None =>
        true
    }
  }


  @JSExport
  def createOrganization(): Unit = {
    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/createOrganization.html"
    options.controller = "CreateOrganizationModalController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal()
      }
    ).asInstanceOf[js.Dictionary[Any]]

    val instance = modal.open[Organization](options)

    instance.result map { organization =>
      scope.organizations.push(organization)
    }
  }

  @JSExport
  def editOrganization(organization: Organization): Unit = {
    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/createOrganization.html"
    options.controller = "CreateOrganizationModalController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal("organization" -> organization.asInstanceOf[js.Object])
      }
    ).asInstanceOf[js.Dictionary[Any]]

    val instance = modal.open[Organization](options)

    instance.result map { organization =>
      scope.organizations.push(organization)
    }
  }



  load(() => {

    backend.getUsers map { u =>
      users = u

      backend.getCurrentUser map { c =>
        currentUser = Some(c).orUndefined
      }

      backend.organizations() map { organizations =>
        scope.organizations = organizations.toJSArray
      } recover {
        case e: Throwable => Future.failed(e)
      }
    }
  })

  override protected def onStartRequest(): Unit = {}

  override protected def onCompleteRequest(): Unit = {}
}
