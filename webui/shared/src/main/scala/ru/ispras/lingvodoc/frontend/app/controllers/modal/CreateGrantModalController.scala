package ru.ispras.lingvodoc.frontend.app.controllers.modal

import com.greencatsoft.angularjs.AngularExecutionContextProvider
import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.{ModalInstance, ModalService}
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseModalController
import ru.ispras.lingvodoc.frontend.app.controllers.traits.LanguageEdit
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.BackendService

import scala.scalajs.js
import scala.scalajs.js.UndefOr
import com.greencatsoft.angularjs.core.{Event, ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.{ModalInstance, ModalService}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseModalController
import ru.ispras.lingvodoc.frontend.app.controllers.traits.{LanguageEdit, LoadingPlaceholder}
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.UndefOr
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}



@js.native
trait CreateGrantModalScope extends Scope {
  var locales: js.Array[Locale] = js.native
  var searchString: String = js.native
  var grantTranslations: js.Array[LocalizedString] = js.native
  var issuerTranslations: js.Array[LocalizedString] = js.native
  var issuerUrl: String = js.native
  var grantUrl: String = js.native
  var grantNumber: String = js.native
  var begin: String = js.native
  var end: String = js.native
  var users: js.Array[UserListEntry] = js.native
  var searchUsers: js.Array[UserListEntry] = js.native

}

@injectable("CreateGrantModalController")
class CreateGrantModalController(scope: CreateGrantModalScope,
                                 val modal: ModalService,
                                 instance: ModalInstance[Grant],
                                 backend: BackendService,
                                 timeout: Timeout,
                                 val exceptionHandler: ExceptionHandler,
                                 params: js.Dictionary[js.Function0[js.Any]])
  extends BaseModalController[CreateGrantModalScope, Grant](scope, modal, instance, timeout, params)
    with AngularExecutionContextProvider {


  scope.locales = js.Array[Locale]()
  scope.searchString = ""
  scope.grantTranslations = (LocalizedString(Utils.getLocale().getOrElse(2), "") :: Nil).toJSArray
  scope.issuerTranslations = (LocalizedString(Utils.getLocale().getOrElse(2), "") :: Nil).toJSArray
  scope.issuerUrl = ""
  scope.grantUrl = ""
  scope.grantNumber = ""
  scope.begin = ""
  scope.end = ""
  scope.users = js.Array[UserListEntry]()

  private[this] var allUsers = Seq[UserListEntry]()



  private[this] def createGrant(): Future[Unit] = {

    backend.createTranslationGist("Grant") flatMap { translationGistId =>

      val grantAtomRequests = scope.grantTranslations.toSeq map { translation =>
        backend.createTranslationAtom(translationGistId, translation)
      }

      Future.sequence(grantAtomRequests) flatMap { _ =>

        backend.createTranslationGist("Grant") flatMap { issuerGistId =>

          val issuerAtomRequests = scope.issuerTranslations.toSeq map { translation =>
            backend.createTranslationAtom(issuerGistId, translation)
          }

          Future.sequence(issuerAtomRequests) flatMap { _ =>
            val users = scope.users.map(_.id).toSeq
            val grant = GrantRequest(issuerGistId, translationGistId, scope.issuerUrl, scope.grantUrl, scope.grantNumber, scope.begin, scope.end, users, Seq[String]())

            backend.createGrant(grant)
          }
        }
      }
    }
  }



  @JSExport
  def addGrantTranslation(): Unit = {
    val currentLocaleId = Utils.getLocale().getOrElse(2)
    if (scope.grantTranslations.exists(_.localeId == currentLocaleId)) {
      // pick next available locale
      scope.locales.filterNot(locale => scope.grantTranslations.exists(name => name.localeId == locale.id)).toList match {
        case firstLocale :: otherLocales =>
          scope.grantTranslations = scope.grantTranslations :+ LocalizedString(firstLocale.id, "")
        case Nil =>
      }
    } else {
      // add translation with current locale pre-selected
      scope.grantTranslations = scope.grantTranslations :+ LocalizedString(currentLocaleId, "")
    }
  }

  @JSExport
  def addIssuerTranslation(): Unit = {
    val currentLocaleId = Utils.getLocale().getOrElse(2)
    if (scope.issuerTranslations.exists(_.localeId == currentLocaleId)) {
      // pick next available locale
      scope.locales.filterNot(locale => scope.issuerTranslations.exists(name => name.localeId == locale.id)).toList match {
        case firstLocale :: otherLocales =>
          scope.issuerTranslations = scope.issuerTranslations :+ LocalizedString(firstLocale.id, "")
        case Nil =>
      }
    } else {
      // add translation with current locale pre-selected
      scope.issuerTranslations = scope.issuerTranslations :+ LocalizedString(currentLocaleId, "")
    }
  }

  @JSExport
  def getAvailableLocales(translations: js.Array[LocalizedString], currentTranslation: LocalizedString): js.Array[Locale] = {
    scope.locales.find(_.id == currentTranslation.localeId) match {
      case Some(currentLocale) =>
        val otherTranslations = translations.filterNot(translation => translation.equals(currentTranslation))
        val availableLocales = scope.locales.filterNot(_.equals(currentLocale)).filter(locale => !otherTranslations.exists(translation => translation.localeId == locale.id)).toList
        (currentLocale :: availableLocales).toJSArray
      case None =>
        js.Array[Locale]()
    }
  }

  @JSExport
  def searchUser(): Unit = {
      scope.searchUsers = allUsers.filterNot(u => scope.users.exists(_.id == u.id))
        .filter(user => user.login.toLowerCase.contains(scope.searchString.toLowerCase) || user.intlName.toLowerCase.contains(scope.searchString.toLowerCase)).take(5).toJSArray
  }

  @JSExport
  def addUser(user: UserListEntry): Unit = {
    if (!scope.users.exists(_.id == user.id)) {
      scope.users.push(user)
    }
  }

  @JSExport
  def removeUser(user: UserListEntry): Unit = {
    scope.users = scope.users.filterNot(_.id == user.id)
  }

  @JSExport
  def save(): Unit = {
    createGrant() map { _ =>
      instance.dismiss(())
    }

  }

  @JSExport
  def cancel(): Unit = {
    instance.dismiss(())
  }

  load(() => {
    backend.getUsers flatMap { users =>
      allUsers = users
      backend.getLocales() map { locales =>
        scope.locales = locales.toJSArray
      }
    }
  })




  override protected def onStartRequest(): Unit = {}

  override protected def onCompleteRequest(): Unit = {}
}
