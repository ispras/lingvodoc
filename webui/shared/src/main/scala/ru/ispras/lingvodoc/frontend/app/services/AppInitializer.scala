package ru.ispras.lingvodoc.frontend.app.services

import com.greencatsoft.angularjs.core.{RootScope, Route}
import com.greencatsoft.angularjs.injectable
import com.greencatsoft.angularjs.Runnable

import scala.scalajs.js


@js.native
@injectable("$route")
trait RouteStatus extends js.Object {
  val current: Route = js.native
}

class AppInitializer(rootScope: RootScope, route: RouteStatus) extends Runnable {
  import org.scalajs.dom._
  rootScope.$on("$routeChangeSuccess", () => {
    route.current.title foreach(title => document.title = title)
  })
}
