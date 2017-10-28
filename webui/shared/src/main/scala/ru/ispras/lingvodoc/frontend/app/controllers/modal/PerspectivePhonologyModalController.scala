
package ru.ispras.lingvodoc.frontend.app.controllers.modal


/* External imports. */

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.{ModalInstance, ModalOptions, ModalService}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}

import org.scalajs.dom.console

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.UndefOr
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}

/* Lingvodoc imports. */

import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseModalController
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services._


@js.native
trait PerspectivePhonologyModalScope extends Scope
{
  var error: UndefOr[Throwable] = js.native

  /** Phonology data source, either "all" for all vowels or "selected" for only logest vowels and vowels
   *  with highest intensity. */
  var source: String = js.native

  /** If we should group phonology data by markup descriptions. */
  var group_by_description: Boolean = js.native

  /** Fields which can be selected as a translation field. */
  var text_field_list: js.Array[Field] = js.native

  /** Identifier of the field selected as a translation field. */
  var translation_field_id: String = js.native

  /** If we should show only first translation ('first') or all available translations ('all') of each
   *  word. */
  var translation_choice: String = js.native

  /** If we should provide markup tier choice. */
  var tier_choice: Boolean = js.native

  /** If the markup tier names are being loaded. */
  var tier_loading: Boolean = js.native
  
  /** If the markup tier names were successfully loaded. */
  var tier_loaded: Boolean = js.native

  /** List of phonology markup tier names. */
  var tier_list: js.Array[String] = js.native

  /** Percentages of markup records each markup tier is present at. */
  var tier_percentage: js.Dictionary[String] = js.native

  /** Names of selected markup tiers. */
  var selected_tiers: js.Dictionary[String] = js.native

  /** Number of selected markup tiers. */
  var selected_tier_count: Int = js.native
}


@injectable("PerspectivePhonologyModalController")
class PerspectivePhonologyModalController(
  scope: PerspectivePhonologyModalScope,
  val modal: ModalService,
  instance: ModalInstance[Unit],
  backend: BackendService,
  timeout: Timeout,
  val exceptionHandler: ExceptionHandler,
  params: js.Dictionary[js.Function0[js.Any]])

  extends BaseModalController(scope, modal, instance, timeout, params)
    with AngularExecutionContextProvider {

  private[this] val __debug__ = false

  private[this] val perspectiveId = params("perspectiveId").asInstanceOf[CompositeId]
  private[this] val text_field_list = params("text_field_list").asInstanceOf[Seq[Field]]

  private[this] var tier_loading = false

  /* By default we extract phonology data from all vowels. */
  scope.source = "all"

  /* By default we do not group phonology data by markup descriptions. */
  scope.group_by_description = false

  scope.text_field_list = js.Array[Field](text_field_list: _*)
  scope.translation_field_id = ""

  /* Setting up default translation field. */

  if (text_field_list.length > 0)
  {
    val id_list =

      text_field_list flatMap { field =>
        "(?i)translation".r.findFirstMatchIn(field.translation) match {
          case Some(_) => Some(field.getId)
          case None => None }}

    scope.translation_field_id = id_list(0)
  }

  /* By default we show all available translations. */
  scope.translation_choice = "all"

  /* By default we use all markup tiers. */
  scope.tier_choice = false

  scope.tier_loading = false
  scope.tier_loaded = false
  scope.tier_list = js.Array[String]()

  scope.selected_tiers = js.Dictionary[String]()
  scope.selected_tier_count = 0

  /** Enables or disables tier choice selection. */
  @JSExport
  def tier_choice_change(): Unit =
  {
    if (!scope.tier_loading && !scope.tier_loaded)
    {
      scope.tier_loading = true

      /* Loading tier names only if we are not currently loading or haven't already loaded them. */

      backend.phonologyTierList(perspectiveId)

      .map {
        case (total_count, tier_count) =>

          scope.tier_loading = false
          scope.tier_loaded = true

          scope.tier_list = js.Array[String](
            tier_count .keys .toSeq .sortBy {
              case tier => (tier.toLowerCase, tier) }: _*)

          /* Computing tier presence percentages, selecting all loaded tiers. */

          scope.tier_percentage = js.Dictionary[String](
            tier_count .toSeq .map { case (tier, count) =>
              tier -> f"${count * 100.0 / total_count}%.1f%%" }: _*)
        
          scope.selected_tiers = js.Dictionary[String](
            scope.tier_list .map { tier => (tier, tier) }: _*)

          scope.selected_tier_count = scope.tier_list.length
        }

      .recover { case e: Throwable => setError(e) }
    }
  }

  /** Changes selection state of a phonology markup tier. */
  @JSExport
  def toggleTierSelection(tier: String)
  {
    if (scope.selected_tiers.contains(tier))
    {
      scope.selected_tiers.delete(tier)
      scope.selected_tier_count -= 1
    }

    else
    {
      scope.selected_tiers(tier) = tier
      scope.selected_tier_count += 1
    }

    console.log(scope.selected_tiers)
  }

  /** Processes selection of a translation field. */
  @JSExport
  def select_field(field_id: String): Unit =
  {
    scope.translation_field_id = field_id
  }

  /** Launches phonology generation. */
  @JSExport
  def generate(): Unit =
  {
    /* Getting translation field identifier, if we have one. */

    val maybe_translation_field: Option[CompositeId] =
    
      if (text_field_list.length > 0)
      {
        val id_list = 

          text_field_list flatMap { field =>
            if (field.getId == scope.translation_field_id)
              Some(CompositeId.fromObject(field)) else None }

        Some(id_list(0))
      }
      else None

    /* Getting list of markup tiers to look at, if required. */

    val maybe_tier_list =
    {
      if (scope.tier_choice)
        Some(scope.selected_tiers.keys.toSeq.sorted)
      else
        None
    }

    /* Trying to launch phonology compilation. */

    backend.phonology(perspectiveId,
      scope.group_by_description,
      maybe_translation_field,
      scope.translation_choice == "first",
      scope.source == "selected",
      maybe_tier_list)
    
    .map {
      blob =>

        /* Closing phonology options modal page. */

        instance.dismiss(())

        /* And showing a message about successfully launched phonology computation. */

        val options = ModalOptions()

        options.templateUrl = "/static/templates/modal/message.html"
        options.windowClass = "sm-modal-window"
        options.controller = "MessageController"
        options.backdrop = false
        options.keyboard = false
        options.size = "lg"

        options.resolve = js.Dynamic.literal(
          params = () => {
            js.Dynamic.literal(
              "title" -> "",
              "message" -> "Background task created. Check tasks menu for details."
            )
          }
        ).asInstanceOf[js.Dictionary[Any]]

        modal.open[Unit](options)
    }
    
    .recover { case e: Throwable => setError(e) }
  }

  @JSExport
  def close(): Unit =
  {
    instance.dismiss(())
  }

  private[this] def setError(e: Throwable) =
  {
    scope.error = e
  }

  load(() => Future[Unit](()))

  override protected def onStartRequest(): Unit = {}

  override protected def onCompleteRequest(): Unit = {}
}

