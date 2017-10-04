package ru.ispras.lingvodoc.frontend.app.controllers.modal

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.{ModalInstance, ModalService}
import com.greencatsoft.angularjs.injectable
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseModalController
import ru.ispras.lingvodoc.frontend.app.model.{Entity, User}
import ru.ispras.lingvodoc.frontend.app.services.BackendService

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.UndefOr
import scala.scalajs.js.annotation.JSExport


@js.native
trait UserProfileScope extends Scope {
  var user: UndefOr[User] = js.native
  var password: String = js.native
  var newPassword: String = js.native
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

  scope.password = ""
  scope.newPassword = ""
  scope.passwordConfirmation = ""

  @JSExport
  def saveDisabled(): Boolean = {
    scope.newPassword.nonEmpty && !(scope.password.nonEmpty && scope.passwordConfirmation == scope.newPassword)
  }


  @JSExport
  def save(): Unit = {

    var requests = Seq[Future[Unit]]()
    if (scope.password.nonEmpty && scope.newPassword.nonEmpty && scope.passwordConfirmation == scope.newPassword) {
      requests = requests :+ backend.updatePassword(scope.password, scope.newPassword)
    }

    scope.user.toOption foreach { user =>
      requests = requests :+ backend.updateCurrentUser(user)
    }

    Future.sequence(requests) map { _ =>
      instance.close(())
    } recover {
      case e: Throwable =>
        error(e)
        instance.close(())
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
