package ru.ispras.lingvodoc.frontend.app.controllers.webui.modal

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.{ModalInstance, ModalService}
import com.greencatsoft.angularjs.{AngularExecutionContextProvider, injectable}
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseModalController
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.UndefOr




@js.native
trait CreateOrganizationModalScope extends Scope {
  var searchString: String = js.native
  var users: js.Array[UserListEntry] = js.native
  var searchUsers: js.Array[UserListEntry] = js.native
  var organizationName: String = js.native
  var organizationAbout: String = js.native
}

@injectable("CreateOrganizationModalController")
class CreateOrganizationModalController(scope: CreateOrganizationModalScope,
                                 val modal: ModalService,
                                 instance: ModalInstance[Grant],
                                 backend: BackendService,
                                 timeout: Timeout,
                                 val exceptionHandler: ExceptionHandler,
                                 params: js.Dictionary[js.Function0[js.Any]])
  extends BaseModalController(scope, modal, instance, timeout, params)
    with AngularExecutionContextProvider {

  private[this] val organizationOpt = params.get("organization").map(_.asInstanceOf[Organization])
  private[this] var allUsers = Seq[UserListEntry]()
  private[this] var addUsers = Seq[Int]()
  private[this] var removeUsers = Seq[Int]()

  scope.searchString = ""
  scope.users = js.Array[UserListEntry]()


  @JSExport
  def searchUser(): Unit = {
    scope.searchUsers = allUsers.filterNot(u => scope.users.exists(_.id == u.id))
      .filter(user => user.login.toLowerCase.contains(scope.searchString.toLowerCase) || user.intlName.toLowerCase.contains(scope.searchString.toLowerCase)).take(5).toJSArray
  }

  @JSExport
  def addUser(user: UserListEntry): Unit = {
    if (!scope.users.exists(_.id == user.id)) {
      addUsers = addUsers :+ user.id
      scope.users.push(user)
    }
  }

  @JSExport
  def removeUser(user: UserListEntry): Unit = {
    scope.users = scope.users.filterNot(_.id == user.id)
    removeUsers = removeUsers :+ user.id
  }

  @JSExport
  def save(): Unit = {

    organizationOpt match {
      case Some(o) =>
        backend.updateOrganization(o.copy(name = scope.organizationName, about = scope.organizationAbout), addUsers, removeUsers) map { _ =>
          instance.dismiss(())
        }
      case None =>
        backend.createOrganization(scope.organizationName, scope.organizationAbout) map { _ =>
          instance.dismiss(())
        }
    }
  }

  @JSExport
  def cancel(): Unit = {
    instance.dismiss(())
  }


  load(() => {
    backend.getUsers map { users =>
      allUsers = users

      organizationOpt match {
        case Some(o) =>
          scope.organizationName = o.name
          scope.organizationAbout = o.about
          scope.users = o.users.flatMap(id => users.find(_.id == id)).toJSArray
        case None =>
          scope.organizationName = ""
          scope.organizationAbout = ""
      }
    } recover {
      case e: Throwable =>
        showError(e)
    }
  })



  override protected def onStartRequest(): Unit = {}

  override protected def onCompleteRequest(): Unit = {}
}
