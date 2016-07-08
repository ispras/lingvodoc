package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.Scope
import ru.ispras.lingvodoc.frontend.app.services.{ModalOptions, ModalService}
import com.greencatsoft.angularjs.{AbstractController, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.BackendService

import scala.scalajs.concurrent.JSExecutionContext.Implicits.runNow
import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.URIUtils.encodeURIComponent
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}
import ru.ispras.lingvodoc.frontend.app.utils.Utils


@js.native
trait EditDictionaryScope extends Scope {

  var dictionary: Dictionary = js.native
  var perspective: Perspective = js.native
  var fields: js.Array[FieldWrapper] = js.native
  var entries: js.Array[LexicalEntry] = js.native

  var pageIndex: Int = js.native
  var pageSize: Int = js.native
  var pageCount: Int = js.native

  var filter: String = js.native

  var enabledInputs: js.Array[Any] = js.native


}

@JSExport
@injectable("EditDictionaryController")
class EditDictionaryController(scope: EditDictionaryScope, modal: ModalService, backend: BackendService) extends
AbstractController[EditDictionaryScope](scope) {

/*
        WaveSurferController.call(this, $scope);

        $scope.perspectiveFields = [];
        $scope.lexicalEntries = [];


        $scope.fields = [];
        $scope.dictionaryTable = [];

        // pagination
        $scope.pageIndex = 1;
        $scope.pageSize = 20;
        $scope.pageCount = 1;

        $scope.filterQuery = '';
        $scope.filterEntries = [];
        $scope.originalEntries = [];

        $scope.selectedEntries = [];

        var enabledInputs = [];
 */

  val dictionaryClientId: Int = Utils.getData("dictionaryClientId").get.toInt
  val dictionaryObjectId: Int = Utils.getData("dictionaryObjectId").get.toInt
  val perspectiveClientId = Utils.getData("perspectiveClientId").get.toInt
  val perspectiveObjectId = Utils.getData("perspectiveObjectId").get.toInt





  def getPage() = {
    scope.pageCount
  }




  // load dictionary
  backend.getDictionary(dictionaryClientId, dictionaryObjectId) onComplete {
    case Success(dictionary) =>
      scope.dictionary = dictionary

      // load perspective
      backend.getPerspective(perspectiveClientId, perspectiveObjectId) onComplete {
        case Success(perspective) =>

          // load perspective fields
          backend.getPerspectiveFields(dictionary, perspective) onComplete {
            case Success(perspectiveWithFields) =>
              scope.perspective = perspectiveWithFields

              // load page count
              //backend.getLexicalEntries(dictionary, perspective, "", 0, 0)



            case Failure(e) => console.error(e.getMessage)
          }
        case Failure(e) => console.error(e.getMessage)
      }
    case Failure(e) => console.error(e.getMessage)
  }

}
