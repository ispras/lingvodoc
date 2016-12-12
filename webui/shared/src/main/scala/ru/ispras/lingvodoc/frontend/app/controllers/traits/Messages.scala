package ru.ispras.lingvodoc.frontend.app.controllers.traits

import com.greencatsoft.angularjs.{AngularExecutionContextProvider, Controller}
import com.greencatsoft.angularjs.extensions.{ModalOptions, ModalService}

import scala.concurrent.Future
import scala.scalajs.js


trait Messages extends AngularExecutionContextProvider {
  this: Controller[_] =>

  def modalService: ModalService

  def showException(e: Throwable): Unit = {
    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/messages/exception.html"
    options.controller = "MessageModalController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(exception = e.asInstanceOf[js.Any])
      }
    ).asInstanceOf[js.Dictionary[Any]]

    modalService.open[Unit](options)
  }

  def showMessage(title: String, message: String): Unit = {
    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/messages/message.html"
    options.controller = "MessageModalController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal("title" -> title, "message" -> message)
      }
    ).asInstanceOf[js.Dictionary[Any]]
    modalService.open[Unit](options)
  }

  def yesNo(title: String, message: String): Future[Boolean] = {
    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/messages/yesno.html"
    options.controller = "MessageModalController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal("title" -> title, "message" -> message)
      }
    ).asInstanceOf[js.Dictionary[Any]]
    modalService.open[Boolean](options).result flatMap { result =>
      Future.successful(result)
    }
  }
}
