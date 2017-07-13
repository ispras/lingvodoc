package ru.ispras.lingvodoc.frontend.app.controllers.webui.modal

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.{ModalInstance, ModalOptions, ModalService}
import com.greencatsoft.angularjs.{AngularExecutionContextProvider, injectable}
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseModalController
import ru.ispras.lingvodoc.frontend.app.controllers.common.{DictionaryTable, Value}
import ru.ispras.lingvodoc.frontend.app.controllers.traits.{SimplePlay, ViewMarkup}
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, UserService}

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.UndefOr
import scala.scalajs.js.annotation.JSExport
import org.scalajs.dom.console



@js.native
trait ContributionsGroupingTagModalScope extends Scope {
  var pageLoaded: Boolean = js.native
  var dictionaryTables: js.Array[DictionaryTable] = js.native
  var searchQuery: String = js.native
  var searchResults: js.Array[DictionaryTable] = js.native
  var size: Int = js.native
  var pageNumber: Int = js.native
  var resultEntriesCount: Int = js.native
}


@injectable("ContributionsGroupingTagModalController")
class ContributionsGroupingTagModalController(scope: ContributionsGroupingTagModalScope,
                                              val modal: ModalService,
                                              instance: ModalInstance[Unit],
                                              val backend: BackendService,
                                              userService: UserService,
                                              timeout: Timeout,
                                              val exceptionHandler: ExceptionHandler,
                                              params: js.Dictionary[js.Function0[js.Any]])
  extends BaseModalController(scope, modal, instance, timeout, params)
    with AngularExecutionContextProvider
    with SimplePlay
    with ViewMarkup {

  private[this] val dictionaryClientId = params("dictionaryClientId").asInstanceOf[Int]
  private[this] val dictionaryObjectId = params("dictionaryObjectId").asInstanceOf[Int]
  private[this] val perspectiveClientId = params("perspectiveClientId").asInstanceOf[Int]
  private[this] val perspectiveObjectId = params("perspectiveObjectId").asInstanceOf[Int]
  private[this] var lexicalEntry = params("lexicalEntry").asInstanceOf[LexicalEntry]
  private[this] val field = params("field").asInstanceOf[Field]
  protected[this] val dictionaryId = CompositeId(dictionaryClientId, dictionaryObjectId)
  protected[this] val perspectiveId = CompositeId(perspectiveClientId, perspectiveObjectId)
  private[this] val lexicalEntryId = CompositeId.fromObject(lexicalEntry)
  private[this] val fieldId = CompositeId.fromObject(field)

  private[this] var foundEntries = Seq[Seq[LexicalEntry]]()
  private[this] var dataTypes = Seq[TranslationGist]()
  private[this] var statuses = Seq[TranslationGist]()
  private[this] var dictionaries = Seq[Dictionary]()
  private[this] var perspectives = Seq[Perspective]()
  private[this] var searchDictionaries = Seq[Dictionary]()
  private[this] var searchPerspectives = Seq[Perspective]()

  private[this] var tables = Map.empty[String, Seq[DictionaryTable]]


  override def spectrogramId: String = "#spectrogram-modal"

  scope.pageLoaded = false
  scope.searchQuery = ""
  scope.searchResults = js.Array[DictionaryTable]()
  scope.size = 10
  scope.pageNumber = 1
  scope.resultEntriesCount = -1

  @JSExport
  def tags(): js.Array[String] = {
    tables.keys.toJSArray
  }

  @JSExport
  def dictionaryTables(tag: String): js.Array[DictionaryTable] = {
    tables.get(tag).get.toJSArray
  }

  @JSExport
  def getSource(dictionaryTable: DictionaryTable): UndefOr[String] = {
    dictionaryTable.rows.toSeq.headOption.flatMap { row =>
      val entry = row.entry
      perspectives.find(p => p.clientId == entry.parentClientId && p.objectId == entry.parentObjectId).flatMap { perspective =>
        dictionaries.find(d => d.clientId == perspective.parentClientId && d.objectId == perspective.parentObjectId).map { dictionary =>
          s"${dictionary.translation} / ${perspective.translation}"
        }
      }
    }.orUndefined

  }

  @JSExport
  def getSearchSource(entry: LexicalEntry): UndefOr[String] = {
    searchPerspectives.find(p => p.clientId == entry.parentClientId && p.objectId == entry.parentObjectId).flatMap { perspective =>
      searchDictionaries.find(d => d.clientId == perspective.parentClientId && d.objectId == perspective.parentObjectId).map { dictionary =>
        s"${dictionary.translation} / ${perspective.translation}"
      }
    }.orUndefined
  }

  @JSExport
  def search(): Unit = {
    load(() => {
      foundEntries = Seq[Seq[LexicalEntry]]()
      backend.search(scope.searchQuery, None, tagsOnly = false, Some(fieldId)) map { results =>
        foundEntries = results.map(_.lexicalEntry)
          .filterNot(entry => scope.dictionaryTables.exists(_.rows.exists(_.entry.getId == entry.getId)))
          .groupBy(e => CompositeId(e.parentClientId, e.parentObjectId).getId)
          .values
          .toSeq
        getPage(1)
      }
    })
  }

  @JSExport
  def remove(entry: LexicalEntry): Unit = {
    backend.disconnectLexicalEntry(entry, CompositeId.fromObject(field)).foreach { _ =>
      loadConnectedEntries()
    }
  }

  @JSExport
  def baseEntry(entry: LexicalEntry): Boolean = {
    lexicalEntry.getId == entry.getId
  }

  @JSExport
  def close(): Unit = {
    instance.dismiss(())
  }

  @JSExport
  def accept(tag: String): Unit = {
    lexicalEntry.entities.find(e => e.fieldClientId == field.clientId && e.fieldObjectId == field.objectId && e.content == tag) foreach { entity =>
      if (!entity.accepted) {
        backend.acceptEntities(dictionaryId, perspectiveId, CompositeId.fromObject(entity) :: Nil) map { _ =>
          // remove accepted tags from list of candidates
          scope.$apply(() => {
            tables -= "tag"
            entity.accepted = true
          })
        }
      }
    }
  }

  @JSExport
  def acceptDisabled(tag: String): Boolean = {
    lexicalEntry.entities.find(e => e.fieldClientId == field.clientId && e.fieldObjectId == field.objectId && e.content == tag).exists(_.accepted)
  }


  @JSExport
  def acceptGroupingTag(entry: LexicalEntry, field: Field, values: js.Array[Value]): Unit = {

    perspectives.find(p => p.clientId == entry.parentClientId && p.objectId == entry.parentObjectId).flatMap { perspective =>
      dictionaries.find(d => d.clientId == perspective.parentClientId && d.objectId == perspective.parentObjectId).map { dictionary =>

        val options = ModalOptions()
        options.templateUrl = "/static/templates/modal/acceptGroupingTag.html"
        options.controller = "ContributionsGroupingTagModalController"
        options.backdrop = false
        options.keyboard = false
        options.size = "lg"
        options.resolve = js.Dynamic.literal(
          params = () => {
            js.Dynamic.literal(
              dictionaryClientId = dictionary.clientId,
              dictionaryObjectId = dictionary.objectId,
              perspectiveClientId = perspective.clientId,
              perspectiveObjectId = perspective.objectId,
              lexicalEntry = entry.asInstanceOf[js.Object],
              field = field.asInstanceOf[js.Object],
              values = values.asInstanceOf[js.Object]
            )
          }
        ).asInstanceOf[js.Dictionary[Any]]

        val instance = modal.open[Unit](options)
        instance.result map { _ =>

        }
      }
    }
    ()
  }

  @JSExport
  def range() = {
    (1 to scala.math.ceil(foundEntries.size.toDouble / scope.size).toInt by 1).toSeq.toJSArray
  }

  @JSExport
  def getPage(p: Int): Unit = {
    scope.pageLoaded = false
    val offset = (p - 1) * scope.size
    val entries = foundEntries.slice(offset, offset + scope.size)

    // get perspectives
    Future.sequence(entries.map { e => backend.getPerspective(CompositeId(e.head.parentClientId, e.head.parentObjectId)) }) map { perspectives =>
      searchPerspectives = perspectives

      // get dictionaries
      Future.sequence(perspectives.map { p => backend.getDictionary(CompositeId(p.parentClientId, p.parentObjectId)) }) map { dictionaries =>
        searchDictionaries = dictionaries

        // get fields
        Future.sequence(perspectives.map { p =>
          backend.getFields(CompositeId(p.parentClientId, p.parentObjectId), CompositeId.fromObject(p)).map { fields =>
            DictionaryTable.build(fields, dataTypes, entries.find(e => e.head.parentClientId == p.clientId && e.head.parentObjectId == p.objectId).get)
          }
        }).foreach { tables =>
          scope.searchResults = tables.toJSArray
          scope.pageLoaded = true
          scope.pageNumber = p
        }
      }
    }
  }

  private[this] def loadConnectedEntries() = {

    // exclude unknown and already accepted tags
    val knownTags = lexicalEntry.entities.filter(entity => entity.fieldClientId == field.clientId && entity.fieldObjectId == field.objectId && !entity.accepted).map(_.content).toSet

    backend.connectedLexicalEntries(lexicalEntryId, fieldId) map { connectedEntries =>

      var groups = Map.empty[String, Seq[LexicalEntry]]

      connectedEntries.foreach { entry =>

        val groupKeys = entry.entities
          .filter(entity => entity.fieldClientId == field.clientId && entity.fieldObjectId == field.objectId && knownTags.contains(entity.content))
          .groupBy(_.content).keys.toSeq

        groupKeys.foreach { g =>
          val s = groups.getOrElse(g, Seq.empty[LexicalEntry])
          groups = groups + (g -> (s :+ entry))
        }
      }

      val tf = groups.toSeq flatMap { case (k, entries) =>
        // collect entries from the same source
        entries.groupBy(entry => CompositeId(entry.parentClientId, entry.parentObjectId)).map { case (parentId, perspectiveEntries) =>
          backend.getPerspective(parentId) flatMap { connectedPerspective =>
            backend.getFields(CompositeId(connectedPerspective.parentClientId, connectedPerspective.parentObjectId), CompositeId.fromObject(connectedPerspective)) map { connectedFields =>
              (k, DictionaryTable.build(connectedFields, dataTypes, perspectiveEntries))
            }
          }
        }
      }

      Future.sequence(tf) map { t =>
        tables = t.groupBy(_._1).map(g => (g._1, g._2.map(_._2)))
      }
    }
  }

  load(() => {

    backend.getLexicalEntry(dictionaryId, perspectiveId, lexicalEntryId) map { entry =>
      lexicalEntry = entry
    }

    backend.getDictionaries() map { d =>
      dictionaries = d
    }

    backend.perspectives() map { p =>
      perspectives = p
    }

    backend.allStatuses() map { s =>
      statuses = s

      backend.dataTypes() flatMap { allDataTypes =>
        dataTypes = allDataTypes
        loadConnectedEntries()
      }
    }
  })

  override protected def onModalClose(): Unit = {
    waveSurfer.foreach(w => w.destroy())
    super.onModalClose()
  }

  override protected def onStartRequest(): Unit = {
    scope.pageLoaded = false
  }

  override protected def onCompleteRequest(): Unit = {
    scope.pageLoaded = true
  }
}
