package ru.ispras.lingvodoc.frontend.app.controllers.webui

import com.greencatsoft.angularjs.{AngularExecutionContextProvider, injectable}
import com.greencatsoft.angularjs.core.{ExceptionHandler, Location, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.{ModalOptions, ModalService}
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseController
import ru.ispras.lingvodoc.frontend.app.model.{Grant, Organization, UserListEntry}
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, UserService}

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.JSConverters._
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

  @JSExport
  def join(organization: Organization): Unit = {
    userService.get() foreach { user =>
      backend.joinOrganization(organization.id)
    }
  }

  @JSExport
  def joinAdmins(organization: Organization): Unit = {
    userService.get() foreach { user =>
      backend.joinOrganizationAdmin(organization.id)
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


  load(() => {

    backend.getUsers map { u =>
      users = u
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
