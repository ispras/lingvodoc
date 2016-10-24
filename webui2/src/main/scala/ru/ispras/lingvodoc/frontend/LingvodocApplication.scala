package ru.ispras.lingvodoc.frontend

import com.greencatsoft.angularjs.{Angular, Config}
import com.greencatsoft.angularjs.core.{Route, RouteProvider}
import ru.ispras.lingvodoc.frontend.app.controllers.{CreateLanguageController, _}
import ru.ispras.lingvodoc.frontend.app.directives.{ConvertToNumberDirective, OnReadDirective, OnReadFileDirective, TranslatableDirective}
import ru.ispras.lingvodoc.frontend.app.services.{BackendServiceFactory, ExceptionHandlerFactory, UserService, UserServiceFactory}

import scala.scalajs.js.annotation.JSExport

class RoutingConfig(routeProvider: RouteProvider) extends Config {

  routeProvider
    .when("/", Route("/static/templates/home.html", "Home", "HomeController"))
    .when("/login", Route("/static/templates/login.html", "Login", "LoginController"))
    .when("/logout", Route("/static/templates/logout.html", "Logout", "LogoutController"))
    .when("/signup", Route("/static/templates/signup.html", "Logout", "SignupController"))
    .when("/dashboard", Route("/static/templates/dashboard.html", "Dashboard", "DashboardController"))
    .when("/languages", Route("/static/templates/language.html", "Languages", "LanguageController"))
    .when("/dictionary/:dictionaryClientId/:dictionaryObjectId/perspective/:perspectiveClientId/:perspectiveObjectId/view", Route("/static/templates/viewDictionary.html", "ViewDictionary", "ViewDictionaryController"))
    .when("/dictionary/:dictionaryClientId/:dictionaryObjectId/perspective/:perspectiveClientId/:perspectiveObjectId/edit", Route("/static/templates/editDictionary.html", "EditDictionary", "EditDictionaryController"))
    .when("/dictionary/:dictionaryClientId/:dictionaryObjectId/perspective/:perspectiveClientId/:perspectiveObjectId/publish", Route("/static/templates/publishDictionary.html", "PublishDictionary", "PublishDictionaryController"))
    .when("/dictionary/create", Route("/static/templates/createDictionary.html", "CreateDictionary", "CreateDictionaryController"))
    .when("/files", Route("/static/templates/files.html", "Files", "UserFilesController"))
    .otherwise(Route("/static/templates/404.html"))
}


@JSExport
object LingvodocApplication {

  @JSExport
  def main() = {
    Angular.module("LingvodocModule", Seq("ngRoute", "ui.bootstrap"))
      .config[RoutingConfig]
	    .factory[BackendServiceFactory]
      .factory[UserServiceFactory]
      .factory[ExceptionHandlerFactory]
      .controller[MainController]
      .controller[NavigationController]
      .controller[LoginController]
      .controller[LogoutController]
      .controller[SignupController]
      .controller[DashboardController]
      .controller[LanguageController]
      .controller[HomeController]
      .controller[CreateLanguageController]
      .controller[CreateDictionaryController]
      .controller[EditDictionaryModalController]
      .controller[ViewDictionaryModalController]
      .controller[PerspectivePropertiesController]
      .controller[DictionaryPropertiesController]
      .controller[CreatePerspectiveModalController]
      .controller[EditDictionaryController]
      .controller[PerspectiveMapController]
      .controller[ViewDictionaryController]
      .controller[PublishDictionaryController]
      .controller[SoundMarkupController]
      .controller[ExceptionHandlerController]
      .controller[CreateFieldController]
      .controller[EditDictionaryRolesModalController]
      .controller[EditPerspectiveRolesModalController]
      .controller[UserFilesController]
      .directive[ConvertToNumberDirective]
      .directive[OnReadFileDirective]
      .directive[OnReadDirective]
      .directive[TranslatableDirective]
  }
}
