package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.Scope
import com.greencatsoft.angularjs.extensions.{ModalOptions, ModalService}
import com.greencatsoft.angularjs.{AbstractController, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.BackendService

import scala.scalajs.concurrent.JSExecutionContext.Implicits.runNow
import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.URIUtils.encodeURIComponent
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}


@js.native
trait EditDictionaryScope extends Scope {
  var dictionaries: js.Array[Dictionary] = js.native
  var user: User = js.native
}

@JSExport
@injectable("EditDictionaryController")
class EditDictionaryController(scope: EditDictionaryScope, modal: ModalService, backend: BackendService) extends
AbstractController[EditDictionaryScope](scope) {







}
