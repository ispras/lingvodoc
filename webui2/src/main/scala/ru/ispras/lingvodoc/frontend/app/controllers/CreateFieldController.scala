package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.{AbstractController, injectable}
import com.greencatsoft.angularjs.core.Scope
import ru.ispras.lingvodoc.frontend.app.controllers.common.{FieldEntry, Translatable}
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, ModalInstance}
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.scalajs.js.JSConverters._
import org.scalajs.dom.console

import scala.scalajs.js
import scala.scalajs.js.Array
import scala.scalajs.js.annotation.JSExport

@js.native
trait CreateFieldScope extends Scope {
  var locales: js.Array[Locale] = js.native
  var fieldEntry: FieldEntry = js.native
  var dataType: String = js.native
  var dataTypes: js.Array[TranslationGist] = js.native
  var translatable: Boolean = js.native
  var dataTypeNames: js.Array[String] = js.native
}

@injectable("CreateFieldController")
class CreateFieldController(scope: CreateFieldScope,
                            instance: ModalInstance[FieldEntry],
                            backend: BackendService,
                            params: js.Dictionary[js.Function0[js.Any]])
  extends AbstractController[CreateFieldScope](scope) {


  scope.locales = params("locales").asInstanceOf[js.Array[Locale]]
  scope.fieldEntry = params("entry").asInstanceOf[FieldEntry]
  scope.dataTypes = params("dataTypes").asInstanceOf[js.Array[TranslationGist]]
  scope.dataTypeNames = dataTypesNames()


  @JSExport
  def getAvailableLocales(translations: js.Array[LocalizedString], currentTranslation: LocalizedString): js.Array[Locale] = {
    val currentLocale = scope.locales.find(_.id == currentTranslation.localeId).get
    val otherTranslations = translations.filterNot(translation => translation.equals(currentTranslation))
    val availableLocales = scope.locales.filterNot(_.equals(currentLocale)).filter(locale => !otherTranslations.exists(translation => translation.localeId == locale.id)).toList
    (currentLocale :: availableLocales).toJSArray
  }

  @JSExport
  def addNameTranslation[T <: Translatable](obj: T) = {
    val currentLocaleId = Utils.getLocale().getOrElse(2)
    if (obj.names.exists(_.localeId == currentLocaleId)) {
      // pick next available locale
      scope.locales.filterNot(locale => obj.names.exists(name => name.localeId == locale.id)).toList match {
        case firstLocale :: otherLocales =>
          obj.names = obj.names :+ LocalizedString(firstLocale.id, "")
        case Nil =>
      }
    } else {
      // add translation with current locale pre-selected
      obj.names = obj.names :+ LocalizedString(currentLocaleId, "")
    }
  }

  private[this] def dataTypesNames(): Array[String] = {
    val currentLocaleId = Utils.getLocale().getOrElse(2)
    scope.dataTypes.flatMap {
      dataType =>
        dataType.atoms.find(_.localeId == currentLocaleId)
    }.map {
      atom => atom.content
    }
  }

  private[this] def getDataTypeTranslationGist(dataTypeName: String): Option[TranslationGist] = {
    val currentLocaleId = Utils.getLocale().getOrElse(2)
    scope.dataTypes.find {
      dataType =>
        dataType.atoms.exists(atom => atom.localeId == currentLocaleId && atom.content == dataTypeName)
    }
  }


  @JSExport
  def ok() = {
    // remove empty strings
    scope.fieldEntry.names = scope.fieldEntry.names.filterNot(_.str.trim.isEmpty)

    // get translation gist
    val gist = getDataTypeTranslationGist(scope.dataType)
    scope.fieldEntry.dataType = gist

    //
    if (scope.fieldEntry.names.nonEmpty && scope.fieldEntry.dataType.nonEmpty) {
      instance.close(scope.fieldEntry)
    }
  }

  @JSExport
  def cancel() = {
    instance.dismiss(())
  }
}
