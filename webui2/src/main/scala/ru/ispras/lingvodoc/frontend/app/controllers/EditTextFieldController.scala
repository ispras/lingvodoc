package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.Scope
import com.greencatsoft.angularjs.{AbstractController, injectable}
import ru.ispras.lingvodoc.frontend.app.model.{Dictionary}
import ru.ispras.lingvodoc.frontend.app.services.ModalInstance

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport
import org.scalajs.dom.console

@js.native
trait EditTextFieldControllerScope extends Scope {
  var originalValue: String = js.native
}

@injectable("EditTextFieldController")
class EditTextFieldController(scope: EditTextFieldControllerScope,
                              modalInstance: ModalInstance[String],
                              params: js.Dictionary[js.Function0[js.Any]])
  extends AbstractController[EditTextFieldControllerScope](scope) {
  scope.originalValue = params("originalValue").asInstanceOf[String]
  val isValid = params.getOrElse("isValid",
    (_: String) => (true, None)).asInstanceOf[String => (Boolean, Option[String])]

  @JSExport
  def ok() = {
    isValid(scope.originalValue) match {
      case (true, _) => modalInstance.close(scope.originalValue)
      case (false, Some(errorMsg)) => console.log(errorMsg) // TODO: add alerts
      case (false, None) => ;
    }
  }

  @JSExport
  def cancel() = {
    modalInstance.dismiss(())
  }
}
