package ru.ispras.lingvodoc.frontend.app.controllers.base

import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider}
import com.greencatsoft.angularjs.core.{Scope, Timeout}

import scala.concurrent.Future

abstract class BaseController[ScopeClass <: Scope](scope: ScopeClass, val timeout: Timeout)
  extends AbstractController[ScopeClass](scope)
    with AngularExecutionContextProvider {


  protected def onStartRequest() = {}

  protected def onCompleteRequest() = {}

  protected def initScope()

  protected def load()

  protected def reload()

  protected def request(loadFunction: () => Future[_]) = {
    onStartRequest()
    loadFunction() map { result =>
      onCompleteRequest()
    } recover {
      case e: Throwable =>
        onCompleteRequest()
    }
  }

  initScope()
  load()
}
