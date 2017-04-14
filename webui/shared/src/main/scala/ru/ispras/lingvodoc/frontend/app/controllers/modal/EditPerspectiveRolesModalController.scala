package ru.ispras.lingvodoc.frontend.app.controllers.modal

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.{ModalInstance, ModalService}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseModalController
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services._

import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.UndefOr
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}


@js.native
trait EditPerspectiveRolesModalScope extends Scope {
  var dictionary: Dictionary = js.native
  var perspective: Perspective = js.native
  var users: js.Array[UserListEntry] = js.native
  var searchString: UndefOr[String] = js.native
  var searchUsers: js.Array[UserListEntry] = js.native
  var error: UndefOr[Throwable] = js.native
  var saveEnabled: Boolean = js.native
  var permissions: js.Dictionary[js.Dictionary[Boolean]] = js.native
}

@injectable("EditPerspectiveRolesModalController")
class EditPerspectiveRolesModalController(scope: EditPerspectiveRolesModalScope,
                                          val modal: ModalService,
                                          instance: ModalInstance[Unit],
                                          backend: BackendService,
                                          timeout: Timeout,
                                          val exceptionHandler: ExceptionHandler,
                                          params: js.Dictionary[js.Function0[js.Any]])
  extends BaseModalController(scope, modal, instance, timeout, params)
    with AngularExecutionContextProvider {

  private[this] val dictionary = params("dictionary").asInstanceOf[Dictionary]
  private[this] val perspective = params("perspective").asInstanceOf[Perspective]
  private[this] var allUsers = Seq[UserListEntry]()

  scope.dictionary = dictionary
  scope.perspective = perspective
  scope.users = js.Array[UserListEntry]()
  scope.searchString = Option.empty[String].orUndefined
  scope.searchUsers = js.Array[UserListEntry]()
  scope.saveEnabled = true

  @JSExport
  def ok(): Unit = {
    scope.saveEnabled = false
    val permissions = scope.permissions.toMap map { case (role, e) =>
      role -> e.toMap.filter(_._2).keys.map(_.toInt).toSeq
    }
    val roles = PerspectiveRoles(permissions, Map.empty[String, Seq[Int]])
    backend.setPerspectiveRoles(CompositeId.fromObject(dictionary), CompositeId.fromObject(perspective), roles) onComplete {
      case Success(_) => instance.close(())
      case Failure(e) => setError(e)
    }
  }

  @JSExport
  def cancel(): Unit = {
    instance.dismiss(())
  }

  @JSExport
  def getUsers(): js.Array[UserListEntry] = {
    if (!js.isUndefined(scope.permissions)) {
      val ids = scope.permissions.headOption match {
        case Some(p) => p._2.keys.map(_.toInt).toSeq
        case None => Seq.empty[Int]
      }
      ids.flatMap(id => allUsers.find(_.id == id)).toJSArray
    } else {
      Seq.empty[UserListEntry].toJSArray
    }
  }

  @JSExport
  def searchUser(): Unit = {
    scope.searchString.toOption foreach { q =>
      scope.searchUsers = allUsers.filterNot(u => scope.users.exists(_.id == u.id))
        .filter(user => user.login.toLowerCase.contains(q.toLowerCase) || user.intlName.toLowerCase.contains(q.toLowerCase)).take(5).toJSArray
    }
  }

  @JSExport
  def addUser(searchUser: UserListEntry): Unit = {
    scope.permissions = scope.permissions.toMap.map { case (role, users) =>
      role -> (users.toMap + (searchUser.id.toString -> false)).toJSDictionary
    }.toJSDictionary
  }

  private[this] def setError(e: Throwable) = {
    scope.error = e
  }

  private[this] def createRoles(users: Seq[UserListEntry], roles: PerspectiveRoles) = {
    val activeUsers = roles.users.values.reduce(_ ++ _).distinct.sortWith(_ > _).flatMap(id => users.find(_.id == id))
    roles.users.map { case (role, roleUsers) =>
      role -> activeUsers.map(u => (u.id.toString, roleUsers.contains(u.id))).toMap.toJSDictionary
    }.toJSDictionary
  }

  load(() => {
    backend.getUsers flatMap { users =>
      allUsers = users
      backend.getPerspectiveRoles(CompositeId.fromObject(dictionary), CompositeId.fromObject(perspective)) map { roles =>
        scope.users = roles.users.values.reduce(_ ++ _).distinct.sortWith(_ > _).flatMap(id => users.find(_.id == id)).toJSArray
        scope.permissions = createRoles(users, roles)
      }
    }
  })

  override protected def onStartRequest(): Unit = {}

  override protected def onCompleteRequest(): Unit = {}
}

