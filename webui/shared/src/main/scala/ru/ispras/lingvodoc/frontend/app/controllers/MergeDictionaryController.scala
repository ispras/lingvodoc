
package ru.ispras.lingvodoc.frontend.app.controllers


import com.greencatsoft.angularjs.core._
import com.greencatsoft.angularjs.extensions.{ModalOptions, ModalService}
import com.greencatsoft.angularjs.{AngularExecutionContextProvider, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseController
import ru.ispras.lingvodoc.frontend.app.controllers.common._
import ru.ispras.lingvodoc.frontend.app.controllers.traits.{SimplePlay, Tools, ViewMarkup}
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

  /** Number of matching entry groups found by selected merge suggestion algorithm. */
  var result_count: Int = js.native

  /** Number of merged matching entry groups. */
  var merged_count: Int = js.native

  /** Data of matching lexical entries. */
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

  /** Indices of currently selected lexical entry groups, with corresponding dictionary table and table page
   *  indices. */
  var selectedGroups: js.Dictionary[(Int, Int, Int)] = js.native

  /** Number of currently selected lexical entry groups, should always be exactly Object.keys(
    * selectedGroups).length. */
  var selected_group_count: Int = js.native

  /** Is set to true if the user has create/delete permissions required to perform suggested merges, and to
    * false otherwise. */
  var user_has_permissions: Boolean = js.native

  var pageLoaded: Boolean = js.native
  var loading: Boolean = js.native
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
    with ViewMarkup
    with Tools {

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

  /** Mapping from lexical entries to matching entry groups. */
  private[this] var entry_group_map: mutable.Map[CompositeId, Int] = mutable.Map()

  /** Mapping from entry group ids to sets of lexical entry ids. */
  private[this] var group_entry_map: mutable.Map[Int, mutable.Set[CompositeId]] = mutable.Map()

  private[this] var dictionary_table_seq: mutable.Seq[DictionaryTable] = mutable.Seq()

  private[this] var table_group_array: mutable.ArrayBuffer[js.Array[DictionaryTable]] =
    mutable.ArrayBuffer()

  scope.algorithm = "simple"

  scope.field_data_list = js.Array()
  scope.field_selection_list = js.Array()
  scope.field_selection_valid = true
  scope.threshold = "0.1"

  scope.pageSize = 10
  scope.pageCount = -1
  scope.pageNumber = -1

  scope.result_count = -1
  scope.merged_count = 0

  scope.publishMergeMode = "any"

  scope.selectedEntries = js.Dictionary[String]()
  scope.selected_entry_count = 0

  scope.selectedGroups = js.Dictionary[(Int, Int, Int)]()
  scope.selected_group_count = 0

  scope.user_has_permissions = false

  scope.pageLoaded = false
  scope.loading = false

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

  /** Selects entry group page. */
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
  def toggleSelectedEntries(client_id: Int, object_id: Int, table_index: Int) =
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

    val group_index = entry_group_map(composite_id)
    var entry_count = 0

    for (entry_id <- group_entry_map(group_index).toSeq.sorted)
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

      scope.selectedGroups(group_string_id) = (group_index, table_index, scope.pageNumber - 1)
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
  def toggleSelectedGroups(group_index: Int, table_index: Int) =
  {
    val string_id = "group" + group_index.toString

    if (__debug__)
      console.log(group_index)

    if (scope.selectedGroups.contains(string_id))
    {
      /* Group is selected, we deselect the whole group. */

      scope.selectedGroups.delete(string_id)
      scope.selected_group_count -= 1

      for (entry_id <- group_entry_map(group_index))
        if (scope.selectedEntries.contains(entry_id.getId))
        {
          scope.selectedEntries.delete(entry_id.getId)
          scope.selected_entry_count -= 1
        }
    }
    else
    {
      /* Group is not selected, we select the whole group. */

      scope.selectedGroups(string_id) = (group_index, table_index, scope.pageNumber - 1)
      scope.selected_group_count += 1

      for (entry_id <- group_entry_map(group_index))
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

  /** 
   *  Opens view of a linked perpective, differs from the method with the same in LinkEntities by absense of
   *  markedForDeletion filtration and absense of processing of modal page results.
   */
  @JSExport
  def viewLinkedPerspective(
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
          dictionaryId = dictionaryId.asInstanceOf[js.Object],
          perspectiveId = perspectiveId.asInstanceOf[js.Object],
          lexicalEntry = entry.asInstanceOf[js.Object],
          field = field.asInstanceOf[js.Object],
          entities = values.map { _.getEntity() }
        )
      }
    ).asInstanceOf[js.Dictionary[Any]]

    val instance = modal.open[Seq[Entity]](options)
    instance.result map { _ => }
  }

  @JSExport
  def viewGroupingTag(entry: LexicalEntry, field: Field, values: js.Array[Value]) =
  {
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
          values = values.asInstanceOf[js.Object],
          edit = false
        )
      }
    ).asInstanceOf[js.Dictionary[Any]]

    val instance = modal.open[Unit](options)
    instance.result map { _ => }
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

      /* Gathers entries belonging to a specified entry group. */

      var group_seq: mutable.Seq[mutable.Set[CompositeId]] = mutable.Seq()

      def df_search(entry_id: CompositeId, group_index: Int): Unit =
      {
        if (entry_group_map.contains(entry_id))
          return

        group_seq.last += entry_id
        entry_group_map(entry_id) = group_index

        for (id <- adjacency_map(entry_id))
          df_search(id, group_index)
      }

      /* Grouping lexical entries into mutually matching groups. */

      entry_group_map = mutable.Map()

      for (entry_id <- adjacency_map.keys.toSeq.sorted)
        if (!entry_group_map.contains(entry_id))
        {
          group_seq :+= mutable.Set()
          df_search(entry_id, group_seq.length - 1)
        }

      group_entry_map = mutable.Map(
        group_seq .zipWithIndex .map { case (entry_id_set, group_index) =>
          group_index -> entry_id_set }: _*)

      /* Setting up lexical entry group data for rendering. */

      val entry_map = Map(
        entry_seq map { entry => (CompositeId(entry.clientId, entry.objectId) -> entry) }: _*)

      dictionary_table_seq =
        group_seq .zipWithIndex .map { case (group, index) =>
          DictionaryTable.build(fields, dataTypes,
            group.toSeq.sorted.map { entry_id => entry_map(entry_id) }, Some(index)) }

      table_group_array = mutable.ArrayBuffer(
        dictionary_table_seq
          .grouped(scope.pageSize)
          .map { table_seq => js.Array(table_seq: _*) }
          .toSeq: _*)

      scope.result_count = group_seq.length
      scope.merged_count = 0

      scope.pageCount = table_group_array.length
      scope.pageNumber = 1

      scope.dictionaryTables = {
        if (scope.pageNumber - 1 < table_group_array.length)
          table_group_array(scope.pageNumber - 1)
        else js.Array() }

      /* Setting up tracking of selection of lexical entry groups. */

      scope.selectedEntries = js.Dictionary[String]()
      scope.selected_entry_count = 0

      scope.selectedGroups = js.Dictionary[(Int, Int, Int)]()
      scope.selected_group_count = 0

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

      scope.loading = false
    }

    .recover {
      case e: Throwable =>

      scope.loading = false
      recover_with_log(e)
    }
  }

  /** Computes and shows merge suggestions. */
  @JSExport
  def compute_merge_suggestions(): Unit =
  {
    if (__debug__)
      console.log("compute_merge_suggestions")

    if (scope.loading)
      return

    scope.loading = true

    if (__debug__)
      console.log(scope.algorithm)

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

  /** Shows message notifying the user about asynchronous merge. */
  def async_merge_message()
  {
    val options = ModalOptions()

    options.templateUrl = "/static/templates/modal/message.html"
    options.controller = "MessageController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"

    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          "title" -> "Merge task launched",

          "message" -> """
            |<p>Due to large number of affected lexical entries a merge process was launched as a 
            |background task, see the "Tasks" menu for details. 
            |
            |<p>Please refrain from computing new merge suggestions or editing the perspective until the 
            |merge task is finished. It is safe to continue working with current merge suggestions and to 
            |view the perspective.""".stripMargin
        )
      }
    ).asInstanceOf[js.Dictionary[Any]]

    modal.open[Unit](options)
  }

  /** Performs merge of all selected entry groups. */
  @JSExport
  def merge_all(): Unit =
  {
    if (__debug__)
      console.log("merge_all")

    if (!scope.user_has_permissions || scope.selected_group_count <= 0 || scope.loading)
      return

    /* Gathering groups selections. */

    var selected_group_map = mutable.Map[Int, mutable.Seq[(Int, Int)]]()

    val selected_seq = Seq(
      scope.selectedGroups .values .toSeq .map {
        
      case (group_index, table_index, page_index) =>

        if (!selected_group_map.contains(page_index))
          selected_group_map(page_index) = mutable.Seq()

        selected_group_map(page_index) :+= (table_index, group_index)

        Seq(group_entry_map(group_index) .toSeq .sorted: _*).filter(
          entry_id => scope.selectedEntries.contains(entry_id.getId))

      }: _*)

    if (__debug__)
    {
      console.log(selected_seq.length)
      console.log(selected_seq.toString)

      console.log("publish_merge_mode: " + scope.publishMergeMode)
    }

    /* Removes selected entry groups. */

    def remove_selected_groups() =
    {
      var current_page_index = scope.pageNumber - 1
      var page_remove_count = 0

      /* Going through all pages with at least one merged entry group in order of page numbers. */

      for ((page_index, selected_group_seq) <- selected_group_map .toSeq .sortBy {
        case (page_index, selected_group_seq) => page_index })
      {
        val table_group = table_group_array(page_index - page_remove_count)
        var table_remove_count = 0

        for ((table_index, group_index) <- selected_group_seq .sorted)
        {
          table_group.remove(table_index - table_remove_count)
          table_remove_count += 1

          /* De-selecting entries of the merged group. */

          for (entry_id <- group_entry_map(group_index))
            if (scope.selectedEntries.contains(entry_id.getId))
            {
              scope.selectedEntries.delete(entry_id.getId)
              scope.selected_entry_count -= 1
            }

          scope.merged_count += 1
        }

        /* If we've removed all groups from the current page, we delete it. */

        if (table_group.length <= 0)
        {
          table_group_array.remove(page_index - page_remove_count)

          if (page_index - page_remove_count < current_page_index)
            current_page_index -= 1

          page_remove_count += 1
        }
      }

      /* De-selecting merged groups, re-setting current page if required. */

      scope.selectedGroups = js.Dictionary[(Int, Int, Int)]()
      scope.selected_group_count = 0

      if (page_remove_count > 0 && table_group_array.length > 0)
        getPage(((current_page_index + 1) min table_group_array.length) max 1)
    }

    /* Low enough number of lexical entries to merge, using synchronous merge. */

    if (scope.selected_entry_count <= 100)
    {
      scope.loading = true

      backend.mergeBulk(
        scope.publishMergeMode == "any",
        selected_seq)

      .map { _ =>
        remove_selected_groups()
        scope.loading = false }

      .recover { case e: Throwable =>
        scope.loading = false
        recover_with_log(e) }
    }

    /* Large number of lexical entries to merge, launching asynchronous merge. */

    else
    
      backend.mergeBulkAsync(
        scope.publishMergeMode == "any",
        selected_seq)

      .map { _ =>
        remove_selected_groups()
        async_merge_message() }

      .recover { case e: Throwable => recover_with_log(e) }
  }

  override protected def onOpen(): Unit = {}

  override protected def onClose(): Unit = {
    waveSurfer foreach {w =>
      w.destroy()}
  }

  /** Merges all selected entry groups on the current page. */
  @JSExport
  def merge_all_page(): Unit =
  {
    if (__debug__)
      console.log("merge_all_page")

    if (!scope.user_has_permissions || scope.loading)
      return

    /* Gathering entries selected for a merge. */

    var selected_group_seq = mutable.Seq[(Int, Int)]()
    var selected_entry_count = 0

    val selected_seq = Seq(
      scope.dictionaryTables .zipWithIndex .flatMap {

        case (dictionary_table, table_index) =>
          val group_index = dictionary_table.tag.asInstanceOf[Int]

          if (scope.selectedGroups.contains("group" + group_index.toString))
          {
            /* For each selected group we remember its index, its position in the table and the number of
             * its selected entries. */

            selected_group_seq :+= (group_index, table_index)

            val entry_id_seq = Seq(
              group_entry_map(group_index) .toSeq .sorted: _*)
                .filter(entry_id => scope.selectedEntries.contains(entry_id.getId))

            selected_entry_count += entry_id_seq.length
            Some(entry_id_seq)
          }

          else None

      }: _*)

    if (selected_seq.length <= 0)
      return

    /* Removes selected entry groups. */

    def remove_selected_groups() =
    {
      var remove_count = 0

      for ((group_index, table_index) <- selected_group_seq)
      {
        scope.dictionaryTables.remove(table_index - remove_count)
        remove_count += 1

        /* De-selecting removed group. */

        scope.selectedGroups.delete("group" + group_index.toString)
        scope.selected_group_count -= 1

        for (entry_id <- group_entry_map(group_index))
          if (scope.selectedEntries.contains(entry_id.getId))
          {
            scope.selectedEntries.delete(entry_id.getId)
            scope.selected_entry_count -= 1
          }

        scope.merged_count += 1
      }

      /* If we've removed all groups from the current page, we delete it. */

      if (scope.dictionaryTables.length <= 0)
      {
        table_group_array.remove(scope.pageNumber - 1)
        getPage(scope.pageNumber min table_group_array.length)
      }
    }

    /* Low enough number of lexical entries to merge, using synchronous merge. */

    if (selected_entry_count <= 100)
    {
      scope.loading = true

      backend.mergeBulk(
        scope.publishMergeMode == "any",
        selected_seq)

      .map { _ =>
        remove_selected_groups()
        scope.loading = false }

      .recover { case e: Throwable =>
        scope.loading = false
        recover_with_log(e) }
    }

    /* Large number of lexical entries to merge, launching asynchronous merge. */

    else
    
      backend.mergeBulkAsync(
        scope.publishMergeMode == "any",
        selected_seq)

      .map { _ =>
        remove_selected_groups()
        async_merge_message() }

      .recover { case e: Throwable => recover_with_log(e) }
  }

  /** Merges specified group. */
  @JSExport
  def merge_group(group_index: Int, table_index: Int): Unit =
  {
    if (__debug__)
      console.log("merge_group")

    if (!scope.user_has_permissions)
      return

    /* Gathering entries selected for a merge. */

    val string_id = "group" + group_index.toString

    if (!scope.selectedGroups.contains(string_id))
      return

    val selected_seq = Seq(
      Seq(group_entry_map(group_index) .toSeq .sorted: _*).filter(
        entry_id => scope.selectedEntries.contains(entry_id.getId)))

    /* Performing merge. */
      
    scope.loading = true

    backend.mergeBulk(
      scope.publishMergeMode == "any",
      selected_seq)

    .map {
      entry_id_seq =>

      /* Removing merged group if the merge finished successfully. */

      scope.dictionaryTables.remove(table_index)

      scope.selectedGroups.delete(string_id)
      scope.selected_group_count -= 1

      for (entry_id <- group_entry_map(group_index))
        if (scope.selectedEntries.contains(entry_id.getId))
        {
          scope.selectedEntries.delete(entry_id.getId)
          scope.selected_entry_count -= 1
        }

      scope.merged_count += 1

      /* If we've removed all groups from the current page, we delete it. */

      if (scope.dictionaryTables.length <= 0)
      {
        table_group_array.remove(scope.pageNumber - 1)
        getPage(scope.pageNumber min table_group_array.length)
      }

      scope.loading = false
    }

    .recover { case e: Throwable =>
      scope.loading = false
      recover_with_log(e) }
  }

  /** Selects all entries of all groups. */
  @JSExport
  def select_all() =
  {
    for ((group_array, page_index) <- table_group_array .zipWithIndex)
      for ((dictionary_table, table_index) <- group_array .zipWithIndex)
      {
        val group_index = dictionary_table.tag.asInstanceOf[Int]
        val string_id = "group" + group_index.toString

        /* Ensuring that each group is selected. */

        scope.selectedGroups(string_id) = (group_index, table_index, page_index)

        for (entry_id <- group_entry_map(group_index))
          scope.selectedEntries(entry_id.getId) = entry_id.getId
      }

    scope.selected_entry_count = scope.selectedEntries.size
    scope.selected_group_count = scope.selectedGroups.size
  }

  /** De-selects all entries of all groups. */
  @JSExport
  def deselect_all() =
  {
    scope.selectedEntries = js.Dictionary[String]()
    scope.selected_entry_count = 0

    scope.selectedGroups = js.Dictionary[(Int, Int, Int)]()
    scope.selected_group_count = 0
  }

  /** Selects all entries of all groups on the current page. */
  @JSExport
  def select_all_page() =
  {
    for ((dictionary_table, table_index) <- scope.dictionaryTables .zipWithIndex)
    {
      val group_index = dictionary_table.tag.asInstanceOf[Int]
      val string_id = "group" + group_index.toString

      if (!scope.selectedGroups.contains(string_id))
      {
        /* If a group is not selected, we select it and ensure that all its entries are selected too. */

        scope.selectedGroups(string_id) = (group_index, table_index, scope.pageNumber - 1)
        scope.selected_group_count += 1

        for (entry_id <- group_entry_map(group_index))
          if (!scope.selectedEntries.contains(entry_id.getId))
          {
            scope.selectedEntries(entry_id.getId) = entry_id.getId
            scope.selected_entry_count += 1
          }
      }
    }
  }

  /** De-selects all entries of all groups on the current page. */
  @JSExport
  def deselect_all_page() =
  {
    for (dictionary_table <- scope.dictionaryTables)
    {
      val group_index = dictionary_table.tag.asInstanceOf[Int]
      val string_id = "group" + group_index.toString

      if (scope.selectedGroups.contains(string_id))
      {
        /* If a group is selected, we deselect it and ensure that all its entries are deselected too. */

        scope.selectedGroups.delete(string_id)
        scope.selected_group_count -= 1

        for (entry_id <- group_entry_map(group_index))
          if (scope.selectedEntries.contains(entry_id.getId))
          {
            scope.selectedEntries.delete(entry_id.getId)
            scope.selected_entry_count -= 1
          }
      }
    }
  }
}

