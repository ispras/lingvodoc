package ru.ispras.lingvodoc.frontend

import com.greencatsoft.angularjs.{Angular, Config}
import com.greencatsoft.angularjs.core.{Route, RouteProvider}
import ru.ispras.lingvodoc.frontend.app.controllers.{PerspectivePropertiesController, DashboardController,
DictionaryPropertiesController}
import ru.ispras.lingvodoc.frontend.app.services.BackendServiceFactory

import scala.scalajs.js.JSApp
import scala.scalajs.js.annotation.JSExport


class RoutingConfig(routeProvider: RouteProvider) extends Config {
  routeProvider
    .when("/dashboard", Route("/assets/templates/home.html", "Dashboard", "DashboardController"))
}

@JSExport
object App extends JSApp {
  override def main() = {
    Angular.module("DashboardModule", Seq("ngRoute", "ui.bootstrap"))
      .config[RoutingConfig]
      .controller[DashboardController]
      .controller[DictionaryPropertiesController]
      .controller[PerspectivePropertiesController]
      .factory[BackendServiceFactory]
  }
}
