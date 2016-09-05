package ru.ispras.lingvodoc.frontend

import com.greencatsoft.angularjs.{Angular, Config}
import com.greencatsoft.angularjs.core.{Route, RouteProvider}
import ru.ispras.lingvodoc.frontend.app.controllers._
import ru.ispras.lingvodoc.frontend.app.directives.ConvertToNumberDirective
import ru.ispras.lingvodoc.frontend.app.services.{BackendServiceFactory, ExceptionHandlerFactory, UserService, UserServiceFactory}

import scala.scalajs.js.annotation.JSExport

class RoutingConfig(routeProvider: RouteProvider) extends Config {

  routeProvider
    .when("/", Route("/static/templates/home.html", "Home", "HomeController"))
    .when("/login", Route("/static/templates/login.html", "Login", "LoginController"))
    .when("/logout", Route("/static/templates/logout.html", "Logout", "LogoutController"))
    .when("/signup", Route("/static/templates/signup.html", "Logout", "SignupController"))
    .when("/dashboard", Route("/static/templates/dashboard.html", "Dashboard", "DashboardController"))
    .when("/dictionary/:dictionaryClientId/:dictionaryObjectId/perspective/:perspectiveClientId/:perspectiveObjectId", Route("/static/templates/viewDictionary.html", "ViewDictionary", "ViewDictionaryController"))
    .when("/dictionary/create", Route("/static/templates/createDictionary.html", "CreateDictionary", "CreateDictionaryController"))
    .otherwise(Route("/"))
}


@JSExport
object LingvodocApplication {

  @JSExport
  def main() = {

    Angular.module("LingvodocModule", Seq("ngRoute", "ngAnimate", "ui.bootstrap"))
      .config[RoutingConfig]
	    .factory[BackendServiceFactory]
      .factory[UserServiceFactory]
      //.factory[ExceptionHandlerFactory]
      .controller[MainController]
      .controller[NavigationController]
      .controller[LoginController]
      .controller[LogoutController]
      .controller[SignupController]
      .controller[DashboardController]
      .controller[HomeController]
      .controller[CreateDictionaryController]
      .controller[PerspectivePropertiesController]
      .controller[DictionaryPropertiesController]
      .controller[EditDictionaryController]
      .controller[PerspectiveMapController]
      .controller[ViewDictionaryController]
      .controller[SoundMarkupController]
      .controller[ExceptionHandlerController]
      .controller[CreateFieldController]
      .directive[ConvertToNumberDirective]
  }
}
