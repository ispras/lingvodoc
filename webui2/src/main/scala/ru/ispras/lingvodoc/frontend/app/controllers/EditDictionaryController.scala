package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{Event, RouteParams, Scope}
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, LexicalEntriesType, ModalOptions, ModalService}
import com.greencatsoft.angularjs.{AbstractController, injectable}
import org.scalajs.dom.console
import org.scalajs.dom.raw.HTMLInputElement
import org.singlespaced.d3js.d3
import ru.ispras.lingvodoc.frontend.app.controllers.common._
import ru.ispras.lingvodoc.frontend.app.exceptions.ControllerException
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.utils.LingvodocExecutionContext.Implicits.executionContext

import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}
import ru.ispras.lingvodoc.frontend.app.utils.Utils
import ru.ispras.lingvodoc.frontend.extras.facades.{WaveSurfer, WaveSurferOpts}

import scala.scalajs.js.UndefOr



@js.native
trait EditDictionaryScope extends Scope {
  var filter: Boolean = js.native
  var path: String = js.native
  var count: Int = js.native
  var offset: Int = js.native
  var size: Int = js.native

  var pageCount: Int = js.native
  var dictionaryTable: DictionaryTable = js.native
  var selectedEntries: js.Array[String] = js.native

}

@JSExport
@injectable("EditDictionaryController")
class EditDictionaryController(scope: EditDictionaryScope, params: RouteParams, modal: ModalService, backend: BackendService) extends
AbstractController[EditDictionaryScope](scope) {

  private[this] val dictionaryClientId = params.get("dictionaryClientId").get.toString.toInt
  private[this] val dictionaryObjectId = params.get("dictionaryObjectId").get.toString.toInt
  private[this] val perspectiveClientId = params.get("perspectiveClientId").get.toString.toInt
  private[this] val perspectiveObjectId = params.get("perspectiveObjectId").get.toString.toInt

  private[this] val dictionary = Dictionary.emptyDictionary(dictionaryClientId, dictionaryObjectId)
  private[this] val perspective = Perspective.emptyPerspective(perspectiveClientId, perspectiveObjectId)

  private[this] var enabledInputs: Seq[String] = Seq[String]()

  private[this] var createdLexicalEntries: Seq[LexicalEntry] = Seq[LexicalEntry]()

  private[this] var dataTypes: Seq[TranslationGist] = Seq[TranslationGist]()
  private[this] var fields: Seq[Field] = Seq[Field]()

  private [this] var waveSurfer: Option[WaveSurfer] = None
  private var _pxPerSec = 50 // minimum pxls per second, all timing is bounded to it
  val pxPerSecStep = 30 // zooming step
  // zoom in/out step; fake value to avoid division by zero; on ws load, it will be set correctly
  private var _duration: Double = 42.0
  var fullWSWidth = 0.0 // again, will be known after audio load
  var wsHeight = 128
  var soundMarkup: Option[String] = None


  scope.filter = true
  //scope.count = 0
  scope.offset = 0
  scope.size = 5
  scope.pageCount = 0

  scope.selectedEntries = js.Array[String]()

  load()


  @JSExport
  def filterKeypress(event: Event) = {
    val e = event.asInstanceOf[org.scalajs.dom.raw.KeyboardEvent]
    if (e.keyCode == 13) {
      val query = e.target.asInstanceOf[HTMLInputElement].value
      loadSearch(query)
    }
  }


  @JSExport
  def loadPage(page: Int) = {
    val offset = (page - 1) * scope.size
    backend.getLexicalEntries(CompositeId.fromObject(dictionary), CompositeId.fromObject(perspective), LexicalEntriesType.All, offset, scope.size) onComplete {
      case Success(entries) =>
        scope.offset = offset
        scope.dictionaryTable = DictionaryTable.build(fields, dataTypes, entries)
      case Failure(e) => console.log(e.getMessage)
    }
  }

  @JSExport
  def loadSearch(query: String) = {
    backend.search(query, Some(CompositeId(perspectiveClientId, perspectiveObjectId)), tagsOnly = false) map {
      results =>
        console.log(results.toJSArray)
        val entries = results map(_.lexicalEntry)
        scope.dictionaryTable = DictionaryTable.build(fields, dataTypes, entries)
    }
  }

  @JSExport
  def range(min: Int, max: Int, step: Int) = {
    (min to max by step).toSeq.toJSArray
  }


  @JSExport
  def createWaveSurfer(): Unit = {
    if (waveSurfer.isEmpty) {
      // params should be synchronized with sm-ruler css
      val wso = WaveSurferOpts("#waveform", waveColor = "violet", progressColor = "purple",
        cursorWidth = 1, cursorColor = "red",
        fillParent = true, minPxPerSec = pxPerSec, scrollParent = false,
        height = wsHeight)
      waveSurfer = Some(WaveSurfer.create(wso))
    }
  }

  def pxPerSec = _pxPerSec

  def pxPerSec_=(mpps: Int) = {
    _pxPerSec = mpps
    waveSurfer.foreach(_.zoom(mpps))
  }

  @JSExport
  def play(soundAddress: String) = {
    (waveSurfer, Some(soundAddress)).zipped.foreach((ws, sa) => {
      ws.load(sa)
    })
  }

  @JSExport
  def playPause() = waveSurfer.foreach(_.playPause())

  @JSExport
  def play(start: Int, end: Int) = waveSurfer.foreach(_.play(start, end))

  @JSExport
  def zoomIn() = { pxPerSec += pxPerSecStep; }

  @JSExport
  def zoomOut() = { pxPerSec -= pxPerSecStep; }


  @JSExport
  def viewSoundMarkup(soundAddress: String, markupAddress: String) = {
    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/soundMarkup.html"; options.windowClass ="sm-modal-window"
    options.controller = "SoundMarkupController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          soundAddress = soundAddress.asInstanceOf[js.Object],
          markupAddress = markupAddress.asInstanceOf[js.Object],
          dictionaryClientId = dictionaryClientId.asInstanceOf[js.Object],
          dictionaryObjectId = dictionaryObjectId.asInstanceOf[js.Object]
        )
      }
    ).asInstanceOf[js.Dictionary[js.Any]]

    val instance = modal.open[Unit](options)
  }

  @JSExport
  def viewPraatSoundMarkup(soundValue: Value, markupValue: Value) = {

    val soundAddress = soundValue.getContent()

    backend.convertPraatMarkup(CompositeId.fromObject(markupValue.getEntity())) onComplete {
      case Success(elan) =>
        val options = ModalOptions()
        options.templateUrl = "/static/templates/modal/soundMarkup.html"; options.windowClass ="sm-modal-window"
        options.controller = "SoundMarkupController"
        options.backdrop = false
        options.keyboard = false
        options.size = "lg"
        options.resolve = js.Dynamic.literal(
          params = () => {
            js.Dynamic.literal(
              soundAddress = soundAddress.asInstanceOf[js.Object],
              markupData = elan.asInstanceOf[js.Object],
              dictionaryClientId = dictionaryClientId.asInstanceOf[js.Object],
              dictionaryObjectId = dictionaryObjectId.asInstanceOf[js.Object]
            )
          }
        ).asInstanceOf[js.Dictionary[js.Any]]
        val instance = modal.open[Unit](options)
      case Failure(e) =>
    }
  }



  @JSExport
  def toggleSelectedEntries(id: String) = {
    if (scope.selectedEntries.contains(id)) {
      scope.selectedEntries = scope.selectedEntries.filterNot(_ == id)
    } else {
      scope.selectedEntries.push(id)
    }
  }

  @JSExport
  def mergeEntries() = {
    val entries = scope.selectedEntries.flatMap {
      id => scope.dictionaryTable.rows.find(_.entry.getId == id) map(_.entry)
    }
  }

  @JSExport
  def addNewLexicalEntry() = {
    backend.createLexicalEntry(CompositeId.fromObject(dictionary), CompositeId.fromObject(perspective)) onComplete {
      case Success(entryId) =>
        backend.getLexicalEntry(CompositeId.fromObject(dictionary), CompositeId.fromObject(perspective), entryId) onComplete {
          case Success(entry) =>
            scope.dictionaryTable.addEntry(entry)
            createdLexicalEntries = createdLexicalEntries :+ entry
          case Failure(e) =>
        }
      case Failure(e) => throw ControllerException("Attempt to create a new lexical entry failed", e)
    }
  }

  @JSExport
  def createdByUser(lexicalEntry: LexicalEntry): Boolean = {
    createdLexicalEntries.contains(lexicalEntry)
  }

  @JSExport
  def removeEntry(lexicalEntry: LexicalEntry) = {
    lexicalEntry.markedForDeletion = true
  }

  @JSExport
  def removeEntity(lexicalEntry: LexicalEntry, entity: Entity) = {
    backend.removeEntity(CompositeId.fromObject(dictionary), CompositeId.fromObject(perspective), CompositeId.fromObject(lexicalEntry), CompositeId.fromObject(entity))
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
  def enableInput(id: String) = {
    if (!isInputEnabled(id)) {
      enabledInputs = enabledInputs :+ id
    }
  }

  @JSExport
  def disableInput(id: String) = {
    if (isInputEnabled(id)) {
      enabledInputs = enabledInputs.filterNot(_.equals(id))
    }
  }

  @JSExport
  def isInputEnabled(id: String): Boolean = {
    enabledInputs.contains(id)
  }

  @JSExport
    def saveTextValue(inputId: String, entry: LexicalEntry, field: Field, event: Event, parent: UndefOr[Value]) = {

    val e = event.asInstanceOf[org.scalajs.dom.raw.Event]
    val textValue = e.target.asInstanceOf[HTMLInputElement].value

    val dictionaryId = CompositeId.fromObject(dictionary)
    val perspectiveId = CompositeId.fromObject(perspective)
    val entryId = CompositeId.fromObject(entry)

    val entity = EntityData(field.clientId, field.objectId, Utils.getLocale().getOrElse(2))
    entity.content = Some(Left(textValue))

    // self
    parent map {
      parentValue =>
        entity.selfClientId = Some(parentValue.getEntity.clientId)
        entity.selfObjectId = Some(parentValue.getEntity.objectId)
    }

    backend.createEntity(dictionaryId, perspectiveId, entryId, entity) onComplete {
      case Success(entityId) =>
        backend.getEntity(dictionaryId, perspectiveId, entryId, entityId) onComplete {
          case Success(newEntity) =>

            parent.toOption match {
              case Some(x) => scope.dictionaryTable.addEntity(x, newEntity)
              case None => scope.dictionaryTable.addEntity(entry, newEntity)
            }

            disableInput(inputId)

          case Failure(ex) => console.log(ex.getMessage)
        }
      case Failure(ex) => console.log(ex.getMessage)
    }
  }

  @JSExport
  def saveFileValue(inputId: String, entry: LexicalEntry, field: Field, fileName: String, fileType: String, fileContent: String, parent: UndefOr[Value]) = {


    val dictionaryId = CompositeId.fromObject(dictionary)
    val perspectiveId = CompositeId.fromObject(perspective)
    val entryId = CompositeId.fromObject(entry)

    val entity = EntityData(field.clientId, field.objectId, Utils.getLocale().getOrElse(2))
    entity.content = Some(Right(FileContent(fileName, fileType, fileContent)))

    // self
    parent map {
      parentValue =>
        entity.selfClientId = Some(parentValue.getEntity.clientId)
        entity.selfObjectId = Some(parentValue.getEntity.objectId)
    }

    backend.createEntity(dictionaryId, perspectiveId, entryId, entity) onComplete {
      case Success(entityId) =>
        backend.getEntity(dictionaryId, perspectiveId, entryId, entityId) onComplete {
          case Success(newEntity) =>

            parent.toOption match {
              case Some(x) => scope.dictionaryTable.addEntity(x, newEntity)
              case None => scope.dictionaryTable.addEntity(entry, newEntity)
            }

            disableInput(inputId)

          case Failure(ex) => console.log(ex.getMessage)
        }
      case Failure(ex) => console.log(ex.getMessage)
    }

  }

  @JSExport
  def editLinkedPerspective(entry: LexicalEntry, field: Field, values: js.Array[Value]) = {

    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/editLinkedDictionary.html"
    options.controller = "EditDictionaryModalController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          dictionaryClientId = dictionaryClientId.asInstanceOf[js.Object],
          dictionaryObjectId = dictionaryObjectId.asInstanceOf[js.Object],
          perspectiveClientId = perspectiveClientId,
          perspectiveObjectId = perspectiveObjectId,
          linkPerspectiveClientId = field.link.get.clientId,
          linkPerspectiveObjectId = field.link.get.objectId,
          lexicalEntry = entry.asInstanceOf[js.Object],
          field = field.asInstanceOf[js.Object],
          links = values.map { _.asInstanceOf[GroupValue].link }
        )
      }
    ).asInstanceOf[js.Dictionary[js.Any]]

    val instance = modal.open[Seq[Entity]](options)
    instance.result map { entities =>
      entities.foreach(e => scope.dictionaryTable.addEntity(entry, e))
    }
  }


  private[this] def load() = {

    backend.perspectiveSource(CompositeId.fromObject(perspective)) onComplete {
      case Success(sources) =>
        scope.path = sources.reverse.map { _.source match {
          case language: Language => language.translation
          case dictionary: Dictionary => dictionary.translation
          case perspective: Perspective => perspective.translation
        }}.mkString(" >> ")
      case Failure(e) => console.error(e.getMessage)
    }


    backend.dataTypes() onComplete {
      case Success(d) =>
        dataTypes = d
        backend.getFields(CompositeId.fromObject(dictionary), CompositeId.fromObject(perspective)) onComplete {
          case Success(f) =>
            fields = f
            backend.getLexicalEntriesCount(CompositeId.fromObject(dictionary), CompositeId.fromObject(perspective)) onComplete {
              case Success(count) =>
                //scope.count = count
                scope.pageCount = scala.math.ceil(count.toDouble / scope.size).toInt


                backend.getLexicalEntries(CompositeId.fromObject(dictionary), CompositeId.fromObject(perspective), LexicalEntriesType.All, scope.offset, scope.size) onComplete {
                  case Success(entries) =>
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
