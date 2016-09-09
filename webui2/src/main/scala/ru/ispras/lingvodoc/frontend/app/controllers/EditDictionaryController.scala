package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{Event, RouteParams, Scope}
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, LexicalEntriesType, ModalOptions, ModalService}
import com.greencatsoft.angularjs.{AbstractController, injectable}
import org.scalajs.dom.console
import org.scalajs.dom.raw.HTMLInputElement
import ru.ispras.lingvodoc.frontend.app.controllers.common.DictionaryTable
import ru.ispras.lingvodoc.frontend.app.exceptions.ControllerException
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.utils.LingvodocExecutionContext.Implicits.executionContext

import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.URIUtils.encodeURIComponent
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}
import ru.ispras.lingvodoc.frontend.app.utils.Utils


@js.native
trait EditDictionaryScope extends Scope {

  var dictionaryClientId: Int = js.native
  var dictionaryObjectId: Int = js.native
  var perspectiveClientId: Int = js.native
  var perspectiveObjectId: Int = js.native



  var count: Int = js.native
  var offset: Int = js.native
  var size: Int = js.native
  var dictionaryTable: DictionaryTable = js.native

  var filter: String = js.native

  var enabledInputs: js.Array[Any] = js.native

}

@JSExport
@injectable("EditDictionaryController")
class EditDictionaryController(scope: EditDictionaryScope, params: RouteParams, modal: ModalService, backend: BackendService) extends
AbstractController[EditDictionaryScope](scope) {

  scope.dictionaryClientId = params.get("dictionaryClientId").get.toString.toInt
  scope.dictionaryObjectId = params.get("dictionaryObjectId").get.toString.toInt
  scope.perspectiveClientId = params.get("perspectiveClientId").get.toString.toInt
  scope.perspectiveObjectId = params.get("perspectiveObjectId").get.toString.toInt

  scope.count = 0
  scope.offset = 0
  scope.size = 20

  val dictionary = Dictionary.emptyDictionary(scope.dictionaryClientId, scope.dictionaryObjectId)
  val perspective = Perspective.emptyPerspective(scope.perspectiveClientId, scope.perspectiveObjectId)

  var enabledInputs: Seq[(Int, Int)] = Seq[(Int, Int)]()


  load()

  @JSExport
  def play(soundAddress: String, soundMarkupAddress: String) = {
    console.log(s"playing $soundAddress with markup $soundMarkupAddress")
  }

  @JSExport
  def viewSoundMarkup(soundAddress: String, soundMarkupAddress: String) = {
    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/soundMarkup.html"
    options.controller = "SoundMarkupController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          soundAddress = soundAddress.asInstanceOf[js.Object],
          dictionaryClientId = scope.dictionaryClientId.asInstanceOf[js.Object],
          dictionaryObjectId = scope.dictionaryObjectId.asInstanceOf[js.Object]
        )
      }
    ).asInstanceOf[js.Dictionary[js.Any]]

    val instance = modal.open[Unit](options)
  }

  @JSExport
  def addNewLexicalEntry() = {
    backend.createLexicalEntry(CompositeId.fromObject(dictionary), CompositeId.fromObject(perspective)) onComplete {
      case Success(entryId) =>
        backend.getLexicalEntry(CompositeId.fromObject(dictionary), CompositeId.fromObject(perspective), entryId) onComplete {
          case Success(entry) =>
            scope.dictionaryTable.addEntry(entry)
          case Failure(e) =>
        }
      case Failure(e) => throw ControllerException("Attempt to create a new lexical entry failed", e)
    }
  }

  @JSExport
  def dataTypeString(dataType: TranslationGist): String = {
    dataType.atoms.find(a => a.localeId == 2) match {
      case Some(atom) =>
        atom.content
      case None => throw new ControllerException("")
    }
  }

  @JSExport
  def enableInput(id1: Int, id2: Int) = {
    if (!isInputEnabled(id1, id2))
      enabledInputs = enabledInputs :+ (id1, id2)
  }

  @JSExport
  def isInputEnabled(id1: Int, id2: Int): Boolean = {
    enabledInputs.exists(input => input._1 == id1 && input._2 == id2)
  }

  @JSExport
  def saveTextValue(entry: LexicalEntry, field: Field, event: Event) = {
    val e = event.asInstanceOf[org.scalajs.dom.raw.Event]
    val textValue = e.target.asInstanceOf[HTMLInputElement].value
    val entity = EntityData(field.clientId, field.objectId, Utils.getLocale().getOrElse(2), textValue)
    backend.createEntity(CompositeId.fromObject(dictionary), CompositeId.fromObject(perspective), CompositeId.fromObject(entry), entity) onComplete {
      case Success(entityId) => console.log("created!")
      case Failure(ex) =>console.log(ex.getMessage)
    }
  }


  private[this] def load() = {

    backend.dataTypes() onComplete {
      case Success(dataTypes) =>
        backend.getFields(dictionary, perspective) onComplete {
          case Success(fields) =>
            backend.getLexicalEntriesCount(CompositeId.fromObject(dictionary), CompositeId.fromObject(perspective)) onComplete {
              case Success(count) =>
                scope.count = count
                backend.getLexicalEntries(dictionary, perspective, LexicalEntriesType.All, scope.offset, scope.size) onComplete {
                  case Success(entries) =>
                    //console.log(entries.toJSArray)
                    //val entries1 = Seq[LexicalEntry]()
                    scope.dictionaryTable = DictionaryTable.build(fields, dataTypes, entries)
                  case Failure(e) => console.log(e.getMessage)
                }
              case Failure(e) => console.log(e.getMessage)
            }
          case Failure(e) => console.log(e.getMessage)
        }
      case Failure(e) => console.log(e.getMessage)
    }
  }


}
