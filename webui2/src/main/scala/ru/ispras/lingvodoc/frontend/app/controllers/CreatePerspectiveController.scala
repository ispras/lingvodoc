package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.Scope
import ru.ispras.lingvodoc.frontend.app.services.ModalInstance
import com.greencatsoft.angularjs.{AbstractController, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.model.{Field, Perspective, Dictionary, Language}
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import ru.ispras.lingvodoc.frontend.app.utils

import ru.ispras.lingvodoc.frontend.app.utils.LingvodocExecutionContext.Implicits.executionContext
import scala.scalajs.js
import scala.scalajs.js.Array
import scala.scalajs.js.annotation.{JSExportAll, JSExport}
import scala.scalajs.js.JSConverters._
import scala.util.{Failure, Success}



@js.native
trait CreatePerspectiveScope extends Scope {
  var dictionary: Dictionary = js.native
  var perspective: Perspective = js.native
  var authors: String = js.native
  var fields: js.Array[FieldWrapper] = js.native
}


@injectable("CreatePerspectiveController")
class CreatePerspectiveController(scope: CreatePerspectiveScope,
                                  instance: ModalInstance[Perspective],
                                  backend: BackendService,
                                  params: js.Dictionary[js.Function0[js.Any]])
  extends AbstractController[CreatePerspectiveScope](scope) {

  scope.fields = js.Array()


  @JSExport
  def addField() = {
    //scope.fields.push(new FieldWrapper(new Field(-1, -1, "", "", "", "", "", 1, "", js.Array())))
  }

  @JSExport
  def removeField(index: Int) = {
    scope.fields = scope.fields.zipWithIndex.filter(_._2 != index).map(_._1)
  }
}