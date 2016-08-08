package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{Location, RootScope, Scope}
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, ModalInstance, UserService}
import com.greencatsoft.angularjs.{AbstractController, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.utils
import ru.ispras.lingvodoc.frontend.app.utils.LingvodocExecutionContext.Implicits.executionContext

import scala.scalajs.js
import scala.scalajs.js.Array
import scala.scalajs.js.annotation.{JSExport, JSExportAll}
import scala.scalajs.js.JSConverters._
import scala.util.{Failure, Success}


@js.native
trait LogoutScope extends Scope {

}

@injectable("LogoutController")
class LogoutController(scope: LogoutScope, location: Location, rootScope: RootScope, backend: BackendService) extends AbstractController[LogoutScope](scope) {



  backend.logout() onComplete {
    case Success(_) =>

      rootScope.$emit("user.logout")
      location.path("/")

    case Failure(e) =>
      // failed to logout?
  }
}
