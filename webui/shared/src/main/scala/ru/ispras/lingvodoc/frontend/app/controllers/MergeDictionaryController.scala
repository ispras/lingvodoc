
package ru.ispras.lingvodoc.frontend.app.controllers


import com.greencatsoft.angularjs.core._
import com.greencatsoft.angularjs.extensions.{ModalOptions, ModalService}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import org.scalajs.dom.console
import org.scalajs.dom.raw.HTMLInputElement
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseController
import ru.ispras.lingvodoc.frontend.app.controllers.common._
import ru.ispras.lingvodoc.frontend.app.controllers.traits.{LinkEntities, LoadingPlaceholder, SimplePlay}
import ru.ispras.lingvodoc.frontend.app.exceptions.ControllerException
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, LexicalEntriesType}

import scala.collection.mutable
import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.URIUtils._
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}


@js.native
trait MergeDictionaryScope extends Scope
{
  var filter: Boolean = js.native
  var path: String = js.native

  /** Number of result entry groups shown on a single page. */
  var pageSize: Int = js.native

  /** Total number of result pages. */
  var pageCount: Int = js.native

  /** Number of the result page currently being shown. */
  var pageNumber: Int = js.native

  var result_count: Int = js.native
  var dictionaryTables: js.Array[DictionaryTable] = js.native

  /** Identifiers of currently selected lexical entries. */
  var selectedEntries: js.Dictionary[String] = js.native

  /** Number of currently selected lexical entries, should always be exactly Object.keys(selectedEntries).
    * length. */
  var selected_entry_count: Int = js.native

  /** Indices of currently selected lexical entry groups. */
  var selectedGroups: js.Dictionary[Int] = js.native

  /** Number of currently selected lexical entry groups, should always be exactly Object.keys(
    * selectedGroups).length. */
  var selected_group_count: Int = js.native

  /** Is set to true if the user has create/delete permissions required to perform suggested merges, and to
    * false otherwise. */
  var user_has_permissions: Boolean = js.native

  var pageLoaded: Boolean = js.native
}


/**
  * Renders and executes merge of sufficiently similar lexical entries of the specified perspective.
  */
@injectable("MergeDictionaryController")
class MergeDictionaryController(
  scope: MergeDictionaryScope,
  params: RouteParams,
  modal: ModalService,
  backend: BackendService,
  timeout: Timeout,
  val exceptionHandler: ExceptionHandler)

  extends BaseController(scope, modal, timeout)
    with AngularExecutionContextProvider
    with SimplePlay
    with LinkEntities {

  private[this] val dictionaryClientId = params.get("dictionaryClientId").get.toString.toInt
  private[this] val dictionaryObjectId = params.get("dictionaryObjectId").get.toString.toInt
  private[this] val perspectiveClientId = params.get("perspectiveClientId").get.toString.toInt
  private[this] val perspectiveObjectId = params.get("perspectiveObjectId").get.toString.toInt

  private[this] val sortBy = params.get("sortBy").map(_.toString).toOption

  private[this] val dictionaryId = CompositeId(dictionaryClientId, dictionaryObjectId)
  private[this] val perspectiveId = CompositeId(perspectiveClientId, perspectiveObjectId)

  private[this] var dataTypes: Seq[TranslationGist] = Seq[TranslationGist]()
  private[this] var fields: Seq[Field] = Seq[Field]()

  private[this] var adjacency_map: mutable.Map[CompositeId, mutable.Set[CompositeId]] = mutable.Map()
  private[this] var weight_map: mutable.Map[CompositeId, Double] = mutable.Map()

  private[this] var group_seq: mutable.Seq[mutable.Set[CompositeId]] = mutable.Seq()
  private[this] var group_map: mutable.Map[CompositeId, Int] = mutable.Map()
  private[this] var table_group_array: Array[js.Array[DictionaryTable]] = Array()

  scope.pageSize = 10
  scope.pageCount = -1
  scope.pageNumber = -1

  scope.selectedEntries = js.Dictionary[String]()
  scope.selected_entry_count = 0

  scope.selectedGroups = js.Dictionary[Int]()
  scope.selected_group_count = 0

  scope.user_has_permissions = false

  scope.pageLoaded = false

  @JSExport
  def getActionLink(action: String) = {
    "#/dictionary/" +
      encodeURIComponent(dictionaryClientId.toString) + '/' +
      encodeURIComponent(dictionaryObjectId.toString) + "/perspective/" +
      encodeURIComponent(perspectiveClientId.toString) + "/" +
      encodeURIComponent(perspectiveObjectId.toString) + "/" +
      action
  }

  @JSExport
  def getPage(p: Int): Unit =
  {
    scope.pageNumber = p
    scope.dictionaryTables = table_group_array(scope.pageNumber - 1)
  }

  @JSExport
  def range() =
  {
    js.Array((1 to table_group_array.length.toInt by 1).toSeq: _*)
  }

  @JSExport
  def toggleSelectedEntries(client_id: Int, object_id: Int) =
  {
    val composite_id = CompositeId(client_id, object_id)
    val string_id = composite_id.getId

    if (scope.selectedEntries.contains(string_id))
    {
      scope.selectedEntries.delete(string_id)
      scope.selected_entry_count -= 1
    }
    else
    {
      scope.selectedEntries(string_id) = string_id
      scope.selected_entry_count += 1
    }

    /* Checking if the entry's group have enough selected entries to be selected itself. */

    val group_index = group_map(composite_id)
    var entry_count = 0

    for (entry_id <- group_seq(group_index).toSeq.sorted)
      if (scope.selectedEntries.contains(entry_id.getId))
        entry_count += 1

    val group_string_id = "group" + group_index.toString

    console.log(group_string_id)
    console.log(entry_count)

    if (entry_count <= 1 && scope.selectedGroups.contains(group_string_id))
    {
      /* Group is selected, but it shouldn't be, so we deselect it. */

      scope.selectedGroups.delete(group_string_id)
      scope.selected_group_count -= 1
    }

    else if (entry_count > 1 && !scope.selectedGroups.contains(group_string_id))
    {
      /* Group is not selected, but it should be, so we select it. */

      scope.selectedGroups(group_string_id) = group_index
      scope.selected_group_count += 1
    }

    console.log(scope.selectedEntries)
    console.log(scope.selected_entry_count)

    console.log(scope.selectedGroups)
    console.log(scope.selected_group_count)
  }

  @JSExport
  def toggleSelectedGroups(group_index: Int) =
  {
    val string_id = "group" + group_index.toString
    console.log(group_index)

    if (scope.selectedGroups.contains(string_id))
    {
      /* Group is selected, we deselect the whole group. */

      scope.selectedGroups.delete(string_id)
      scope.selected_group_count -= 1

      for (entry_id <- group_seq(group_index))
        if (scope.selectedEntries.contains(entry_id.getId))
        {
          scope.selectedEntries.delete(entry_id.getId)
          scope.selected_entry_count -= 1
        }
    }
    else
    {
      /* Group is not selected, we select the whole group. */

      scope.selectedGroups(string_id) = group_index
      scope.selected_group_count += 1

      for (entry_id <- group_seq(group_index))
        if (!scope.selectedEntries.contains(entry_id.getId))
        {
          scope.selectedEntries(entry_id.getId) = entry_id.getId
          scope.selected_entry_count += 1
        }
    }

    console.log(scope.selectedEntries)
    console.log(scope.selected_entry_count)

    console.log(scope.selectedGroups)
    console.log(scope.selected_group_count)
  }

  @JSExport
  def viewSoundMarkup(soundValue: Value, markupValue: Value) = {

    val soundAddress = soundValue.getContent()

    backend.convertMarkup(CompositeId.fromObject(markupValue.getEntity())) onComplete {
      case Success(elan) =>
        val options = ModalOptions()
        options.templateUrl = "/static/templates/modal/soundMarkup.html"
        options.windowClass = "sm-modal-window"
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
        ).asInstanceOf[js.Dictionary[Any]]
        val instance = modal.open[Unit](options)
      case Failure(e) =>
    }
  }

  @JSExport
  def viewMarkup(markupValue: Value) = {

    backend.convertMarkup(CompositeId.fromObject(markupValue.getEntity())) onComplete {
      case Success(elan) =>
        val options = ModalOptions()
        options.templateUrl = "/static/templates/modal/soundMarkup.html"
        options.windowClass = "sm-modal-window"
        options.controller = "SoundMarkupController"
        options.backdrop = false
        options.keyboard = false
        options.size = "lg"
        options.resolve = js.Dynamic.literal(
          params = () => {
            js.Dynamic.literal(
              markupData = elan.asInstanceOf[js.Object],
              markupAddress = markupValue.getEntity().content.asInstanceOf[js.Object],
              dictionaryClientId = dictionaryClientId.asInstanceOf[js.Object],
              dictionaryObjectId = dictionaryObjectId.asInstanceOf[js.Object]
            )
          }
        ).asInstanceOf[js.Dictionary[Any]]
        val instance = modal.open[Unit](options)
      case Failure(e) =>
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

/*
  At the moment we do not support that, as it requires updating dictionary table. In the future we will fix
  that.

  @JSExport
  def viewLinkedPerspective(entry: LexicalEntry, field: Field, values: js.Array[Value]) =
  {
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
          perspectiveClientId = perspectiveClientId,
          perspectiveObjectId = perspectiveObjectId,
          linkPerspectiveClientId = field.link.get.clientId,
          linkPerspectiveObjectId = field.link.get.objectId,
          lexicalEntry = entry.asInstanceOf[js.Object],
          field = field.asInstanceOf[js.Object],
          links = values.map { _.asInstanceOf[GroupValue].link }
        )
      }
    ).asInstanceOf[js.Dictionary[Any]]

    val instance = modal.open[Seq[Entity]](options)
    instance.result map { entities =>
      entities.foreach(e => scope.dictionaryTable.addEntity(entry, e))
    }
  }
*/

  @JSExport
  def viewGroupingTag(entry: LexicalEntry, field: Field, values: js.Array[Value]) = {

    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/viewGroupingTag.html"
    options.controller = "EditGroupingTagModalController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          dictionaryClientId = dictionaryClientId,
          dictionaryObjectId = dictionaryObjectId,
          perspectiveClientId = perspectiveClientId,
          perspectiveObjectId = perspectiveObjectId,
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

  @JSExport
  def phonology(): Unit = {
    backend.phonology(perspectiveId) map { blob =>
      val options = ModalOptions()
      options.templateUrl = "/static/templates/modal/downloadEmbeddedBlob.html"
      options.windowClass = "sm-modal-window"
      options.controller = "DownloadEmbeddedBlobController"
      options.backdrop = false
      options.keyboard = false
      options.size = "lg"
      options.resolve = js.Dynamic.literal(
        params = () => {
          js.Dynamic.literal(
            "fileName" -> "phonology.xlsx",
            "fileType" -> "application/vnd.ms-excel",
            "blob" -> blob
          )
        }
      ).asInstanceOf[js.Dictionary[Any]]
      modal.open[Unit](options)
    } recover { case e: Throwable =>
      error(e)
    }
  }

  load(() => {
    backend.perspectiveSource(perspectiveId) flatMap {
      sources =>
        scope.path = sources.reverse.map {
          _.source match {
            case language: Language => language.translation
            case dictionary: Dictionary => dictionary.translation
            case perspective: Perspective => perspective.translation
          }
        }.mkString(" >> ")

        backend.dataTypes() flatMap { d =>
          dataTypes = d
          backend.getFields(dictionaryId, perspectiveId) flatMap { f =>
            fields = f

            /* Getting merge suggestions data. */

            backend.mergeSuggestions(perspectiveId) map
            {
              case (entry_seq, match_seq, user_has_permissions) =>

                scope.user_has_permissions = user_has_permissions

                /* Computing lexical entry match graph. */

                for ((id_a, id_b, confidence) <- match_seq)
                {
                  adjacency_map(id_a) = adjacency_map.getOrElse(id_a, mutable.Set()) + id_b
                  adjacency_map(id_b) = adjacency_map.getOrElse(id_b, mutable.Set()) + id_a

                  weight_map(id_a) = weight_map.getOrElse(id_a, 0.0) + confidence / 2
                  weight_map(id_b) = weight_map.getOrElse(id_b, 0.0) + confidence / 2
                }

                console.log(adjacency_map.toString)
                console.log(weight_map.toString)

                /* Grouping lexical entries into mutually matching groups. */

                def df_search(entry_id: CompositeId, group_index: Int): Unit =
                {
                  if (group_map.contains(entry_id))
                    return

                  group_seq.last += entry_id
                  group_map(entry_id) = group_index

                  for (id <- adjacency_map(entry_id))
                    df_search(id, group_index)
                }

                for (entry_id <- adjacency_map.keys.toSeq.sorted)
                  if (!group_map.contains(entry_id))
                  {
                    group_seq :+= mutable.Set()
                    df_search(entry_id, group_seq.length - 1)
                  }

                console.log(adjacency_map.keys.toSeq.sorted.toString)
                console.log(group_seq.toString)
                console.log(group_map.toString)

                /* Setting up lexical entry group data for rendering. */

                val entry_map = Map(
                  entry_seq map { entry => (CompositeId(entry.clientId, entry.objectId) -> entry) }: _*)

                console.log(entry_map.toString)

                val dictionary_table_seq: mutable.Seq[DictionaryTable] =
                  group_seq .zipWithIndex .map { case (group, index) =>
                    DictionaryTable.build(fields, dataTypes,
                      group.toSeq.sorted.map { entry_id => entry_map(entry_id) }, Some(index)) }

                table_group_array = dictionary_table_seq
                  .grouped(scope.pageSize)
                  .map { table_seq => js.Array(table_seq: _*) }
                  .toArray

                scope.pageCount = table_group_array.length
                scope.pageNumber = 1

                scope.result_count = group_seq.length
                scope.dictionaryTables = table_group_array(scope.pageNumber - 1)

                /* Setting up tracking selection of lexical entry groups. */

                for (entry_id <- adjacency_map.keys)
                  scope.selectedEntries(entry_id.getId) = entry_id.getId

                scope.selected_entry_count = adjacency_map.size

                for (group_index <- 0 until group_seq.length)
                  scope.selectedGroups("group" + group_index.toString) = group_index

                scope.selected_group_count = group_seq.length

                console.log(scope.selectedEntries)
                console.log(scope.selected_entry_count)
                console.log(scope.selectedGroups)
                console.log(scope.selected_group_count)

                table_group_array

            } recover { case e: Throwable => Future.failed(e) }

            /*
            backend.getLexicalEntriesCount(dictionaryId, perspectiveId, LexicalEntriesType.Published) flatMap { count =>
              scope.pageCount = scala.math.ceil(count.toDouble / scope.size).toInt
              val offset = getOffset(scope.pageNumber, scope.size)
              backend.getLexicalEntries(dictionaryId, perspectiveId, LexicalEntriesType.Published, offset, scope.size, sortBy) flatMap { entries =>

                scope.dictionaryTable = DictionaryTable.build(fields, dataTypes, entries)

                backend.getPerspectiveRoles(dictionaryId, perspectiveId) map { roles =>
                  perspectiveRoles = Some(roles)
                  roles
                } recover {
                  case e: Throwable => Future.failed(e)
                }
              } recover {
                case e: Throwable => Future.failed(e)
              }
            } recover {
              case e: Throwable => Future.failed(e)
            }
            */
          } recover {
            case e: Throwable => Future.failed(e)
          }
        } recover {
          case e: Throwable => Future.failed(e)
        }
    } recover {
      case e: Throwable => Future.failed(e)
    }
  })

  override protected def onStartRequest(): Unit = {
    scope.pageLoaded = false
  }

  override protected def onCompleteRequest(): Unit = {
    scope.pageLoaded = true
  }

  /** Performs merge of selected entry groups. */
  @JSExport
  def performMerge(): Unit =
  {
    console.log("performMerge")

    val selected_seq = Seq({

      for ((group_set, group_index) <- group_seq.zipWithIndex
        if scope.selectedGroups.contains("group" + group_index.toString))

          yield Seq(group_set.toSeq.sorted: _*).filter(
            entry_id => scope.selectedEntries.contains(entry_id.getId))}: _*)

    console.log(selected_seq.length)
    console.log(selected_seq.toString)

    backend.bulkMerge(selected_seq)
      .map { entry_id_seq => () }
      .recover { case e: Throwable => error(e) }
  }
}

