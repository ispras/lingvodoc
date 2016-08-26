package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.{AbstractController, injectable}
import com.greencatsoft.angularjs.core.Scope
import ru.ispras.lingvodoc.frontend.app.controllers.common.{FieldType, Translatable}
import ru.ispras.lingvodoc.frontend.app.model.{Dictionary, Locale, LocalizedString, Perspective}
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, ModalInstance}
import ru.ispras.lingvodoc.frontend.app.utils.Utils
import scala.scalajs.js.JSConverters._
import org.scalajs.dom.console


import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport

@js.native
trait CreateFieldTypeScope extends Scope {
  var locales: js.Array[Locale] = js.native
  var fieldType: FieldType = js.native

}

@injectable("CreateFieldTypeController")
class CreateFieldTypeController(scope: CreateFieldTypeScope,
                                instance: ModalInstance[FieldType],
                                backend: BackendService,
                                params: js.Dictionary[js.Function0[js.Any]])
  extends AbstractController[CreateFieldTypeScope](scope) {


  scope.locales = params("locales").asInstanceOf[js.Array[Locale]]
  scope.fieldType = FieldType(js.Array[LocalizedString](LocalizedString(Utils.getLocale().getOrElse(2), "")))

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

  @JSExport
  def ok() = {
    // remove empty strings
    scope.fieldType.names = scope.fieldType.names.filterNot(_.str.trim.isEmpty)
    instance.close(scope.fieldType)
  }

  @JSExport
  def cancel() = {
    instance.dismiss(())
  }
}
