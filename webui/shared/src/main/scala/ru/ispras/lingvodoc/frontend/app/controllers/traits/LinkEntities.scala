package ru.ispras.lingvodoc.frontend.app.controllers.traits

import com.greencatsoft.angularjs.Controller
import com.greencatsoft.angularjs.extensions.{ModalOptions, ModalService}
import ru.ispras.lingvodoc.frontend.app.controllers.common.{DictionaryTable, GroupValue, Value}
import ru.ispras.lingvodoc.frontend.app.model.{CompositeId, Entity, Field, LexicalEntry}

import scala.concurrent.ExecutionContext
import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport


trait LinkEntities {
  this: Controller[_] =>

  implicit val executionContext: ExecutionContext

  protected[this] def modal: ModalService

  protected[this] def dictionaryTable: DictionaryTable

  protected[this] def dictionaryId: CompositeId

  protected[this] def perspectiveId: CompositeId

  @JSExport
  def linksCount(values: js.Array[Value]): Int = {
    values.filterNot(_.getEntity().markedForDeletion).size
  }

  @JSExport
  def editLinkedPerspective(entry: LexicalEntry, field: Field, values: js.Array[Value]): Unit = {

    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/editLinkedDictionary.html"
    options.controller = "EditDictionaryModalController"
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
          entities = values.map { _.getEntity() }.filterNot(_.markedForDeletion)
        )
      }
    ).asInstanceOf[js.Dictionary[Any]]

    val instance = modal.open[Seq[Entity]](options)
    instance.result map { entities =>
      entities.foreach(e => dictionaryTable.addEntity(entry, e))
    }
  }

  @JSExport
  def viewLinkedPerspective(entry: LexicalEntry, field: Field, values: js.Array[Value]): Unit = {

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
          entities = values.map { _.getEntity() }.filterNot(_.markedForDeletion)
        )
      }
    ).asInstanceOf[js.Dictionary[Any]]

    val instance = modal.open[Seq[Entity]](options)
    instance.result map { entities =>
      entities.foreach(e => dictionaryTable.addEntity(entry, e))
    }
  }

  @JSExport
  def publishLinkedPerspective(entry: LexicalEntry, field: Field, values: js.Array[Value]): Unit = {

    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/publishLinkedDictionaryModal.html"
    options.controller = "PublishLinkedDictionaryModalController"
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
          entities = values.map { _.getEntity() }.filterNot(_.markedForDeletion)
        )
      }
    ).asInstanceOf[js.Dictionary[Any]]

    modal.open[Unit](options)
  }

  @JSExport
  def acceptLinkedPerspective(entry: LexicalEntry, field: Field, values: js.Array[Value]): Unit = {

    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/contributionsLinkedDictionaryModal.html"
    options.controller = "ContributionsLinkedDictionaryModalController"
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
          entities = values.map { _.getEntity() }.filterNot(_.markedForDeletion)
        )
      }
    ).asInstanceOf[js.Dictionary[Any]]

    modal.open[Unit](options)
  }
}
