package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.ModalInstance
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import ru.ispras.lingvodoc.frontend.app.controllers.traits.LoadingPlaceholder
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.BackendService

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.annotation.JSExport


@js.native
trait ViewInfoBlobsScope extends Scope {
  var title: String = js.native
  var blobs: js.Array[File] = js.native
}


@injectable("ViewInfoBlobsController")
class ViewInfoBlobsController(scope: ViewInfoBlobsScope,
                              instance: ModalInstance[Unit],
                              backend: BackendService,
                              val timeout: Timeout,
                              val exceptionHandler: ExceptionHandler,
                              params: js.Dictionary[js.Function0[js.Any]])
  extends AbstractController[ViewInfoBlobsScope](scope)
  with AngularExecutionContextProvider
  with LoadingPlaceholder {


  private[this] val dictionary = params("dictionary").asInstanceOf[Dictionary]
  private[this] val perspective = params("perspective").asInstanceOf[Perspective]
  private[this] val meta = params("meta").asInstanceOf[MetaData]

  scope.title = dictionary.translation
  scope.blobs = js.Array[File]()

  @JSExport
  def ok() = {
    instance.dismiss(())
  }


  @JSExport
  def cancel() = {
    instance.dismiss(())
  }



  override protected def onLoaded[T](result: T): Unit = {}

  override protected def onError(reason: Throwable): Unit = {}

  override protected def preRequestHook(): Unit = {}

  override protected def postRequestHook(): Unit = {}

  doAjax(() => {
      val reqs = meta.info.map(blob => backend.blob(blob.blob)).map { req =>
      req.map { file =>
        Some(file)
      }.recover {
        case e => Option.empty[File]
      }
    }

    Future.sequence(reqs) map { blobs =>
      scope.blobs = blobs.filter(_.nonEmpty).flatten.filter(_.dataType == "pdf").toJSArray
    }
  })
}
