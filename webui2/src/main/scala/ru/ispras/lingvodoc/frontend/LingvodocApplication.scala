package ru.ispras.lingvodoc.frontend

import com.greencatsoft.angularjs.{Angular, Config}
import com.greencatsoft.angularjs.core.{HttpProvider, Route, RouteProvider}
import ru.ispras.lingvodoc.frontend.app.controllers.{CreateLanguageController, _}
import ru.ispras.lingvodoc.frontend.app.directives._
import ru.ispras.lingvodoc.frontend.app.services._

import scala.scalajs.js.annotation.JSExport

class LingvodocConfig(routeProvider: RouteProvider, httpProvider: HttpProvider) extends Config {

  routeProvider
    .when("/", Route("/static/templates/home.html", "Home", "HomeController"))
    .when("/login", Route("/static/templates/login.html", "Login", "LoginController"))
    .when("/logout", Route("/static/templates/logout.html", "Logout", "LogoutController"))
    .when("/signup", Route("/static/templates/signup.html", "Logout", "SignupController"))
    .when("/dashboard", Route("/static/templates/dashboard.html", "Dashboard", "DashboardController"))
    .when("/corpora", Route("/static/templates/corpora.html", "Corpora", "CorporaController"))
    .when("/languages", Route("/static/templates/language.html", "Languages", "LanguageController"))
    .when("/dictionary/:dictionaryClientId/:dictionaryObjectId/perspective/:perspectiveClientId/:perspectiveObjectId/view/:page?/:sortBy?", Route("/static/templates/viewDictionary.html", "ViewDictionary", "ViewDictionaryController"))
    .when("/dictionary/:dictionaryClientId/:dictionaryObjectId/perspective/:perspectiveClientId/:perspectiveObjectId/edit/:page?/:sortBy?", Route("/static/templates/editDictionary.html", "EditDictionary", "EditDictionaryController"))
    .when("/dictionary/:dictionaryClientId/:dictionaryObjectId/perspective/:perspectiveClientId/:perspectiveObjectId/publish/:page?/:sortBy?", Route("/static/templates/publishDictionary.html", "PublishDictionary", "PublishDictionaryController"))
    .when("/dictionary/:dictionaryClientId/:dictionaryObjectId/perspective/:perspectiveClientId/:perspectiveObjectId/contributions/:page?/:sortBy?", Route("/static/templates/contributions.html", "Contributions", "ContributionsController"))
    .when("/dictionary/create", Route("/static/templates/createDictionary.html", "CreateDictionary", "CreateDictionaryController"))
    .when("/corpora/create", Route("/static/templates/createCorpus.html", "CreateCorpus", "CreateCorpusController"))
    .when("/files", Route("/static/templates/files.html", "Files", "UserFilesController"))
    .when("/map_search", Route("/static/templates/mapSearch.html", "Map", "MapSearchController"))
    .otherwise(Route("/static/templates/404.html"))
}


@JSExport
object LingvodocApplication {

  @JSExport
  def main() = {
  Angular.module("LingvodocModule", Seq("ngRoute", "ngAnimate", "ui.bootstrap"))
      .config[LingvodocConfig]
	    .factory[BackendServiceFactory]
      .factory[UserServiceFactory]
      //.factory[ExceptionHandlerFactory]
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
      .controller[CreateCorpusController]
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
      .controller[MapSearchController]
      .controller[ViewInfoBlobsController]
      .controller[EditGroupingTagModalController]
      .controller[ContributionsController]
      .controller[CorporaController]
      .directive[ConvertToNumberDirective]
      .directive[OnReadFileDirective]
      .directive[OnReadDirective]
      .directive[TranslatableDirective]
      .directive[WaveSurferDirective]
      .directive[IndeterminateCheckboxDirective]
  }
}
