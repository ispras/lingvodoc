package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.Scope
import com.greencatsoft.angularjs.extensions.ModalInstance
import com.greencatsoft.angularjs.{AbstractController, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.{UserService, BackendService}
import ru.ispras.lingvodoc.frontend.app.utils

import scala.scalajs.concurrent.JSExecutionContext.Implicits.runNow
import scala.scalajs.js
import scala.scalajs.js.Array
import scala.scalajs.js.annotation.{JSExportAll, JSExport}
import scala.scalajs.js.JSConverters._
import scala.util.{Failure, Success}


@js.native
trait LogoutScope extends Scope {

}

@injectable("LogoutController")
class LogoutController(scope: LogoutScope, backend: BackendService) extends AbstractController[LogoutScope](scope) {

  backend.logout() onComplete {
    case Success(_) => UserService.user = null
    case Failure(e) =>
  }
}
