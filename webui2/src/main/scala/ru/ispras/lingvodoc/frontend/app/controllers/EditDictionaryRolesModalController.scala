package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{Scope, Timeout}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services._

import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}


@js.native
trait EditDictionaryRolesModalScope extends Scope {
  var dictionary: Dictionary = js.native
}

@injectable("EditDictionaryRolesModalController")
class EditDictionaryRolesModalController(scope: EditDictionaryRolesModalScope,
                                         modal: ModalService,
                                         instance: ModalInstance[Dictionary],
                                         backend: BackendService,
                                         val timeout: Timeout,
                                         params: js.Dictionary[js.Function0[js.Any]])
  extends AbstractController[EditDictionaryRolesModalScope](scope) with AngularExecutionContextProvider {

  private[this] val dictionary = params("dictionary").asInstanceOf[Dictionary]
  private[this] var permissions = Map[String, Seq[UserListEntry]]()

  scope.dictionary = dictionary

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
    instance.dismiss(())
  }

  @JSExport
  def cancel() = {
    instance.dismiss(())
  }

  private[this] def getPermissions(users: Seq[UserListEntry], roles: DictionaryRoles): Map[String, Seq[UserListEntry]] = {
    roles.users.map { case (roleName, ids) =>
      roleName -> ids.flatMap(userId => users.find(_.id == userId))
    }
  }


  private[this] def load() = {

    backend.getUsers onComplete {
      case Success(users) =>
        backend.getDictionaryRoles(CompositeId.fromObject(dictionary)) onComplete {
          case Success(roles) =>
            permissions = getPermissions(users, roles)
          case Failure(e) =>
        }
      case Failure(e) =>
    }
  }
}
