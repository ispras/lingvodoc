package ru.ispras.lingvodoc.frontend.app.controllers.modal

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services._

import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.UndefOr
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}




@js.native
trait EditDictionaryRolesModalScope extends Scope {
  var dictionary: Dictionary = js.native
  var users: js.Array[UserListEntry] = js.native
  var error: UndefOr[Throwable] = js.native
  var saveEnabled: Boolean = js.native
}

@injectable("EditDictionaryRolesModalController")
class EditDictionaryRolesModalController(scope: EditDictionaryRolesModalScope,
                                         modal: ModalService,
                                         instance: ModalInstance[Unit],
                                         backend: BackendService,
                                         val timeout: Timeout,
                                         val exceptionHandler: ExceptionHandler,
                                         params: js.Dictionary[js.Function0[js.Any]])
  extends AbstractController[EditDictionaryRolesModalScope](scope) with AngularExecutionContextProvider {

  private[this] val dictionary = params("dictionary").asInstanceOf[Dictionary]
  private[this] var permissions = Map[String, Seq[UserListEntry]]()
  private[this] var addUsersActive = Seq[String]()

  scope.dictionary = dictionary
  scope.users = js.Array[UserListEntry]()
  scope.saveEnabled = true

  load()

  @JSExport
  def getRoles(): js.Array[String] = {
    permissions.keys.toJSArray
  }

  @JSExport
  def getUsers(roleName: String): js.Array[UserListEntry] = {
    permissions.find(_._1 == roleName) match {
      case Some(e) => e._2.toJSArray
      case None => js.Array[UserListEntry]()
    }
  }

  @JSExport
  def ok() = {
    val roles = dictionaryRoles()
    scope.saveEnabled = false
    backend.setDictionaryRoles(CompositeId.fromObject(scope.dictionary), roles) onComplete {
      case Success(_) => instance.close(())
      case Failure(e) => setError(e)
    }
  }

  @JSExport
  def cancel() = {
    instance.dismiss(())
  }

  @JSExport
  def toggleAddUsers(role: String) = {
    if (!isAddUsersActive(role)) {
      addUsersActive = addUsersActive :+ role
    } else {
      addUsersActive = addUsersActive.filterNot(_ == role)
    }
  }

  @JSExport
  def isAddUsersActive(role: String): Boolean = {
    addUsersActive.contains(role)
  }


  @JSExport
  def userHasRole(user: UserListEntry, role: String): Boolean = {
    permissions.keySet.find(_ == role) match {
      case Some(_) => permissions(role).exists(_.id == user.id)
      case None => false
    }
  }

  @JSExport
  def addRole(user: UserListEntry, role: String) = {
    permissions.keySet.find(_ == role).foreach {
      _ =>
        permissions = permissions + (role -> (permissions(role) :+ user))
    }
  }


  @JSExport
  def removeRole(user: UserListEntry, role: String) = {
    permissions.keySet.find(_ == role).foreach {
      _ =>
        permissions = permissions + (role -> permissions(role).filterNot(_.id == user.id))
    }
  }


  private[this] def getPermissions(users: Seq[UserListEntry], roles: DictionaryRoles): Map[String, Seq[UserListEntry]] = {
    roles.users.map { case (roleName, ids) =>
      roleName -> ids.flatMap(userId => users.find(_.id == userId))
    }
  }

  private[this] def dictionaryRoles(): DictionaryRoles = {
    val users = permissions.map { case (role, u) => role -> u.map(_.id)}
    DictionaryRoles(users, Map[String, Seq[Int]]())
  }

  private[this] def setError(e: Throwable) = {
    scope.error = e
  }


  private[this] def load() = {

    backend.getUsers onComplete {
      case Success(users) =>
        scope.users = users.toJSArray
        backend.getDictionaryRoles(CompositeId.fromObject(dictionary)) onComplete {
          case Success(roles) =>
            permissions = getPermissions(users, roles)


          case Failure(e) =>
        }
      case Failure(e) =>
    }
  }
}
