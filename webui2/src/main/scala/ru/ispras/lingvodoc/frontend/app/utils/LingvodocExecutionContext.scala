package ru.ispras.lingvodoc.frontend.app.utils

import scala.concurrent.ExecutionContextExecutor

object LingvodocExecutionContext extends ExecutionContextExecutor {

  def execute(runnable: Runnable): Unit = {
    try {
      runnable.run()
    } catch {
      case t: Throwable => reportFailure(t)
    }
  }

  def reportFailure(t: Throwable): Unit = t.printStackTrace()


  object Implicits {
    implicit val executionContext: ExecutionContextExecutor = LingvodocExecutionContext
  }
}


