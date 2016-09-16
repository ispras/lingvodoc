package ru.ispras.lingvodoc.frontend.app.services

import com.greencatsoft.angularjs.{Factory, Service, injectable}
import com.greencatsoft.angularjs.core.Injector
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.api.exceptions.BackendException

import scala.scalajs.js

@injectable("$exceptionHandler")
class ExceptionHandlerFactory(injector: Injector) extends Factory[js.Function2[Throwable, js.Object, Unit]] {

  override def apply(): js.Function2[Throwable, js.Object, Unit] = {
    // exception handler function
    (e: Throwable, cause: js.Object) => {

      val modal = injector.get[ModalService]("$uibModal")
      val options = ModalOptions()
      options.templateUrl = "/static/templates/modal/exceptionHandler.html"
      options.controller = "ExceptionHandlerController"
      options.backdrop = false
      options.keyboard = false
      options.size = "lg"
      options.resolve = js.Dynamic.literal(
        params = () => {
          js.Dynamic.literal(exception = e.asInstanceOf[js.Object], cause = cause)
        }
      ).asInstanceOf[js.Dictionary[js.Any]]

      val instance = modal.open[Unit](options)
    }
  }
}


