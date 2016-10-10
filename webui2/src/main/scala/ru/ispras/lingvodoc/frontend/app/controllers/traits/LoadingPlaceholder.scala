package ru.ispras.lingvodoc.frontend.app.controllers.traits

import com.greencatsoft.angularjs.Controller
import com.greencatsoft.angularjs.core.Scope

import scala.concurrent.{ExecutionContext, Future, OnCompleteRunnable}
import scala.scalajs.js.Any
import scala.util.{Failure, Success}


trait LoadingPlaceholder {
  this: Controller[_] =>


  protected implicit def executionContext: ExecutionContext

  protected def onLoaded[T](result: T)
  protected def onError(reason: Throwable)
  protected def bootstrap(): Future[_]

  protected def preRequestHook()
  protected def postRequestHook()

  protected def doAjax(load: () => Future[_]) = {
    preRequestHook()
    load() onComplete {
      case Success(result) =>
        postRequestHook()
        onLoaded(result)
      case Failure(e) =>
        postRequestHook()
        onError(e)
    }
  }

  preRequestHook()
  bootstrap() onComplete {
    case Success(result) =>
      postRequestHook()
      onLoaded(result)
    case Failure(e) =>
      postRequestHook()
      onError(e)
  }
}
