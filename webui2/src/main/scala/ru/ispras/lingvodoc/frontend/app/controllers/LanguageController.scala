package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.Scope
import com.greencatsoft.angularjs.{AbstractController, injectable}
import ru.ispras.lingvodoc.frontend.app.services.BackendService

import scala.scalajs.js


@js.native
trait LanguageScope extends Scope {

}


@injectable("LanguageController")
class LanguageController(scope: LanguageScope, backend: BackendService) extends AbstractController[LanguageScope](scope) {









}