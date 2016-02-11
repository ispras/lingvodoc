package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.Scope
import com.greencatsoft.angularjs.extensions.ModalInstance
import com.greencatsoft.angularjs.{AbstractController, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.model.{Field, Perspective, Dictionary, Language}
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import ru.ispras.lingvodoc.frontend.app.utils

import scala.scalajs.concurrent.JSExecutionContext.Implicits.runNow
import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport
import scala.scalajs.js.JSConverters._
import scala.util.{Failure, Success}

@js.native
trait PerspectivePropertiesScope extends Scope {
  var dictionary: Dictionary = js.native
  var perspective: Perspective = js.native
}

@injectable("PerspectivePropertiesController")
class PerspectivePropertiesController(scope: PerspectivePropertiesScope,
                                     instance: ModalInstance[Perspective],
                                     backend: BackendService,
                                     params: js.Dictionary[js.Function0[js.Any]])
  extends AbstractController[PerspectivePropertiesScope](scope) {

  scope.dictionary = params("dictionary").asInstanceOf[Dictionary]
  scope.perspective = params("perspective").asInstanceOf[Perspective]

  val backupPerspective = scope.perspective.copy()

  backend.getPerspectiveFields(scope.dictionary, scope.perspective) onComplete {
    case Success(fields) =>
      console.log(fields.toString)
    case Failure(e) =>
      console.log(e.getMessage)
  }


  @JSExport
  def ok() = {








      instance.dismiss(())
  }

  @JSExport
  def cancel() = {
    instance.dismiss(())
  }
}
