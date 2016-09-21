package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{Event, Scope}
import com.greencatsoft.angularjs.{AbstractController, injectable}
import org.scalajs.dom._
import org.scalajs.dom.raw.HTMLInputElement
import ru.ispras.lingvodoc.frontend.app.controllers.common.{DictionaryTable, GroupValue, Value}
import ru.ispras.lingvodoc.frontend.app.exceptions.ControllerException
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services._
import ru.ispras.lingvodoc.frontend.app.utils.LingvodocExecutionContext.Implicits.executionContext
import ru.ispras.lingvodoc.frontend.app.utils.Utils
import ru.ispras.lingvodoc.frontend.extras.facades.{WaveSurfer, WaveSurferOpts}

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.UndefOr
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}


@js.native
trait EditDictionaryModalScope extends Scope {
  var path: String = js.native
  var linkedPath: String = js.native
  var dictionaryTable: DictionaryTable = js.native
  var linkedDictionaryTable: DictionaryTable = js.native
  var count: Int = js.native
  var offset: Int = js.native
  var size: Int = js.native
  var pageCount: Int = js.native
  var edit: Boolean = js.native
}

@injectable("EditDictionaryModalController")
class EditDictionaryModalController(scope: EditDictionaryModalScope,
                                    modal: ModalService,
                                    instance: ModalInstance[Seq[Entity]],
                                    backend: BackendService,
                                    params: js.Dictionary[js.Function0[js.Any]])
  extends AbstractController[EditDictionaryModalScope](scope) {

  private[this] val dictionaryClientId = params("dictionaryClientId").asInstanceOf[Int]
  private[this] val dictionaryObjectId = params("dictionaryObjectId").asInstanceOf[Int]
  private[this] val perspectiveClientId = params("perspectiveClientId").asInstanceOf[Int]
  private[this] val perspectiveObjectId = params("perspectiveObjectId").asInstanceOf[Int]
  private[this] val linkPerspectiveClientId = params("linkPerspectiveClientId").asInstanceOf[Int]
  private[this] val linkPerspectiveObjectId = params("linkPerspectiveObjectId").asInstanceOf[Int]
  private[this] val lexicalEntry = params("lexicalEntry").asInstanceOf[LexicalEntry]
  private[this] val field = params("field").asInstanceOf[Field]
  private[this] val links = params("links").asInstanceOf[js.Array[Link]]

  private[this] val dictionaryId = CompositeId(dictionaryClientId, dictionaryObjectId)
  private[this] val perspectiveId = CompositeId(perspectiveClientId, perspectiveObjectId)
  private[this] val linkPerspectiveId = CompositeId(linkPerspectiveClientId, linkPerspectiveObjectId)

  private[this] var perspectiveTranslation: Option[TranslationGist] = None

  private[this] var enabledInputs: Seq[String] = Seq[String]()

  scope.count = 0
  scope.offset = 0
  scope.size = 5
  scope.pageCount = 1
  scope.edit = true

  private[this] var createdEntities = Seq[Entity]()

  private[this] var dataTypes = Seq[TranslationGist]()
  private[this] var perspectiveFields = Seq[Field]()
  private[this] var linkedPerspectiveFields = Seq[Field]()

  // wavesurfer
  private [this] var waveSurfer: Option[WaveSurfer] = None
  private var _pxPerSec = 50 // minimum pxls per second, all timing is bounded to it
  val pxPerSecStep = 30 // zooming step
  // zoom in/out step; fake value to avoid division by zero; on ws load, it will be set correctly
  private var _duration: Double = 42.0
  var fullWSWidth = 0.0 // again, will be known after audio load
  var wsHeight = 128
  var soundMarkup: Option[String] = None


  load()


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
    options.templateUrl = "/static/templates/modal/soundMarkup.html"
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
  def addNewLexicalEntry() = {

    backend.createLexicalEntry(dictionaryId, linkPerspectiveId) onComplete {
      case Success(entryId) =>
        backend.getLexicalEntry(dictionaryId, linkPerspectiveId, entryId) onComplete {
          case Success(entry) =>
            scope.dictionaryTable.addEntry(entry)
            // create corresponding entity in main perspective
            val entity = EntityData(field.clientId, field.objectId, 2)
            entity.linkClientId = Some(entry.clientId)
            entity.linkObjectId = Some(entry.objectId)
            backend.createEntity(dictionaryId, perspectiveId, CompositeId.fromObject(lexicalEntry), entity) onComplete {
              case Success(entityId) =>
                backend.getEntity(dictionaryId, perspectiveId, CompositeId.fromObject(lexicalEntry), entityId) onComplete {
                // backend.getEntity(dictionaryId, perspectiveId, entryId, entityId) onComplete {
                  case Success(newEntity) =>
                    createdEntities = createdEntities :+ newEntity
                    lexicalEntry.entities.push(newEntity)
                  case Failure(ex) => throw ControllerException("Attempt to get link entity failed", ex)
                }
              case Failure(ex) => throw ControllerException("Attempt to create link entity failed", ex)
            }

          case Failure(e) => throw ControllerException("Attempt to get linked lexical entry failed", e)
        }
      case Failure(e) => throw ControllerException("Attempt to create linked lexical entry failed", e)
    }
  }

  @JSExport
  def loadPage(page: Int) = {
    val offset = (page - 1) * scope.size
    backend.getLexicalEntries(dictionaryId, linkPerspectiveId, LexicalEntriesType.All, offset, scope.size) onComplete {
      case Success(entries) =>
        scope.offset = offset
        scope.linkedDictionaryTable = DictionaryTable.build(linkedPerspectiveFields, dataTypes, entries)
      case Failure(e) => console.error(e.getMessage)
    }
  }

  @JSExport
  def range(min: Int, max: Int, step: Int) = {
    (min to max by step).toSeq.toJSArray
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
  def addLinkToLexicalEntry(entry: LexicalEntry) = {
    // add link to this lexical entry
    scope.dictionaryTable.addEntry(entry)
    // create corresponding entity in main perspective
    val entity = EntityData(field.clientId, field.objectId, 2)
    entity.linkClientId = Some(entry.clientId)
    entity.linkObjectId = Some(entry.objectId)
    backend.createEntity(dictionaryId, perspectiveId, CompositeId.fromObject(lexicalEntry), entity) onComplete {
      case Success(entityId) =>
        backend.getEntity(dictionaryId, perspectiveId, CompositeId.fromObject(lexicalEntry), entityId) onComplete {
          case Success(newEntity) =>
            lexicalEntry.entities.push(newEntity)
            createdEntities = createdEntities :+ newEntity
          case Failure(ex) => throw ControllerException("Attempt to get link entity failed", ex)
        }
      case Failure(ex) => throw ControllerException("Attempt to create link entity failed", ex)
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

    val entryId = CompositeId.fromObject(entry)

    val entity = EntityData(field.clientId, field.objectId, Utils.getLocale().getOrElse(2))
    entity.content = Some(Left(textValue))

    // self
    parent map {
      parentValue =>
        entity.selfClientId = Some(parentValue.getEntity.clientId)
        entity.selfObjectId = Some(parentValue.getEntity.objectId)
    }

    backend.createEntity(dictionaryId, linkPerspectiveId, entryId, entity) onComplete {
      case Success(entityId) =>
        backend.getEntity(dictionaryId, linkPerspectiveId, entryId, entityId) onComplete {
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


    val entryId = CompositeId.fromObject(entry)

    val entity = EntityData(field.clientId, field.objectId, Utils.getLocale().getOrElse(2))
    entity.content = Some(Right(FileContent(fileName, fileType, fileContent)))

    // self
    parent map {
      parentValue =>
        entity.selfClientId = Some(parentValue.getEntity.clientId)
        entity.selfObjectId = Some(parentValue.getEntity.objectId)
    }

    backend.createEntity(dictionaryId, linkPerspectiveId, entryId, entity) onComplete {
      case Success(entityId) =>
        backend.getEntity(dictionaryId, linkPerspectiveId, entryId, entityId) onComplete {
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

  @JSExport
  def viewLinkedPerspective(entry: LexicalEntry, field: Field, values: js.Array[Value]) = {

    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/viewLinkedDictionary.html"
    options.controller = "ViewDictionaryModalController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          dictionaryClientId = dictionaryClientId.asInstanceOf[js.Object],
          dictionaryObjectId = dictionaryObjectId.asInstanceOf[js.Object],
          linkPerspectiveClientId = perspectiveClientId,
          linkPerspectiveObjectId = perspectiveObjectId,
          perspectiveClientId = field.link.get.clientId,
          perspectiveObjectId = field.link.get.objectId,
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

  @JSExport
  def linkedPerspectiveName(): String = {
    perspectiveTranslation match {
      case Some(gist) =>
        val localeId = Utils.getLocale().getOrElse(2)
        gist.atoms.find(_.localeId == localeId) match {
          case Some(atom) => atom.content
          case None => ""
        }
      case None => ""
    }
  }

  @JSExport
  def isLexicalEntryLinked(entry: LexicalEntry): Boolean = {
    (dataTypes.find(d => d.atoms.exists(atom => atom.localeId == 2 && atom.content == "Link")) map {
      linkDataType =>
        val linkFields = perspectiveFields.filter(field => field.dataTypeTranslationGistClientId == linkDataType.clientId && field.dataTypeTranslationGistObjectId == linkDataType.objectId)

        val linkEntities = linkFields.flatMap {
          field =>
            lexicalEntry.entities.filter(e => e.fieldClientId == field.clientId && e.fieldObjectId == field.objectId)
        }

        linkEntities.exists { e => e.link match {
          case Some(link) => link.clientId == entry.clientId && link.objectId == entry.objectId
          case None => false
        }}
    }).get
  }


  @JSExport
  def close() = {
    instance.close(createdEntities)
  }



  private[this] def load() = {

    backend.perspectiveSource(linkPerspectiveId) onComplete {
      case Success(sources) =>
        scope.linkedPath = sources.reverse.map { _.source match {
          case language: Language => language.translation
          case dictionary: Dictionary => dictionary.translation
          case perspective: Perspective => perspective.translation
        }}.mkString(" >> ")
      case Failure(e) => console.error(e.getMessage)
    }

    backend.perspectiveSource(perspectiveId) onComplete {
      case Success(sources) =>
        scope.path = sources.reverse.map { _.source match {
          case language: Language => language.translation
          case dictionary: Dictionary => dictionary.translation
          case perspective: Perspective => perspective.translation
        }}.mkString(" >> ")
      case Failure(e) => console.error(e.getMessage)
    }

    backend.getPerspective(linkPerspectiveId) map {
      p =>
        backend.translationGist(p.translationGistClientId, p.translationGistObjectId) map {
          gist =>
            perspectiveTranslation = Some(gist)
        }
    }


    backend.dataTypes() onComplete {
      case Success(allDataTypes) =>
        dataTypes = allDataTypes

        // get fields of main perspective
        backend.getFields(dictionaryId, perspectiveId) onComplete {
          case Success(fields) =>
            perspectiveFields = fields

            // get fields of this perspective
            backend.getFields(dictionaryId, linkPerspectiveId) onComplete {
              case Success(linkedFields) =>

                backend.getLexicalEntriesCount(dictionaryId, linkPerspectiveId) onComplete {
                  case Success(count) =>
                    scope.pageCount = scala.math.ceil(count.toDouble / scope.size).toInt
                    backend.getLexicalEntries(dictionaryId, linkPerspectiveId, LexicalEntriesType.All, scope.offset, scope.size) onComplete {
                      case Success(entries) =>
                        scope.linkedDictionaryTable = DictionaryTable.build(linkedFields, dataTypes, entries)
                      case Failure(e) => console.log(e.getMessage)
                    }
                  case Failure(e) => console.log(e.getMessage)
                }

                linkedPerspectiveFields = linkedFields
                val reqs = links.toSeq.map { link => backend.getLexicalEntry(dictionaryId, linkPerspectiveId, CompositeId(link.clientId, link.objectId)) }
                Future.sequence(reqs) onComplete {
                  case Success(lexicalEntries) =>
                    scope.dictionaryTable = DictionaryTable.build(linkedFields, dataTypes, lexicalEntries)
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
