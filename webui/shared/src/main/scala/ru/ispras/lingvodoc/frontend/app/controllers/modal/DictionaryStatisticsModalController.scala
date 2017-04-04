
package ru.ispras.lingvodoc.frontend.app.controllers.modal


/* External imports. */

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.{ModalInstance, ModalService}
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
trait DictionaryStatisticsModalScope extends Scope
{
  var error: UndefOr[Throwable] = js.native

  /** String representation of the starting date/time of the statistics gathering period. */
  var from_string: UndefOr[String] = js.native

  /** String representation of the ending date/time of the statistics gathering period. */
  var to_string: UndefOr[String] = js.native

  /** Gathered statistical data. */
  var statistics_data: UndefOr[js.Array[js.Dictionary[js.Object]]] = js.native
}


@injectable("DictionaryStatisticsModalController")
class DictionaryStatisticsModalController(
  scope: DictionaryStatisticsModalScope,
  val modal: ModalService,
  instance: ModalInstance[Unit],
  backend: BackendService,
  timeout: Timeout,
  val exceptionHandler: ExceptionHandler,
  params: js.Dictionary[js.Function0[js.Any]])

  extends BaseModalController(scope, modal, instance, timeout, params)
    with AngularExecutionContextProvider {

  private[this] val __debug__ = false
  private[this] val datetime_re = """(\d\d\d\d)-(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d)""".r

  private[this] val dictionaryId = params("dictionaryId").asInstanceOf[CompositeId]

  /** Starting date/time of the statistics gathering period. */
  private[this] var from_date_time: js.Date = new js.Date(js.Date.now())
  
  from_date_time.setDate(1)
  from_date_time.setHours(0)
  from_date_time.setMinutes(0)
  from_date_time.setSeconds(0)

  /** Ending date/time of the statistics gathering period. */
  private[this] var to_date_time: js.Date = new js.Date(js.Date.now())

  /* Initializing starting and ending datetime as the current datetime. */

  scope.from_string = date_to_string(from_date_time)
  scope.to_string = date_to_string(to_date_time)

  scope.statistics_data = Option.empty[js.Array[js.Dictionary[js.Object]]].orUndefined

  /** Transforms js.Date into a date/time's string representation in a "YYYY-MM-DD hh:mm:ss" format. */
  def date_to_string(date_time: js.Date, separator: String = " "): String =
  {
    f"""
      |${date_time.getFullYear()}%04d-
      |${date_time.getMonth() + 1}%02d-
      |${date_time.getDate()}%02d
      |$separator
      |${date_time.getHours()}%02d:
      |${date_time.getMinutes()}%02d:
      |${date_time.getSeconds()}%02d""".stripMargin.replaceAll("\n", "")
  }

  /** Transforms js.Date into a corresponding UTC date/time's string representation in a
    * "YYYY-MM-DD hh:mm:ss" format. */
  def date_to_utc_string(date_time: js.Date, separator: String = " "): String =
  {
    f"""
      |${date_time.getUTCFullYear()}%04d-
      |${date_time.getUTCMonth() + 1}%02d-
      |${date_time.getUTCDate()}%02d
      |$separator
      |${date_time.getUTCHours()}%02d:
      |${date_time.getUTCMinutes()}%02d:
      |${date_time.getUTCSeconds()}%02d""".stripMargin.replaceAll("\n", "")
  }

  /** Transforms date/time's string representation in a "YYYY-MM-DD hh:mm:ss" format into a js.Date. */
  def string_to_date(string: String): js.Date =
  {
    string match {
      case datetime_re(year, month, day, hour, minute, second) =>

        new js.Date(
          year.toInt, month.toInt - 1, day.toInt,
          hour.toInt, minute.toInt, second.toInt) }
  }

  /** Parses starting datetime of the statistics gathering period. */
  @JSExport
  def change_from(): Unit =
  {
    if (__debug__)
    {
      console.log(scope.from_string.isEmpty)
      console.log(scope.from_string)
      console.log(from_date_time.toString)
    }

    /* Parsing datetime string only if it in a valid format. */

    if (scope.from_string.isEmpty)
      return

    scope.from_string.get match {
      case datetime_re(year, month, day, hour, minute, second) =>

        from_date_time = new js.Date(
          year.toInt, month.toInt - 1, day.toInt,
          hour.toInt, minute.toInt, second.toInt)

        /* Resetting datetime string so that it matches parsed datetime. Required when, e.g., user inputs
         * more than 59 seconds/minutes, or more than 23 hours, etc. */

        if (__debug__)
        {
          console.log((year, month, day, hour, minute, second).toString)
          console.log(from_date_time.toString)
        }

        scope.from_string = date_to_string(from_date_time) }
  }

  /** Parses starting datetime of the statistics gathering period. */
  @JSExport
  def change_to(): Unit =
  {
    if (__debug__)
    {
      console.log(scope.to_string.isEmpty)
      console.log(scope.to_string)
      console.log(to_date_time.toString)
    }

    /* Parsing datetime string only if it in a valid format. */

    if (scope.to_string.isEmpty)
      return

    val datetime_re = """(\d\d\d\d)-(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d)""".r

    scope.to_string.get match {
      case datetime_re(year, month, day, hour, minute, second) =>

        to_date_time = new js.Date(
          year.toInt, month.toInt - 1, day.toInt,
          hour.toInt, minute.toInt, second.toInt)

        /* Resetting datetime string so that it matches parsed datetime. Required when, e.g., user inputs
         * more than 59 seconds/minutes, or more than 23 hours, etc. */

        if (__debug__)
        {
          console.log((year, month, day, hour, minute, second).toString)
          console.log(to_date_time.toString)
        }

        scope.to_string = date_to_string(to_date_time) }
  }

  /** Prepares dictionary key sequence, ensures that the keys are in alphabetical order and the
    * 'total' key is last. */
  def sorted_keys_total_last(key_set: scala.collection.Set[String]): Seq[String] =
  {
    if (key_set.contains("total"))
      (key_set - "total") .toSeq .sorted :+ "total"
    else
      key_set .toSeq .sorted
  }

  /** Gathers user participation statistics for a specified period, prepares it for rendering. */
  @JSExport
  def gather(): Unit =
  {
    if (__debug__)
    {
      console.log(date_to_utc_string(from_date_time, "t"))
      console.log(date_to_utc_string(to_date_time, "t"))
    }

    /* Requesting statistics. */

    backend.dictionaryStatistics(dictionaryId,
      date_to_utc_string(from_date_time, "t"),
      date_to_utc_string(to_date_time, "t"))

    .map {
      case statistics_data =>
    
        scope.statistics_data = js.Array(statistics_data .values .toSeq

          /* Sorting users' statistics by user names and logins, preparing it for rendering. */
          
          .sortBy { user_data =>
            (user_data("name").asInstanceOf[String], user_data("login").asInstanceOf[String]) }

          .map { user_data =>

            if (user_data.contains("lexical entries"))
            {
              val entry_data = user_data("lexical entries")
                .asInstanceOf[js.Dictionary[js.Dictionary[Int]]]

              var entry_table_data: js.Array[js.Array[String]] = js.Array()

              /* Grouping lexical entry statistics by perspective state, organizing it for table display. */

              for (perspective_state <- sorted_keys_total_last(entry_data.keySet))
              {
                val perspective_state_data = entry_data(perspective_state).asInstanceOf[js.Dictionary[Int]]

                entry_table_data.append(js.Array(perspective_state,
                  perspective_state_data("desktop").toString,
                  perspective_state_data("web").toString,
                  perspective_state_data("total").toString))
              }

              user_data.put("entry_table", entry_table_data)
            }

            if (user_data.contains("entities"))
            {
              val entity_data = user_data("entities")
                .asInstanceOf[js.Dictionary[js.Dictionary[js.Dictionary[js.Dictionary[Int]]]]]

              var entity_table_data: js.Array[js.Array[js.Array[String]]] = js.Array()

              /* Grouping entity statistics by perspective and publishing state, organizing it for table
               * display. */

              for (perspective_state <- sorted_keys_total_last(entity_data.keySet))
              {
                val perspective_state_data = entity_data(perspective_state)
                  .asInstanceOf[js.Dictionary[js.Dictionary[js.Dictionary[Int]]]]

                for ((state, state_index) <-
                  sorted_keys_total_last(perspective_state_data.keySet) .zipWithIndex)
                {
                  val state_data = perspective_state_data(state)
                    .asInstanceOf[js.Dictionary[js.Dictionary[Int]]]

                  /* A group of table rows for each entity publishing state. */

                  var entity_table_group: js.Array[js.Array[String]] = js.Array()

                  for ((entity_type, type_index) <-
                    sorted_keys_total_last(state_data.keySet) .zipWithIndex)
                  {
                    val entity_data = state_data(entity_type)

                    val perspective_state_string =
                      if (state_index <= 0 && type_index <= 0) perspective_state else ""

                    val entity_state_string = if (type_index <= 0) state else ""

                    /* Each entity type is a separate row. */

                    entity_table_group.append(js.Array(
                      perspective_state_string,
                      entity_state_string,
                      entity_type,
                      entity_data("desktop").toString,
                      entity_data("web").toString,
                      entity_data("total").toString))
                  }

                  if (entity_table_group.length > 0)
                    entity_table_data.append(entity_table_group)
                }
              }

              user_data.put("entity_table", entity_table_data)
            }

            user_data }: _*)
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

