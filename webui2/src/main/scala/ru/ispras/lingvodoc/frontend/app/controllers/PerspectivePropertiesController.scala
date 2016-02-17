package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.Scope
import com.greencatsoft.angularjs.extensions.ModalInstance
import com.greencatsoft.angularjs.{AbstractController, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.model.{Field, Perspective, Dictionary, Language}
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import ru.ispras.lingvodoc.frontend.app.utils

import scala.concurrent.{Promise, Future}
import scala.scalajs.concurrent.JSExecutionContext.Implicits.runNow
import scala.scalajs.js
import scala.scalajs.js.Array
import scala.scalajs.js.annotation.{JSExportAll, JSExport}
import scala.scalajs.js.JSConverters._
import scala.util.{Failure, Success}

@js.native
trait PerspectivePropertiesScope extends Scope {
  var dictionary: Dictionary = js.native
  var perspective: Perspective = js.native
  var authors: String = js.native
  var fields: js.Array[FieldWrapper] = js.native
}

@JSExportAll
class FieldWrapper(val field: Field) {
  var groupEnabled = field.group match {
    case Some(group) => true
    case None => false
  }
  var statusEnabled = field.status == "enabled"
  var translatable = false
  var subfieldsEnabled = field.fields.toSeq.nonEmpty
}


@injectable("PerspectivePropertiesController")
class PerspectivePropertiesController(scope: PerspectivePropertiesScope,
                                      instance: ModalInstance[Perspective],
                                      backend: BackendService,
                                      params: js.Dictionary[js.Function0[js.Any]])
  extends AbstractController[PerspectivePropertiesScope](scope) {

  val d = params("dictionary").asInstanceOf[Dictionary]
  val p = params("perspective").asInstanceOf[Perspective]
  var backupPerspective: Perspective = null

  scope.dictionary = d


  @JSExport
  def addField() = {
    scope.fields.push(new FieldWrapper(new Field(-1, -1, "", "", "", "", "", 1, "", js.Array())))
  }

  @JSExport
  def removeField(index: Int) = {
    scope.fields = scope.fields.zipWithIndex.filter(_._2 != index).map(_._1)

  }

  @JSExport
  def enableGroup() = {

  }

  @JSExport
  def enableLinkedField() = {

  }

  @JSExport
  def ok() = {

//    var s = Seq[Perspective]()
//    s = s :+ scope.perspective
//    s = s :+ backupPerspective
//    console.log(s.toJSArray)

    var futures: Seq[Future[Any]] = Seq()

    // update perspective
    if (backupPerspective.isTemplate != scope.perspective.isTemplate ||
      backupPerspective.status != scope.perspective.status ||
      backupPerspective.translation != scope.perspective.translation ||
      backupPerspective.translationString != scope.perspective.translationString) {

      console.log("1")
      futures = futures :+ backend.updatePerspective(scope.dictionary, scope.perspective)
    }



    // check if fields were changed
    val originalFields = scope.perspective.fields.map(new FieldWrapper(_)).zipWithIndex
    var updateFields = false
    for ((fw, index) <- scope.fields.zipWithIndex) {
        originalFields.find(_._2 == index) match {
        case Some(e) =>
          val originalFW = e._1
          // compare field values
          if (originalFW.field.dataType != fw.field.dataType || originalFW.field.entityType != fw.field.entityType ||
            originalFW.field.dataTypeTranslation != fw.field.dataTypeTranslation || originalFW.field.group != fw.field.group ||
            originalFW.field.position != fw.field.position) {
            updateFields = true
          }
        case None => updateFields = true
      }
    }

    if (updateFields) {
      scope.perspective.fields = scope.fields.map(_.field)
      futures = futures :+ backend.updateFields(scope.dictionary, scope.perspective)
    }

    Future.sequence(futures) onComplete {
      case Success(a) => instance.dismiss(())
      case Failure(e) => console.log(e.getMessage)
    }
  }

  @JSExport
  def cancel() = {
    instance.dismiss(())
  }


  backend.getPerspectiveFields(d, p) onComplete {
    case Success(perspective) =>
      backupPerspective = perspective.copy()
      scope.perspective = perspective

      // wrap fields
      scope.fields = perspective.fields.toSeq.map {
        f => new FieldWrapper(f)
      }.toJSArray

    case Failure(e) =>
      console.log(e.getMessage)
  }
}
