package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{Location, _}
import com.greencatsoft.angularjs.extensions.{ModalOptions, ModalService}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import org.scalajs.dom.raw.HTMLInputElement
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseController
import ru.ispras.lingvodoc.frontend.app.controllers.common._
import ru.ispras.lingvodoc.frontend.app.controllers.traits._
import ru.ispras.lingvodoc.frontend.app.exceptions.ControllerException
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, LexicalEntriesType, UserService}

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.URIUtils._
import scala.scalajs.js.annotation.JSExport
import scala.scalajs.js.JSConverters._



@js.native
trait GrantsScope extends Scope {
  var grants: js.Array[Grant] = js.native
}

@injectable("GrantsController")
class GrantsController(scope: GrantsScope,
                       val modal: ModalService,
                       location: Location,
                       userService: UserService,
                       backend: BackendService,
                       timeout: Timeout,
                       val exceptionHandler: ExceptionHandler) extends
  BaseController(scope, modal, timeout)
  with AngularExecutionContextProvider {


  private[this] var users = Seq[UserListEntry]()

  load(() => {

    backend.getUsers map { u =>
      users = u
      backend.grants() map { grants =>
        scope.grants = grants.toJSArray
      } recover {
        case e: Throwable => Future.failed(e)
      }
    }
  })

  @JSExport
  def owners(grant: Grant): String = {
    grant.owners.flatMap(id => users.find(_.id == id)).map(_.name).mkString(", ")
  }

  @JSExport
  def createGrant(): Unit = {

    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/createGrant.html"
    options.controller = "CreateGrantModalController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal()
      }
    ).asInstanceOf[js.Dictionary[Any]]

    val instance = modal.open[Grant](options)

    instance.result map { grant =>
      scope.grants.push(grant)
    }
  }

  override protected def onStartRequest(): Unit = {}

  override protected def onCompleteRequest(): Unit = {}
}
