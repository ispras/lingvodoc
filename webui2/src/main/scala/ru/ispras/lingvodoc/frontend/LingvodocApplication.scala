package ru.ispras.lingvodoc.frontend

import com.greencatsoft.angularjs.{Config, Angular}
import com.greencatsoft.angularjs.core.{Route, RouteProvider}
import ru.ispras.lingvodoc.frontend.app.controllers._
import ru.ispras.lingvodoc.frontend.app.services.BackendServiceFactory

import scala.scalajs.js.annotation.JSExport

class RoutingConfig(routeProvider: RouteProvider) extends Config {

  routeProvider
    .when("/", Route("/static/templates/home.html", "Home", "HomeController"))
    .when("/login", Route("/static/templates/login.html", "Login", "LoginController"))
    .when("/logout", Route("/static/templates/logout.html", "Logout", "LogoutController"))
    .when("/dashboard", Route("/static/templates/dashboard.html", "Dashboard", "DashboardController"))
    .when("/dictionary/:dictionaryClientId/:dictionaryObjectId/perspective/:perspectiveClientId/:perspectiveObjectId", Route("/static/templates/viewDictionary.html", "ViewDictionary", "ViewDictionaryController"))
    .otherwise(Route("/home"))
}


@JSExport
object LingvodocApplication {

  @JSExport
  def main() = {
    Angular.module("LingvodocModule", Seq("ngRoute", "ui.bootstrap"))
      .config[RoutingConfig]
      .controller[MainController]
      .controller[NavigationController]
      .controller[LoginController]
      .controller[LogoutController]
      .controller[DashboardController]
      .controller[HomeController]
      .controller[PerspectivePropertiesController]
      .controller[DictionaryPropertiesController]
      .controller[EditDictionaryController]
      .controller[PerspectiveMapController]
      .controller[ViewDictionaryController]
      .controller[SoundMarkupController]
      .factory[BackendServiceFactory]
  }
}
