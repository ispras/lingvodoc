
package ru.ispras.lingvodoc.frontend.app.controllers.modal


/* External imports. */

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.{ModalInstance, ModalOptions, ModalService}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}

import org.scalajs.dom.console

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.UndefOr
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}

/* Lingvodoc imports. */

import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseModalController
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services._


@js.native
trait PerspectivePhonologyModalScope extends Scope
{
  var error: UndefOr[Throwable] = js.native

  /** Phonology data source, either "all" for all vowels or "selected" for only logest vowels and vowels
   *  with highest intensity. */
  var source: String = js.native

  /** If we should group phonology data by markup descriptions. */
  var group_by_description: Boolean = js.native

  /** If we should show only first translation ('first') or all available translations ('all') of each
   *  word. */
  var translation_choice: String = js.native
}


@injectable("PerspectivePhonologyModalController")
class PerspectivePhonologyModalController(
  scope: PerspectivePhonologyModalScope,
  val modal: ModalService,
  instance: ModalInstance[Unit],
  backend: BackendService,
  timeout: Timeout,
  val exceptionHandler: ExceptionHandler,
  params: js.Dictionary[js.Function0[js.Any]])

  extends BaseModalController(scope, modal, instance, timeout, params)
    with AngularExecutionContextProvider {

  private[this] val __debug__ = false
  private[this] val perspectiveId = params("perspectiveId").asInstanceOf[CompositeId]

  /* By default we extract phonology data from all vowels. */
  scope.source = "all"

  /* By default we do not group phonology data by markup descriptions. */
  scope.group_by_description = false

  /* By default we show all available translations. */
  scope.translation_choice = "all"

  /** Launches phonology generation. */
  @JSExport
  def generate(): Unit =
  {
    backend.phonology(perspectiveId,
      scope.group_by_description,
      scope.translation_choice == "first",
      scope.source == "selected")
    
    .map {
      blob =>

        /* Closing phonology options modal page. */

        instance.dismiss(())

        /* And showing a message about successfully launched phonology computation. */

        val options = ModalOptions()

        options.templateUrl = "/static/templates/modal/message.html"
        options.windowClass = "sm-modal-window"
        options.controller = "MessageController"
        options.backdrop = false
        options.keyboard = false
        options.size = "lg"

        options.resolve = js.Dynamic.literal(
          params = () => {
            js.Dynamic.literal(
              "title" -> "",
              "message" -> "Background task created. Check tasks menu for details."
            )
          }
        ).asInstanceOf[js.Dictionary[Any]]

        modal.open[Unit](options)
    }
    
    .recover { case e: Throwable => setError(e) }
  }

  @JSExport
  def close(): Unit =
  {
    instance.dismiss(())
  }

  private[this] def setError(e: Throwable) =
  {
    scope.error = e
  }

  load(() => Future[Unit](()))

  override protected def onStartRequest(): Unit = {}

  override protected def onCompleteRequest(): Unit = {}
}

