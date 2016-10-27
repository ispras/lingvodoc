package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{Scope, Timeout}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import ru.ispras.lingvodoc.frontend.app.controllers.traits.{LoadingPlaceholder, SimplePlay}
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, ModalInstance, ModalService}

import scala.scalajs.js

@js.native
trait EditGroupingTagScope extends Scope {

}

@injectable("EditGroupingTagModalController")
class EditGroupingTagModalController(scope: EditGroupingTagScope, modal: ModalService,
                               instance: ModalInstance[Unit],
                               backend: BackendService,
                               val timeout: Timeout,
                               params: js.Dictionary[js.Function0[js.Any]])
  extends AbstractController[EditGroupingTagScope](scope)
    with AngularExecutionContextProvider
    with SimplePlay
    with LoadingPlaceholder {

  override protected def onLoaded[T](result: T): Unit = {}

  override protected def onError(reason: Throwable): Unit = {}

  override protected def preRequestHook(): Unit = {}

  override protected def postRequestHook(): Unit = {}
}
