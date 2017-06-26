package ru.ispras.lingvodoc.frontend.app.controllers.webui

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.ModalService
import com.greencatsoft.angularjs.{AngularExecutionContextProvider, injectable}
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseController
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services._

import scala.scalajs.js
import scala.scalajs.js.Array
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.annotation.JSExport


@js.native
trait UserRequestsScope extends Scope {

}

@injectable("GrantRequests")
class UserRequestsController(scope: UserRequestsScope,
                             val modal: ModalService,
                             backend: BackendService,
                             timeout: Timeout,
                             val exceptionHandler: ExceptionHandler)
  extends BaseController(scope, modal, timeout)
    with AngularExecutionContextProvider {

  private[this] var allRequests: Seq[UserRequest] = Seq.empty[UserRequest]
  private[this] var users: Seq[UserListEntry] = Seq.empty[UserListEntry]
  private[this] var grants: Seq[Grant] = Seq.empty[Grant]
  private[this] var dictionaries: Seq[Dictionary] = Seq.empty[Dictionary]
  private[this] var requestType: RequestType.Value = RequestType.GrantPermission

  @JSExport
  def sender(request: UserRequest): UserListEntry = {
    users.find(_.id == request.senderId).get
  }

  @JSExport
  def requests(): Array[UserRequest] = {
    allRequests.filter(_.`type` == requestType).toJSArray
  }

  @JSExport
  def grant(request: UserRequest): Grant = {
    val grantId = request.subject match {
      case permission: GrantPermission =>
        permission.grantId
      case g: AddDictionaryToGrant =>
        g.grantId
    }
    grants.find(_.id == grantId).get
  }

  @JSExport
  def dictionary(request: UserRequest): Dictionary = {
    val dictionaryId = request.subject match {
      case g: AddDictionaryToGrant =>
        CompositeId(g.clientId, g.objectId)
    }
    dictionaries.find(_.getId == dictionaryId.getId).get
  }

  @JSExport
  def filterGrantPermission(): Unit = {
    requestType = RequestType.GrantPermission
  }

  @JSExport
  def filterAddDictionary(): Unit = {
    requestType = RequestType.AddDictionaryToGrant
  }

  @JSExport
  def filterOrganizationUser(): Unit = {
    requestType = RequestType.ParticipateOrganization
  }

  @JSExport
  def filterOrganizationAdmin(): Unit = {
    requestType = RequestType.AdministrateOrganization
  }

  @JSExport
  def isGrantPermissionRequest(request: UserRequest): Boolean = {
    request.`type` == RequestType.GrantPermission
  }

  @JSExport
  def isAddDictionaryRequest(request: UserRequest): Boolean = {
    request.`type` == RequestType.AddDictionaryToGrant
  }

  @JSExport
  def isOrganizationUserRequest(request: UserRequest): Boolean = {
    request.`type` == RequestType.ParticipateOrganization
  }

  @JSExport
  def isOrganizationAdminRequest(request: UserRequest): Boolean = {
    request.`type` == RequestType.AdministrateOrganization
  }


  @JSExport
  def GrantPermissionRequestsCount(): Int = {
    allRequests.count(_.`type` == RequestType.GrantPermission)
  }

  @JSExport
  def AddDictionaryRequestsCount(): Int = {
    allRequests.count(_.`type` == RequestType.AddDictionaryToGrant)
  }

  @JSExport
  def OrganizationUserRequestsCount(): Int = {
    allRequests.count(_.`type` == RequestType.ParticipateOrganization)
  }

  @JSExport
  def OrganizationAdminRequestCount(): Int = {
    allRequests.count(_.`type` == RequestType.AdministrateOrganization)
  }







  @JSExport
  def accept(request: UserRequest): Unit = {
    backend.acceptUserRequest(request.id, accept = true) map { _ =>
      allRequests = allRequests.filterNot(_.id == request.id)
    }
  }

  @JSExport
  def decline(request: UserRequest): Unit = {
    backend.acceptUserRequest(request.id, accept = false) map { _ =>
      allRequests = allRequests.filterNot(_.id == request.id)
    }
  }

  load(() => {
    backend.getUsers map { u =>
      users = u
      backend.grants() map { g =>
        grants = g
        backend.grantUserRequests map { r =>
          allRequests = r
          val query = DictionaryQuery()
          backend.getDictionaries(query) map { d =>
            dictionaries = d
          }
        }
      }
    }
  })


  override protected def onStartRequest(): Unit = {}

  override protected def onCompleteRequest(): Unit = {}
}
