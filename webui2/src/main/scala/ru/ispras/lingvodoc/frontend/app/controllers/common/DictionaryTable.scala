package ru.ispras.lingvodoc.frontend.app.controllers.common

import ru.ispras.lingvodoc.frontend.app.model._

import scala.scalajs.js
import scala.scalajs.js.Array
import scala.scalajs.js.annotation.{JSExport, JSExportAll}
import scala.scalajs.js.JSConverters._
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.exceptions.ControllerException
import ru.ispras.lingvodoc.frontend.app.utils.Utils



@JSExportAll
abstract class Column {
  def getName(): String
}

@JSExportAll
case class SimpleColumn(field: Field, dataType: TranslationGist) extends Column {
  override def getName(): String = {
    field.translation
  }
}

@JSExportAll
case class MasterColumn(field: Field, dataType: TranslationGist, linkedColumns: js.Array[SimpleColumn]) extends Column {
  override def getName(): String = {
    field.translation
  }
}

@JSExportAll
case class Value(content: String, dataType: TranslationGist, values: js.Array[Value]) {
  def getContent(): String = content
}


@JSExportAll
abstract class GenericCell {
  def getType(): String
}

@JSExportAll
case class Cell(values: js.Array[Value]) extends GenericCell {
  override def getType(): String = "content"
}

@JSExportAll
case class GroupCell(contents: js.Array[Cell]) extends GenericCell {
  override def getType(): String = "group"
}


@JSExportAll
case class Row(entry: LexicalEntry, cells: js.Array[GenericCell])


class DictionaryTable {

  private var linkedPerspectives: Seq[Perspective] = Seq[Perspective]()
  private var fields: Seq[Field] = Seq[Field]()

  @JSExport
  var header: js.Array[Column] = js.Array()

  @JSExport
  var rows: js.Array[Row] = js.Array()


  protected def getContent(entities: Seq[Entity], column: SimpleColumn): Cell = {
//    console.log((column.field :: Nil).toJSArray)
//    console.log((entities).toJSArray)

    val values = entities.filter(entity => entity.fieldClientId == column.field.clientId && entity.fieldObjectId == column.field.objectId).map(entity => {
      Value(entity.content, column.dataType, js.Array())
    }).toJSArray
    
    Cell(values)
  }

  protected def getContent(entities: Seq[Entity], column: MasterColumn): Cell = {
    val values: js.Array[Value] = entities.toJSArray.filter(entity => entity.fieldClientId == column.field.clientId && entity.fieldObjectId == column.field.objectId).map(entity => {
      var subEntities = Seq[Value]()
      // create list of sub-entities
      for (e <- entity.entities) {
        val slaveColumnOpt = column.linkedColumns.find(f => f.field.clientId == e.fieldClientId && f.field.objectId == e.fieldObjectId)
        if (slaveColumnOpt.nonEmpty) {
          subEntities = subEntities :+ Value(e.content, slaveColumnOpt.get.dataType, js.Array())
        }
      }
      Value(entity.content, column.dataType, subEntities.toJSArray)
    })
    Cell(values)
  }

  def addEntry(entry: LexicalEntry) = {
    val rowData: js.Array[Cell] = header.map {
      case column: SimpleColumn => getContent(entry.entities, column)
      case column: MasterColumn => getContent(entry.entities, column)
    }.toJSArray
    rows = Row(entry, rowData.asInstanceOf[js.Array[GenericCell]]) +: rows
  }
}

object DictionaryTable {


  def build(fields: Seq[Field], dataTypes: Seq[TranslationGist], entries: Seq[LexicalEntry]): DictionaryTable = {

    val table = new DictionaryTable()

    val columns = fields.flatMap { field =>
      dataTypes.find(dataType => dataType.clientId == field.dataTypeTranslationGistClientId && dataType.objectId == field.dataTypeTranslationGistObjectId) match {
        case Some(dataType) =>
          val column: Column = field match {
            case x if x.fields.nonEmpty =>
              MasterColumn(field, dataType, x.fields.map { f =>
                dataTypes.find(dataType => dataType.clientId == f.dataTypeTranslationGistClientId && dataType.objectId == f.dataTypeTranslationGistObjectId) match {
                  case Some(linkedFieldDataType) => SimpleColumn(f, linkedFieldDataType)
                  case None => throw new ControllerException("")
                }
              })
            case x if x.fields.isEmpty => SimpleColumn(field, dataType)
          }
          Some(column)
        case None => None
      }
    }

    val rows = entries.map { entry =>
      val rowData: js.Array[Cell] = columns.map {
        case column: SimpleColumn => table.getContent(entry.entities, column)
        case column: MasterColumn => table.getContent(entry.entities, column)
      }.toJSArray
      Row(entry, rowData.asInstanceOf[js.Array[GenericCell]])
    }

    table.header = columns.toJSArray
    table.rows = rows.toJSArray

    console.log((table :: Nil).toJSArray)

    table
  }
}

















