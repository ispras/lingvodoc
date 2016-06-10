package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{RouteParams, Scope}
import com.greencatsoft.angularjs.extensions.ModalInstance
import com.greencatsoft.angularjs.{AbstractController, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, LexicalEntriesType}
import ru.ispras.lingvodoc.frontend.app.utils
import ru.ispras.lingvodoc.frontend.app.controllers.common._

import scala.scalajs.concurrent.JSExecutionContext.Implicits.runNow
import scala.scalajs.js
import scala.scalajs.js.Array
import scala.scalajs.js.annotation.{JSExport, JSExportAll}
import scala.scalajs.js.JSConverters._
import scala.util.{Failure, Success}


@js.native
trait ViewDictionaryScope extends Scope {
  var dictionaryClientId: Int = js.native
  var dictionaryObjectId: Int = js.native
  var perspectiveClientId: Int = js.native
  var perspectiveObjectId: Int = js.native
  var count: Int = js.native
  var offset: Int = js.native
  var size: Int = js.native
  var dictionaryTable: DictionaryTable = js.native
}

@injectable("ViewDictionaryController")
class ViewDictionaryController(scope: ViewDictionaryScope, params: RouteParams, backend: BackendService) extends AbstractController[ViewDictionaryScope](scope) {

  scope.dictionaryClientId = params.get("dictionaryClientId").get.toString.toInt
  scope.dictionaryObjectId = params.get("dictionaryObjectId").get.toString.toInt
  scope.perspectiveClientId = params.get("perspectiveClientId").get.toString.toInt
  scope.perspectiveObjectId = params.get("perspectiveObjectId").get.toString.toInt

  scope.count = 0
  scope.offset = 0
  scope.size = 20



  @JSExport
  def viewGroup(column: GroupColumn, content: GroupContent) = {
    console.log((column :: Nil).toJSArray)
    console.log((content :: Nil).toJSArray)
  }

  @JSExport
  def viewMarkup() = {

  }

  @JSExport
  def playSound() = {

  }


  val dictionary = Dictionary.emptyDictionary(scope.dictionaryClientId, scope.dictionaryObjectId)
  val perspective = Perspective.emptyPerspective(scope.perspectiveClientId, scope.perspectiveObjectId)

  backend.getPublishedLexicalEntriesCount(dictionary, perspective) onComplete {
    case Success(count) =>
      scope.count = count

      backend.getFields(dictionary, perspective) onComplete {
        case Success(fields) =>

          backend.getLexicalEntries(dictionary, perspective, LexicalEntriesType.Published, scope.offset, scope.size) onComplete {
            case Success(entries) =>
              scope.dictionaryTable = DictionaryTable(fields, entries)
              console.log(entries.toJSArray)


            case Failure(e) => console.log(e.getMessage)
          }
        case Failure(e) =>
      }
    case Failure(e) => console.log(e.getMessage)
  }
}