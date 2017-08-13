
package ru.ispras.lingvodoc.frontend.app.controllers.traits


/* External imports. */

import com.greencatsoft.angularjs.core._
import com.greencatsoft.angularjs.Controller
import com.greencatsoft.angularjs.extensions.{ModalOptions, ModalService}

import org.scalajs.dom.console

import scala.concurrent.ExecutionContext
import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}

/* Lingovodoc imports. */

import ru.ispras.lingvodoc.frontend.app.controllers.common.Value
import ru.ispras.lingvodoc.frontend.app.model.CompositeId
import ru.ispras.lingvodoc.frontend.app.services.BackendService


trait Tools extends ErrorModalHandler
{
  this: Controller[_] =>

  implicit val executionContext: ExecutionContext

  protected[this] def backend: BackendService

  protected[this] def dictionaryId: CompositeId

  protected[this] def perspectiveId: CompositeId

  /** Opens perspective phonology page. */
  @JSExport
  def phonology(): Unit =
  {
    val options = ModalOptions()

    options.templateUrl = "/static/templates/modal/perspectivePhonology.html"
    options.controller = "PerspectivePhonologyModalController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"

    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          perspectiveId = perspectiveId.asInstanceOf[js.Object]
        )
      }
    ).asInstanceOf[js.Dictionary[Any]]

    modal.open[Unit](options)
  }

  /** Opens perspective statistics page. */
  @JSExport
  def statistics(): Unit =
  {
    val options = ModalOptions()

    options.templateUrl = "/static/templates/modal/perspectiveStatistics.html"
    options.controller = "PerspectiveStatisticsModalController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"

    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          perspectiveId = perspectiveId.asInstanceOf[js.Object]
        )
      }
    ).asInstanceOf[js.Dictionary[Any]]

    modal.open[Unit](options)
  }

  /** Launches background task of packaging all sound/markup pairs of perspective as a single archive. */
  @JSExport
  def sound_and_markup(published_mode: String): Unit =
  {
    backend.sound_and_markup(
      perspectiveId, published_mode)

    .map {
      result =>

        /* Showing a message about successfully launched sound/markup archive compilation. */

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
    
    .recover { case e: Throwable => Future.failed(e) }
  }
}

