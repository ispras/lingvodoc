package ru.ispras.lingvodoc.frontend.app.controllers.modal

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.{ModalInstance, ModalService}
import com.greencatsoft.angularjs.injectable
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseModalController
import ru.ispras.lingvodoc.frontend.app.model.{Entity, User}
import ru.ispras.lingvodoc.frontend.app.services.BackendService

import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.UndefOr
import scala.scalajs.js.annotation.JSExport


@js.native
trait UserProfileScope extends Scope {
  var user: UndefOr[User] = js.native
  var passwordConfirmation: String = js.native
}

@injectable("UserProfileController")
class UserProfileController(scope: UserProfileScope,
                            val modal: ModalService,
                            instance: ModalInstance[Unit],
                            val backend: BackendService,
                            timeout: Timeout,
                            val exceptionHandler: ExceptionHandler,
                            params: js.Dictionary[js.Function0[js.Any]])
  extends BaseModalController(scope, modal, instance, timeout, params) {



  @JSExport
  def save(): Unit = {

    scope.user.toOption foreach { user =>
      backend.updateCurrentUser(user) map { _ =>
        instance.close(())
      } recover {
        case e: Throwable =>
          error(e)
          instance.close(())
      }
    }
  }

  @JSExport
  def cancel(): Unit = {
    instance.dismiss(())
  }

  load(() => {
    backend.getCurrentUser map { user =>
      scope.user = Option[User](user).orUndefined
    }
  })

  override protected def onStartRequest(): Unit = {}

  override protected def onCompleteRequest(): Unit = {}
}
