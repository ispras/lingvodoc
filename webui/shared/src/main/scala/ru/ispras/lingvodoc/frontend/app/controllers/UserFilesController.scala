package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.ModalService
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import org.scalajs.dom._
import ru.ispras.lingvodoc.frontend.app.controllers.traits.ErrorModalHandler
import ru.ispras.lingvodoc.frontend.app.model.{CompositeId, File}
import ru.ispras.lingvodoc.frontend.app.services.BackendService

import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}


@js.native
trait UserFilesScope extends Scope {
  var files: js.Array[File] = js.native
  var dataType: String = js.native
  var progress: Int = js.native
}


@injectable("UserFilesController")
class UserFilesController(scope: UserFilesScope, backend: BackendService, val modalService: ModalService, val timeout: Timeout, val exceptionHandler: ExceptionHandler)
  extends AbstractController[UserFilesScope](scope)
    with AngularExecutionContextProvider
    with ErrorModalHandler {

  scope.files = js.Array[File]()
  scope.dataType = ""
  scope.progress = -1

  load()

  @JSExport
  def upload(file: org.scalajs.dom.raw.File) = {

    val formData = new FormData()
    formData.append("blob", file)
    formData.append("data_type", scope.dataType)

    scope.progress = 0

    backend.uploadFile(formData, (uploaded: Int, total: Int) => {
      scope.$apply(() => {
        scope.progress = (Math.ceil(uploaded / total) * 100).toInt
      })
    }) onComplete  {
      case Success(id) =>
        scope.progress = -1

        backend.userFiles map {
          files =>
            files.find(_.getId == id.getId) foreach {
              file => scope.files.push(file)
          }
        }

      case Failure(e) =>
        showError(e)
        console.error(e.getMessage)
    }
  }

  @JSExport
  def removeFile(file: File): Unit = {
    backend.removeBlob(CompositeId.fromObject(file)) flatMap { _ =>
      backend.userFiles map { files =>
        scope.files = files.toJSArray
      } recover { case e: Throwable =>
        showError(e)
      }
    }
  }

  private[this] def load() = {
    backend.userFiles onComplete {
      case Success(files) =>
        scope.files = files.toJSArray
      case Failure(e) =>
        showError(e)
    }
  }
}
