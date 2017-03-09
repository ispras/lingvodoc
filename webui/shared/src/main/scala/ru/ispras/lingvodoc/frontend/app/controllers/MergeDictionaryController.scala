
package ru.ispras.lingvodoc.frontend.app.controllers


import com.greencatsoft.angularjs.core._
import com.greencatsoft.angularjs.extensions.{ModalOptions, ModalService}
import com.greencatsoft.angularjs.{AngularExecutionContextProvider, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseController
import ru.ispras.lingvodoc.frontend.app.controllers.common._
import ru.ispras.lingvodoc.frontend.app.controllers.traits.{SimplePlay, ViewMarkup}
import ru.ispras.lingvodoc.frontend.app.exceptions.ControllerException
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.BackendService

import scala.collection.mutable
import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.JSON
import scala.scalajs.js.URIUtils._
import scala.scalajs.js.annotation.JSExport


@js.native
trait MergeDictionaryScope extends Scope
{
  var filter: Boolean = js.native
  var path: String = js.native

  /** Entity matching algorithm used for computation of merge suggestions.
    * Possible values: 'simple', 'fields'. Default value: 'simple'. */
  var algorithm: String = js.native

  /** List of all fields, including subfields, of the perspective, with their data types. */
  var field_data_list: js.Array[js.Tuple2[Field, TranslationGist]] = js.native

  /** List of fields selected for merge suggestions, with additional options. */
  var field_selection_list: js.Array[js.Dynamic] = js.native

  /** If all field selections have valid data. */
  var field_selection_valid: Boolean = js.native

  /** Entity matching threshold. */
  var threshold: String = js.native

  /** Number of result entry groups shown on a single page. */
  var pageSize: Int = js.native

  /** Total number of result pages. */
  var pageCount: Int = js.native

  /** Number of the result page currently being shown. */
  var pageNumber: Int = js.native

  var result_count: Int = js.native
  var dictionaryTables: js.Array[DictionaryTable] = js.native

  /** 
    * How we set publishing state of merged entities, either when any merged entity is published (value
    * "any"), or when all merged entities are published (value "all").
    *
    * Default value is "any".
    */
  var publishMergeMode: String = js.native

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
  var suggestionsLoading: Boolean = js.native
}


/**
  * Renders and executes merge of sufficiently similar lexical entries of the specified perspective.
  */
@injectable("MergeDictionaryController")
class MergeDictionaryController(
  scope: MergeDictionaryScope,
  params: RouteParams,
  val modal: ModalService,
  val backend: BackendService,
  timeout: Timeout,
  val exceptionHandler: ExceptionHandler)

  extends BaseController(scope, modal, timeout)
    with AngularExecutionContextProvider
    with SimplePlay
    with ViewMarkup {

  private[this] val __debug__ = false

  private[this] val dictionaryClientId = params.get("dictionaryClientId").get.toString.toInt
  private[this] val dictionaryObjectId = params.get("dictionaryObjectId").get.toString.toInt
  private[this] val perspectiveClientId = params.get("perspectiveClientId").get.toString.toInt
  private[this] val perspectiveObjectId = params.get("perspectiveObjectId").get.toString.toInt

  private[this] val sortBy = params.get("sortBy").map(_.toString).toOption

  protected[this] val dictionaryId = CompositeId(dictionaryClientId, dictionaryObjectId)
  protected[this] val perspectiveId = CompositeId(perspectiveClientId, perspectiveObjectId)

  private[this] var dataTypes: Seq[TranslationGist] = Seq[TranslationGist]()
  private[this] var fields: Seq[Field] = Seq[Field]()

  private[this] var adjacency_map: mutable.Map[CompositeId, mutable.Set[CompositeId]] = mutable.Map()
  private[this] var weight_map: mutable.Map[CompositeId, Double] = mutable.Map()

  private[this] var group_seq: mutable.Seq[mutable.Set[CompositeId]] = mutable.Seq()
  private[this] var group_map: mutable.Map[CompositeId, Int] = mutable.Map()
  private[this] var dictionary_table_seq: mutable.Seq[DictionaryTable] = mutable.Seq()
  private[this] var table_group_array: Array[js.Array[DictionaryTable]] = Array()

  scope.algorithm = "simple"

  scope.field_data_list = js.Array()
  scope.field_selection_list = js.Array()
  scope.field_selection_valid = true
  scope.threshold = "0.1"

  scope.pageSize = 10
  scope.pageCount = -1
  scope.pageNumber = -1

  scope.publishMergeMode = "any"

  scope.selectedEntries = js.Dictionary[String]()
  scope.selected_entry_count = 0

  scope.selectedGroups = js.Dictionary[Int]()
  scope.selected_group_count = 0

  scope.user_has_permissions = false

  scope.pageLoaded = false
  scope.suggestionsLoading = false

  /** To be used for recover from Future failures, logs exception info to the console. */
  def recover_with_log(exception: Throwable): Unit =
  {
    console.log(exception.toString)
    console.log(exception.getMessage)

    val http_message_map = Map(
      403 -> "Forbidden")

    val stack_trace =
      exception.getCause match
      {
        /* HTTP exceptions are processed separately. */

        case cause: HttpException =>

          console.log(s"HTTP ${cause.status.code} " +
            http_message_map.getOrElse(cause.status.code, ""))

          cause.getStackTrace.mkString("\n")

        /* Other exceptions. */

        case cause: Throwable =>

          console.log(cause.toString)
          console.log(cause.getMessage)

          cause.getStackTrace.mkString("\n")

        case _ =>
          exception.getStackTrace.mkString("\n")
      }

    console.log(stack_trace)
    error(exception)
  }

  @JSExport
  def getActionLink(action: String): String = {
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
  def range(): js.Array[Int] =
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

    if (__debug__)
    {
      console.log(group_string_id)
      console.log(entry_count)
    }

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

    if (__debug__)
    {
      console.log(scope.selectedEntries)
      console.log(scope.selected_entry_count)

      console.log(scope.selectedGroups)
      console.log(scope.selected_group_count)
    }
  }

  @JSExport
  def toggleSelectedGroups(group_index: Int) =
  {
    val string_id = "group" + group_index.toString
    if (__debug__) console.log(group_index)

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

    if (__debug__)
    {
      console.log(scope.selectedEntries)
      console.log(scope.selected_entry_count)

      console.log(scope.selectedGroups)
      console.log(scope.selected_group_count)
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
  def viewLinkedPerspective(
    group_index: Int,
    entry: LexicalEntry,
    field: Field,
    values: js.Array[Value]) =
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

    /* Updating dictionary table, if required. */

    val instance = modal.open[Seq[Entity]](options)
    instance.result map { entities =>
      entities.foreach(e => dictionary_table_seq(group_index).addEntity(entry, e))
    }
  }

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
    } recover {case e: Throwable => recover_with_log(e)}
  }

  /** Processes selection of a field used for entity matching. */
  @JSExport
  def field_selection(index: Int) =
  {
    if (__debug__)
    {
      console.log(index)
      console.log(scope.field_selection_list(index))
    }

    val field_selection = scope.field_selection_list(index)
    val field_index = field_selection.field_index.asInstanceOf[String].toInt

    field_selection.is_text =
      scope.field_data_list(field_index)._2.atoms.exists(a =>
        a.content == "Text" || a.content == "Grouping Tag")

    check_duplicates()
  }

  /** Selection of another field for entity matching. */
  @JSExport
  def add_field_selection() =
  {
    val field_selection: js.Dynamic = 

      js.Dynamic.literal(
        "field_index" -> "0",
        "duplicate" -> "",
        "is_text" -> scope.field_data_list(0)._2.atoms.exists(a =>
          a.content == "Text" || a.content == "Grouping Tag"),
        "ordinal_number" -> s"${scope.field_selection_list.length + 1}",
        "split_space" -> true,
        "split_punctuation" -> true,
        "levenshtein" -> 0)

    scope.field_selection_list :+= field_selection
    check_duplicates()
  }

  /** Removing an entity matching field selection. */
  @JSExport
  def remove_field_selection(index: Int) =
  {
    scope.field_selection_list.remove(index)
  }

  /** 
    * Checks if any selected fields are the same as previously selected fields, marks such fields as
    * duplicates.
    * 
    * Also checks if any field selection is not valid because of invalid Levenshtein distance threshold
    * specification.
    */
  @JSExport
  def check_duplicates() =
  {
    scope.field_selection_valid = true
    var selection_map: mutable.Map[String, mutable.Set[Int]] = mutable.Map()

    for ((field_selection, index) <-
      scope.field_selection_list.zipWithIndex)
    {
      /* If a field selection is invalid, we drop field selection validity flag. */

      if (!field_selection.levenshtein.isInstanceOf[Int])
      {
        field_selection.duplicate = ""
        scope.field_selection_valid = false
      }

      else
      {
        /* We check all field selections with valid data. */

        val selection_key: String = JSON.stringify(

          if (field_selection.is_text.asInstanceOf[Boolean])
            js.Dynamic.literal(
              "field_index" -> field_selection.field_index,
              "split_space" -> field_selection.split_space,
              "split_punctuation" -> field_selection.split_punctuation,
              "levenshtein" -> field_selection.levenshtein)

          else
            js.Dynamic.literal("field_index" -> field_selection.field_index))

        /* Checking if we've already seen such field selection, setting the selection's duplicate status. */

        val selection_set = selection_map.getOrElse(selection_key, mutable.Set())
        val selection_string = selection_set.toSeq.sorted.map(index => index + 1).mkString(", ")
        val mutiplicity_string = if (selection_set.size == 1) "" else "s"

        field_selection.duplicate = 
          if (selection_set.size <= 0) ""
          else s"Duplicate of field selection$mutiplicity_string $selection_string."

        selection_map(selection_key) = selection_set + index
      }
    }
  }

  load(() => {
    backend.perspectiveSource(perspectiveId) flatMap { sources =>

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

          /* Getting all non-link fields of the perspective. */

          def all_fields(field: Field): js.Array[Field] = {
            js.Array(field) ++ field.fields.flatMap(all_fields) }

          scope.field_data_list =
            js.Array(fields: _*).flatMap(all_fields)

            /* Matching data types to fields. */
            
            .map( field => {

              dataTypes.find(data_type =>
                data_type.clientId == field.dataTypeTranslationGistClientId &&
                data_type.objectId == field.dataTypeTranslationGistObjectId) match {

                case Some(data_type) => js.Tuple2(field, data_type)
                case None => throw new Exception("Unknown field data type.")}})

            /* Removing fields with link data type. */
              
            .filter( field_data =>

              field_data._2.atoms.forall(
                translation_atom => translation_atom.content != "Link"))

          /* Selecting first field for entity matching. */

          scope.field_selection_list = js.Array(js.Dynamic.literal(
            "field_index" -> "0",
            "duplicate" -> "",
            "is_text" -> scope.field_data_list(0)._2.atoms.exists(a =>
              a.content == "Text" || a.content == "Grouping Tag"),
            "ordinal_number" -> 1,
            "split_space" -> true,
            "split_punctuation" -> true,
            "levenshtein" -> 0))

          /* Checking if the user has create/delete permissions required to perform merges. */

          backend.mergePermissions(perspectiveId) map { merge_permissions =>
            scope.user_has_permissions = merge_permissions
            Future(())

          } recover { case e: Throwable => recover_with_log(e) }
        } recover { case e: Throwable => recover_with_log(e) }
      } recover { case e: Throwable => recover_with_log(e) }
    } recover { case e: Throwable => recover_with_log(e) }
  })

  override protected def onStartRequest(): Unit = {
    scope.pageLoaded = false
  }

  override protected def onCompleteRequest(): Unit = {
    scope.pageLoaded = true
  }

  /** Gets computed merge suggestions and initializes their rendering. */
  def get_merge_suggestions(
    perspectiveId: CompositeId,
    algorithm: String,
    field_selection_list: js.Array[js.Dynamic],
    threshold: Double): Unit =
  {
    backend.mergeSuggestions(
      perspectiveId, algorithm, field_selection_list, threshold)

    .map {
      case (entry_seq, match_seq, user_has_permissions) =>

      scope.user_has_permissions = user_has_permissions

      /* Computing lexical entry match graph. */

      adjacency_map = mutable.Map()
      weight_map = mutable.Map()

      for ((id_a, id_b, confidence) <- match_seq)
      {
        adjacency_map(id_a) = adjacency_map.getOrElse(id_a, mutable.Set()) + id_b
        adjacency_map(id_b) = adjacency_map.getOrElse(id_b, mutable.Set()) + id_a

        weight_map(id_a) = weight_map.getOrElse(id_a, 0.0) + confidence / 2
        weight_map(id_b) = weight_map.getOrElse(id_b, 0.0) + confidence / 2
      }

      /* Grouping lexical entries into mutually matching groups. */

      group_seq = mutable.Seq()
      group_map = mutable.Map()

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

      /* Setting up lexical entry group data for rendering. */

      val entry_map = Map(
        entry_seq map { entry => (CompositeId(entry.clientId, entry.objectId) -> entry) }: _*)

      dictionary_table_seq =
        group_seq .zipWithIndex .map { case (group, index) =>
          DictionaryTable.build(fields, dataTypes,
            group.toSeq.sorted.map { entry_id => entry_map(entry_id) }, Some(index)) }

      table_group_array = dictionary_table_seq
        .grouped(scope.pageSize)
        .map { table_seq => js.Array(table_seq: _*) }
        .toArray

      scope.result_count = group_seq.length

      scope.pageCount = table_group_array.length
      scope.pageNumber = 1

      scope.dictionaryTables = {
        if (scope.pageNumber - 1 < table_group_array.length)
          table_group_array(scope.pageNumber - 1)
        else js.Array() }

      /* Setting up tracking of selection of lexical entry groups. */

      for (entry_id <- adjacency_map.keys)
        scope.selectedEntries(entry_id.getId) = entry_id.getId

      scope.selected_entry_count = adjacency_map.size

      for (group_index <- 0 until group_seq.length)
        scope.selectedGroups("group" + group_index.toString) = group_index

      scope.selected_group_count = group_seq.length

      /* 
       * Dropping indication of loading of merge suggestions.
       *
       * NOTE:
       *
       * This indication is initialized in the method compute_merge_suggestions(). Such separation of
       * initialization and deinitialization is bad, but we have to do it, as otherwise deinitialization
       * happens immediately, and it should happend only on completion of mergeSuggestions() request, either
       * successful or unsuccessful.
       */

      scope.suggestionsLoading = false
    }

    .recover {
      case e: Throwable =>

      scope.suggestionsLoading = false
      recover_with_log(e)
    }
  }

  /** Computes and shows merge suggestions. */
  @JSExport
  def compute_merge_suggestions(): Unit =
  {
    scope.suggestionsLoading = true

    if (__debug__)
    {
      console.log("compute_merge_suggestions")
      console.log(scope.algorithm)
    }

    if (scope.algorithm == "simple")

      get_merge_suggestions(perspectiveId,
        "simple", js.Array(), scope.threshold.toDouble)

    /* Merge suggestions based on a set of selected fields. */

    else if (scope.algorithm == "fields")
    {
      if (__debug__)
        console.log(JSON.stringify(scope.field_selection_list))

      val field_selection_list: js.Array[js.Dynamic] = js.Array(
        scope.field_selection_list

        /* Skipping duplicates. */

        .filter { field_selection =>
          field_selection.duplicate.asInstanceOf[String].length <= 0 }
        
        .map { field_selection => {

          val field_data_type = scope.field_data_list(
            field_selection.field_index.asInstanceOf[String].toInt)

          val field = field_data_type._1
          val data_type = field_data_type._2

          /* Getting match type of the selected field. */

          val match_type =
          {
            if (data_type.atoms.exists(a =>
              a.content == "Text" || a.content == "Grouping Tag")) "text"

            else if (data_type.atoms.exists(a =>
              a.content == "Link")) "link"

            else if (data_type.atoms.exists(a =>
              a.content == "Image" || a.content == "Markup" || a.content == "Sound")) "hash"

            else throw new Exception("Unknown field data type.")
          }

          /* Compiling info of either discrete or text field. */

          if (!field_selection.is_text.asInstanceOf[Boolean])
            js.Dynamic.literal(
              "client_id" -> field.clientId,
              "object_id" -> field.objectId,
              "type" -> match_type)

          else
            js.Dynamic.literal(
              "client_id" -> field.clientId,
              "object_id" -> field.objectId,
              "levenshtein" -> field_selection.levenshtein,
              "split_space" -> field_selection.split_space,
              "split_punctuation" -> field_selection.split_punctuation,
              "type" -> match_type)

        }}: _*)

      if (__debug__)
        console.log(JSON.stringify(field_selection_list))

      /* Getting merge suggestions data. */

      get_merge_suggestions(perspectiveId,
        "fields", field_selection_list, scope.threshold.toDouble)
    }

    else throw new Exception(
      s"Unknown entity matching algorithm '$scope.algorithm'.")
  }

  /** Performs merge of selected entry groups. */
  @JSExport
  def performMerge(): Unit =
  {
    if (__debug__)
      console.log("performMerge")

    val selected_seq = Seq({

      for ((group_set, group_index) <- group_seq.zipWithIndex
        if scope.selectedGroups.contains("group" + group_index.toString))

          yield Seq(group_set.toSeq.sorted: _*).filter(
            entry_id => scope.selectedEntries.contains(entry_id.getId))}: _*)

    if (__debug__)
    {
      console.log(selected_seq.length)
      console.log(selected_seq.toString)

      console.log("publish_merge_mode: " + scope.publishMergeMode)
    }

    backend.mergeBulk(
      scope.publishMergeMode == "any",
      selected_seq)

      .map { entry_id_seq => () }
      .recover { case e: Throwable => recover_with_log(e) }
  }

  override protected def onOpen(): Unit = {}

  override protected def onClose(): Unit = {
    waveSurfer foreach {w =>
      w.destroy()}
  }
}

