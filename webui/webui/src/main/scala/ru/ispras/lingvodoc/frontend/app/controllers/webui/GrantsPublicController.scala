package ru.ispras.lingvodoc.frontend.app.controllers.webui

import com.greencatsoft.angularjs.{AngularExecutionContextProvider, injectable}
import com.greencatsoft.angularjs.core.{ExceptionHandler, Location, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.ModalService
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseController
import ru.ispras.lingvodoc.frontend.app.model.{Grant, UserListEntry}
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, UserService}

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.annotation.JSExport


@js.native
trait GrantsPublicScope extends Scope {
  var grants: js.Array[Grant] = js.native
}

@injectable("GrantsPublicController")
class GrantsPublicController(scope: GrantsPublicScope,
                              val modal: ModalService,
                              location: Location,
                              userService: UserService,
                              backend: BackendService,
                              timeout: Timeout,
                              val exceptionHandler: ExceptionHandler) extends
  BaseController(scope, modal, timeout)
  with AngularExecutionContextProvider {

  private[this] var users = Seq[UserListEntry]()

  @JSExport
  def join(grant: Grant): Unit = {

    userService.get() foreach { user =>
      backend.grantUserPermission(grant.id)
    }
  }

  @JSExport
  def owners(grant: Grant): String = {
    grant.owners.flatMap(id => users.find(_.id == id)).map(_.name).mkString(", ")
  }

  load(() => {

    backend.getUsers map { u =>
      users = u
      backend.grants() map { grants =>

        backend.getCurrentUser map { user =>
          scope.grants = grants.filterNot(_.owners.contains(user.id)).toJSArray
        }
      } recover {
        case e: Throwable => Future.failed(e)
      }
    }
  })


  override protected def onStartRequest(): Unit = {}

  override protected def onCompleteRequest(): Unit = {}
}