package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.Scope
import com.greencatsoft.angularjs.{AbstractController, injectable}
import org.scalajs.dom._
import ru.ispras.lingvodoc.frontend.app.exceptions.ControllerException
import ru.ispras.lingvodoc.frontend.app.model.File
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, ModalOptions, ModalService}
import ru.ispras.lingvodoc.frontend.app.utils.LingvodocExecutionContext.Implicits.executionContext

import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}


@js.native
trait UserFilesScope extends Scope {
  var files: js.Array[File] = js.native
  var dataType: String = js.native
}


@injectable("UserFilesController")
class UserFilesController(scope: UserFilesScope, backend: BackendService) extends AbstractController[UserFilesScope](scope) {

  scope.files = js.Array[File]()
  scope.dataType = ""

  load()

  @JSExport
  def upload(fileName: String, fileType: String, fileContent: String) = {

    val req = js.Dynamic.literal("name" -> fileName, "type" -> fileType, "content" -> fileContent, "data_type" -> scope.dataType)
    backend.uploadFile(req) onComplete  {
      case Success(id) => console.log("uploaded")
      case Failure(e) =>
    }
  }

  private[this] def load() = {
    backend.userFiles onComplete {
      case Success(files) =>
        scope.files = files.toJSArray
      case Failure(e) =>
    }
  }
}
