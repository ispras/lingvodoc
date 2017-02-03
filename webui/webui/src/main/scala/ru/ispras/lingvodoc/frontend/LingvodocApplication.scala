package ru.ispras.lingvodoc.frontend

import com.greencatsoft.angularjs.{Angular, Config, Module}
import com.greencatsoft.angularjs.core.{HttpProvider, Route, RouteProvider}
import ru.ispras.lingvodoc.frontend.app.controllers.modal._
import ru.ispras.lingvodoc.frontend.app.controllers.webui.modal.ViewSociolinguisticsInfoController
import ru.ispras.lingvodoc.frontend.app.controllers.webui.{PerspectivePropertiesController, SociolinguisticsController}
import ru.ispras.lingvodoc.frontend.app.controllers._
import ru.ispras.lingvodoc.frontend.app.directives._
import ru.ispras.lingvodoc.frontend.app.services._

import scala.scalajs.js.annotation.JSExport

class LingvodocConfig(routeProvider: RouteProvider, httpProvider: HttpProvider) extends Config {

  routeProvider
    .when("/", Route("/static/templates/home.html", "Lingvodoc 2.0", "HomeController"))
    .when("/login", Route("/static/templates/login.html", "Lingvodoc 2.0 / Login", "LoginController"))
    .when("/logout", Route("/static/templates/logout.html", "Lingvodoc 2.0 / Logout", "LogoutController"))
    .when("/signup", Route("/static/templates/signup.html", "Lingvodoc 2.0 / Sign up", "SignupController"))
    .when("/dashboard", Route("/static/templates/dashboard.html", "Lingvodoc 2.0 / Dashboard", "DashboardController"))
    .when("/corpora", Route("/static/templates/corpora.html", "Lingvodoc 2.0 / Corpora", "CorporaController"))
    .when("/languages", Route("/static/templates/language.html", "Lingvodoc 2.0 / Languages", "LanguageController"))
    .when("/dictionary/:dictionaryClientId/:dictionaryObjectId/perspective/:perspectiveClientId/:perspectiveObjectId/view/:page?/:sortBy?", Route("/static/templates/viewDictionary.html", "Lingvodoc 2.0 / View", "ViewDictionaryController"))
    .when("/dictionary/:dictionaryClientId/:dictionaryObjectId/perspective/:perspectiveClientId/:perspectiveObjectId/edit/:page?/:sortBy?", Route("/static/templates/editDictionary.html", "Lingvodoc 2.0 / Edit", "EditDictionaryController"))
    .when("/dictionary/:dictionaryClientId/:dictionaryObjectId/perspective/:perspectiveClientId/:perspectiveObjectId/publish/:page?/:sortBy?", Route("/static/templates/publishDictionary.html", "Lingvodoc 2.0 / Publish", "PublishDictionaryController"))
    .when("/dictionary/:dictionaryClientId/:dictionaryObjectId/perspective/:perspectiveClientId/:perspectiveObjectId/contributions/:page?/:sortBy?", Route("/static/templates/contributions.html", "Lingvodoc 2.0 / Contributions", "ContributionsController"))

    .when("/dictionary/:dictionaryClientId/:dictionaryObjectId" +
        "/perspective/:perspectiveClientId/:perspectiveObjectId/merge",
      Route("/static/templates/mergeDictionary.html", "Lingvodoc 2.0 / Merge suggestions", "MergeDictionaryController"))

    .when("/dictionary/create", Route("/static/templates/createDictionary.html", "Lingvodoc 2.0 / Create dictionary", "CreateDictionaryController"))
    .when("/corpora/create", Route("/static/templates/createCorpus.html", "Lingvodoc 2.0 / Create corpus", "CreateCorpusController"))
    .when("/files", Route("/static/templates/files.html", "Lingvodoc 2.0 / Files", "UserFilesController"))
    .when("/map_search", Route("/static/templates/mapSearch.html", "Lingvodoc 2.0 / Map search", "MapSearchController"))
    .when("/sociolinguistics", Route("/static/templates/sociolinguistics.html", "Lingvodoc 2.0 / Sociolinguistics", "SociolinguisticsController"))
    .when("/desktop_software", Route("/static/templates/desktop.html", "Lingvodoc 2.0 / Desktop software"))
    .otherwise(Route("/static/templates/404.html"))
}


@JSExport
object LingvodocApplication {

  @JSExport
  def main(): Unit = {

    Angular.module("LingvodocModule", Seq("ngRoute", "ngSanitize", "ngAnimate", "ui.bootstrap"))
      .config[LingvodocConfig]
	    .factory[BackendServiceFactory]
      .factory[UserServiceFactory]
      //.factory[ExceptionHandlerFactory]
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
      .controller[webui.EditDictionaryController]
      .controller[PerspectiveMapController]
      .controller[ViewDictionaryController]
      .controller[MergeDictionaryController]
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
      .controller[SociolinguisticsController]
      .controller[ViewSociolinguisticsInfoController]
      .controller[ConvertEafController]
      .controller[DownloadEmbeddedBlobController]
      .controller[MessageController]
      .directive[ConvertToNumberDirective]
      .directive[OnReadFileDirective]
      .directive[OnReadDirective]
      .directive[TranslatableDirective]
      .directive[WaveSurferDirective]
      .directive[IndeterminateCheckboxDirective]
      .directive[DataLinkDirective]
      .directive[ClickAndHoldDirective]
      .run[AppInitializer]
  }
}
