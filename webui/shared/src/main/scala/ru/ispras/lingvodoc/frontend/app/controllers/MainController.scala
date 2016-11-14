package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.Scope
import com.greencatsoft.angularjs.{AbstractController, injectable}
import ru.ispras.lingvodoc.frontend.app.services.BackendService

import scala.scalajs.js


@js.native
trait MainScope extends Scope {

}

@injectable("MainController")
class MainController(scope: MainScope, backend: BackendService) extends AbstractController[MainScope](scope) {


}
