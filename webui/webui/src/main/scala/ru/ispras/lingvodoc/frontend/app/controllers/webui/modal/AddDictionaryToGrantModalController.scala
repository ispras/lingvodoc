package ru.ispras.lingvodoc.frontend.app.controllers.webui.modal

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.{ModalInstance, ModalService}
import com.greencatsoft.angularjs.{AngularExecutionContextProvider, injectable}
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseModalController
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, UserService}

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.annotation.JSExport


@js.native
trait AddDictionaryToGrantModalScope extends Scope {
  var currentGrants: js.Array[Grant] = js.native
  var grants: js.Array[Grant] = js.native
  var selectedGrantId: Int = js.native
}

@injectable("AddDictionaryToGrantModalController")
class AddDictionaryToGrantModalController(scope: AddDictionaryToGrantModalScope,
                                          val modal: ModalService,
                                          instance: ModalInstance[Unit],
                                          userService: UserService,
                                          backend: BackendService,
                                          timeout: Timeout,
                                          val exceptionHandler: ExceptionHandler,
                                          params: js.Dictionary[js.Function0[js.Any]])

  extends BaseModalController(scope, modal, instance, timeout, params)
    with AngularExecutionContextProvider {

  private[this] val dictionary = params("dictionary").asInstanceOf[Dictionary]
  private[this] var users: Seq[UserListEntry] = Seq.empty[UserListEntry]

  scope.currentGrants = js.Array[Grant]()
  scope.grants = js.Array[Grant]()
  scope.selectedGrantId = -1


  @JSExport
  def addDictionary(): Unit = {

    scope.grants.find(_.id == scope.selectedGrantId) foreach { grant =>
      backend.addDictionaryToGrant(grant.id, CompositeId.fromObject(dictionary)) map { _ =>
        scope.currentGrants.push(grant)
        scope.grants = scope.grants.filterNot(_.id == grant.id)
      }
    }
  }

  @JSExport
  def close(): Unit = {
    instance.dismiss(())
  }

  load(() => {

    backend.getUsers map { u =>
      users = u
      backend.grants() map { grants =>
        scope.currentGrants = grants.filter(_.participants.exists(_.getId == dictionary.getId)).toJSArray
        scope.grants = grants.filter(_.owners.nonEmpty).filterNot(g => scope.currentGrants.exists(_.id == g.id)).toJSArray
      } recover {
        case e: Throwable => Future.failed(e)
      }
    }
  })

  override protected def onStartRequest(): Unit = {}

  override protected def onCompleteRequest(): Unit = {}
}
