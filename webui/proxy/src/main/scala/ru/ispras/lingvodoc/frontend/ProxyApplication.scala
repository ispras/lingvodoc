package ru.ispras.lingvodoc.frontend

import ru.ispras.lingvodoc.frontend.app.controllers.proxy
import com.greencatsoft.angularjs.{Angular, Config, Module}
import com.greencatsoft.angularjs.core.{HttpProvider, Route, RouteProvider}
import ru.ispras.lingvodoc.frontend.app.controllers.modal.{ConvertEafController, CreateLanguageController, CreatePerspectiveModalController, DictionaryStatisticsModalController, DownloadEmbeddedBlobController, EditDictionaryModalController, EditDictionaryRolesModalController, EditGroupingTagModalController, EditPerspectiveRolesModalController, MessageController, PerspectiveMapController, PerspectivePhonologyModalController, PerspectiveStatisticsModalController, SoundMarkupController, UserProfileController, ViewDictionaryModalController, _}
import ru.ispras.lingvodoc.frontend.app.controllers.webui.modal.{AddDictionaryToGrantModalController, ContributionsGroupingTagModalController, ContributionsLinkedDictionaryModalController, CreateGrantModalController, CreateOrganizationModalController, PublishLinkedDictionaryModalController, ViewSociolinguisticsInfoController, _}
import ru.ispras.lingvodoc.frontend.app.controllers.webui.{EditTranslationsController, GrantsController, GrantsPublicController, OrganizationsController, PerspectivePropertiesController, SociolinguisticsController, UserRequestsController, _}
import ru.ispras.lingvodoc.frontend.app.controllers.{ContributionsController, CorporaController, CreateCorpusController, CreateDictionaryController, CreateFieldController, DashboardController, DictionaryPropertiesController, ExceptionHandlerController, HomeController, LanguageController, LoginController, LogoutController, MapSearchController, MergeDictionaryController, NavigationController, PublishDictionaryController, SignupController, UserFilesController, ViewDictionaryController, ViewInfoBlobsController, _}
import ru.ispras.lingvodoc.frontend.app.directives.{ClickAndHoldDirective, ConvertToNumberDirective, DataLinkDirective, IndeterminateCheckboxDirective, OnReadDirective, OnReadFileDirective, TranslatableDirective, WaveSurferDirective, _}
import ru.ispras.lingvodoc.frontend.app.services.{AppInitializer, BackendServiceFactory, UserServiceFactory, _}

import scala.scalajs.js.annotation.JSExport

class LingvodocConfig(routeProvider: RouteProvider, httpProvider: HttpProvider) extends Config {

  routeProvider
    .when("/", Route("/static/templates/home.html", "Lingvodoc 2.1", "HomeController"))
    .when("/login", Route("/static/templates/login.html", "Lingvodoc 2.1 / Login", "LoginController"))
    .when("/logout", Route("/static/templates/logout.html", "Lingvodoc 2.1 / Logout", "LogoutController"))
    .when("/signup", Route("/static/templates/signup.html", "Lingvodoc 2.1 / Sign up", "SignupController"))
    .when("/dashboard", Route("/static/templates/dashboard.html", "Lingvodoc 2.1 / Dashboard", "DashboardController"))
    .when("/corpora", Route("/static/templates/corpora.html", "Lingvodoc 2.1 / Corpora", "CorporaController"))
    .when("/languages", Route("/static/templates/language.html", "Lingvodoc 2.1 / Languages", "LanguageController"))
    .when("/dictionary/:dictionaryClientId/:dictionaryObjectId/perspective/:perspectiveClientId/:perspectiveObjectId/view/:page?/:sortBy?", Route("/static/templates/viewDictionary.html", "Lingvodoc 2.1 / View", "ViewDictionaryController"))
    .when("/dictionary/:dictionaryClientId/:dictionaryObjectId/perspective/:perspectiveClientId/:perspectiveObjectId/edit/:page?/:sortBy?", Route("/static/templates/editDictionary.html", "Lingvodoc 2.1 / Edit", "EditDictionaryController"))
    .when("/dictionary/:dictionaryClientId/:dictionaryObjectId/perspective/:perspectiveClientId/:perspectiveObjectId/publish/:page?/:sortBy?", Route("/static/templates/publishDictionary.html", "Lingvodoc 2.1 / Publish", "PublishDictionaryController"))
    .when("/dictionary/:dictionaryClientId/:dictionaryObjectId/perspective/:perspectiveClientId/:perspectiveObjectId/contributions/:page?/:sortBy?", Route("/static/templates/contributions.html", "Lingvodoc 2.1 / Contributions", "ContributionsController"))

    .when("/dictionary/:dictionaryClientId/:dictionaryObjectId" +
      "/perspective/:perspectiveClientId/:perspectiveObjectId/merge",
      Route("/static/templates/mergeDictionary.html", "Lingvodoc 2.1 / Merge suggestions", "MergeDictionaryController"))

    .when("/dictionary/create", Route("/static/templates/createDictionary.html", "Lingvodoc 2.1 / Create dictionary", "CreateDictionaryController"))
    .when("/corpora/create", Route("/static/templates/createCorpus.html", "Lingvodoc 2.1 / Create corpus", "CreateCorpusController"))
    .when("/files", Route("/static/templates/files.html", "Lingvodoc 2.1 / Files", "UserFilesController"))
    .when("/map_search", Route("/static/templates/mapSearch.html", "Lingvodoc 2.1 / Map search", "MapSearchController"))
    .when("/sociolinguistics", Route("/static/templates/sociolinguistics.html", "Lingvodoc 2.1 / Sociolinguistics", "SociolinguisticsController"))
    .when("/desktop_software", Route("/static/templates/desktop.html", "Lingvodoc 2.1 / Desktop software"))
    .when("/edit_translations", Route("/static/templates/editTranslations.html", "Lingvodoc 2.1 / Edit translations", "EditTranslationsController"))
    .when("/grants_admin", Route("/static/templates/grants.html", "Lingvodoc 2.1 / Grants", "GrantsController"))
    .when("/grants", Route("/static/templates/grantsPublic.html", "Lingvodoc 2.1 / Grants", "GrantsPublicController"))
    .when("/user_requests", Route("/static/templates/userRequests.html", "Lingvodoc 2.1 / User requests", "UserRequestsController"))
    .when("/organizations", Route("/static/templates/organizations.html", "Lingvodoc 2.1 / Organizations", "OrganizationsController"))
    .otherwise(Route("/static/templates/404.html"))
}


@JSExport
object ProxyApplication {

  @JSExport
  def main(): Unit = {

    Angular.module("ProxyApplication", Seq("ngRoute", "ngSanitize", "ngAnimate", "ui.bootstrap"))
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
      .controller[proxy.HomeController]
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
      .controller[PublishLinkedDictionaryModalController]
      .controller[UserFilesController]
      .controller[MapSearchController]
      .controller[ViewInfoBlobsController]
      .controller[EditGroupingTagModalController]
      .controller[ContributionsController]
      .controller[ContributionsLinkedDictionaryModalController]
      .controller[ContributionsGroupingTagModalController]
      .controller[CorporaController]
      .controller[SociolinguisticsController]
      .controller[ViewSociolinguisticsInfoController]
      .controller[ConvertEafController]
      .controller[DownloadEmbeddedBlobController]
      .controller[MessageController]
      .controller[EditTranslationsController]
      .controller[UserProfileController]
      .controller[PerspectiveStatisticsModalController]
      .controller[DictionaryStatisticsModalController]
      .controller[PerspectivePhonologyModalController]
      .controller[GrantsController]
      .controller[GrantsPublicController]
      .controller[UserRequestsController]
      .controller[CreateGrantModalController]
      .controller[AddDictionaryToGrantModalController]
      .controller[OrganizationsController]
      .controller[CreateOrganizationModalController]
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
