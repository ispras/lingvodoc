package ru.ispras.lingvodoc.frontend.app.services

import com.greencatsoft.angularjs
import com.greencatsoft.angularjs.core._
import com.greencatsoft.angularjs.{AngularExecutionContextProvider, injectable}

@injectable("LoadingInterceptor")
class LoadingInterceptor(val rootScope: RootScope, val q: Q, val timeout: Timeout) extends HttpInterceptor {

  protected[this] var pendingRequestsCount: Long = 0

  override def request(config: HttpConfig): HttpConfig = {
    pendingRequestsCount += 1
    rootScope.$broadcast("loader.show")
    super.request(config)
  }

  override def response(response: HttpResult): HttpResult = {
    pendingRequestsCount -= 1
    if (pendingRequestsCount == 0) {
      rootScope.$broadcast("loader.hide")
    }
    super.response(response)
  }

  override def responseError[T](rejection: HttpResult): Promise[T] = {
    pendingRequestsCount -= 1
    if (pendingRequestsCount == 0) {
      rootScope.$broadcast("loader.hide")
    }
    super.responseError(rejection)
  }
}

object LoadingInterceptor {
  @injectable("LoadingInterceptor")
  class Factory(val rootScope: RootScope, q: Q, timeout: Timeout) extends angularjs.Factory[LoadingInterceptor] {
    override def apply(): LoadingInterceptor = new LoadingInterceptor(rootScope, q, timeout)
  }
}

