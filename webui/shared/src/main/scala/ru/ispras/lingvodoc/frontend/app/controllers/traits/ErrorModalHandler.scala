package ru.ispras.lingvodoc.frontend.app.controllers.traits

import com.greencatsoft.angularjs.extensions.{ModalOptions, ModalService}

import scala.scalajs.js


trait ErrorModalHandler {

  def modalService: ModalService

  def showError(e: Throwable) = {
    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/exceptionHandler.html"
    options.controller = "ExceptionHandlerController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(exception = e.asInstanceOf[js.Object])
      }
    ).asInstanceOf[js.Dictionary[js.Any]]

    val instance = modalService.open[Unit](options)
  }
}
