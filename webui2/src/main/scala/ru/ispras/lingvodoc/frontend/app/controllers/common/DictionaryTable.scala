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
case class GroupColumn(field: Field, dataType: TranslationGist) extends Column {
  override def getName(): String = {
    field.translation
  }
}


abstract class Value() {
  def getType(): String
}

@JSExportAll
case class TextValue(content: String, dataType: TranslationGist, values: js.Array[TextValue]) extends Value {
  override def getType(): String = "Text"
  def getContent(): String = content
}

@JSExportAll
case class GroupValue(dataType: TranslationGist, link: Link) extends Value {
  override def getType(): String = "Group"
  def getContent(): String = "group"
}


@JSExportAll
abstract class GenericCell {
  def getType(): String
}

@JSExportAll
case class Cell(values: js.Array[Value], field: Field) extends GenericCell {
  override def getType(): String = "content"
}

@JSExportAll
case class GroupCell(values: js.Array[Value], field: Field) extends GenericCell {
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







  protected def getContent(entities: Seq[Entity], column: SimpleColumn): GenericCell = {

    val values: js.Array[Value] = entities.toJSArray.filter(entity => entity.fieldClientId == column.field.clientId && entity.fieldObjectId == column.field.objectId).map(entity => {
      TextValue(entity.content, column.dataType, js.Array())
    })

    Cell(values, column.field)
  }

  protected def getContent(entities: Seq[Entity], column: MasterColumn): GenericCell = {
    val values: js.Array[Value] = entities.toJSArray.filter(entity => entity.fieldClientId == column.field.clientId && entity.fieldObjectId == column.field.objectId).map(entity => {
      var subEntities = Seq[TextValue]()
      // create list of sub-entities
      for (e <- entity.entities) {
        val slaveColumnOpt = column.linkedColumns.find(f => f.field.clientId == e.fieldClientId && f.field.objectId == e.fieldObjectId)
        if (slaveColumnOpt.nonEmpty) {
          subEntities = subEntities :+ TextValue(e.content, slaveColumnOpt.get.dataType, js.Array())
        }
      }
      TextValue(entity.content, column.dataType, subEntities.toJSArray)
    })
    Cell(values, column.field)
  }

  protected def getContent(entities: Seq[Entity], column: GroupColumn): GenericCell = {
    val values: Array[Value] = entities.toJSArray.filter(entity => entity.fieldClientId == column.field.clientId && entity.fieldObjectId == column.field.objectId).map(entity => {
      GroupValue(column.dataType, entity.link.get)
    })

    GroupCell(values, column.field)
  }


  def addEntry(entry: LexicalEntry) = {
    val rowData: js.Array[GenericCell] = header.map {
      case column: SimpleColumn => getContent(entry.entities, column)
      case column: MasterColumn => getContent(entry.entities, column)
      case column: GroupColumn => getContent(entry.entities, column)
    }.toJSArray
    rows = Row(entry, rowData.asInstanceOf[js.Array[GenericCell]]) +: rows
  }

  def addRow(entities: Seq[Entity]) = {
    val rowData: js.Array[GenericCell] = header.map {
      case column: SimpleColumn => getContent(entities, column)
      case column: MasterColumn => getContent(entities, column)
    }.toJSArray
    rows = Row(null, rowData.asInstanceOf[js.Array[GenericCell]]) +: rows
  }

  def addEntity(entry: LexicalEntry, entity: Entity) = {

    // first, find corresponding column
    header.find {
      case f: SimpleColumn => f.field.clientId == entity.fieldClientId && f.field.objectId == entity.fieldObjectId
      case f: MasterColumn => f.field.clientId == entity.fieldClientId && f.field.objectId == entity.fieldObjectId
      case f: GroupColumn => f.field.clientId == entity.fieldClientId && f.field.objectId == entity.fieldObjectId
    } match {
      case Some(column) =>
        // find row to append entity to
        rows.find(row => row.entry.getId == entry.getId) match {
          case Some(row) =>

            // get entity as cell
            val content = column match {
              case f: SimpleColumn => getContent(entity :: Nil, f)
              case f: MasterColumn => getContent(entity :: Nil, f)
              case f: GroupColumn => getContent(entity :: Nil, f)
            }

            // find cell
            row.cells.find {
              case c: Cell => c.field.clientId == entity.fieldClientId && c.field.objectId == entity.fieldObjectId
              case c: GroupCell => c.field.clientId == entity.fieldClientId && c.field.objectId == entity.fieldObjectId
            } match {
              case Some(cell) =>
                cell match {
                  case c: Cell =>
                    content match {
                      case gc: Cell => gc.values.foreach(e => c.values.push(e))
                      case gc: GroupCell => gc.values.foreach(e => c.values.push(e))
                    }
                  case c: GroupCell =>
                    content match {
                      case gc: Cell => gc.values.foreach(e => c.values.push(e))
                      case gc: GroupCell => gc.values.foreach(e => c.values.push(e))
                    }
                }
              case None =>
            }
          case None => // row not found
        }
      case None => // column not found
    }
  }
}

object DictionaryTable {

  private[this] def buildHeader(fields: Seq[Field], dataTypes: Seq[TranslationGist]): Seq[Column] = {
    fields.flatMap { field =>
      dataTypes.find(dataType => dataType.clientId == field.dataTypeTranslationGistClientId && dataType.objectId == field.dataTypeTranslationGistObjectId) match {
        case Some(dataType) =>
          val column: Column = field match {
            case x if x.fields.nonEmpty && x.link.isEmpty =>
              MasterColumn(field, dataType, x.fields.map { f =>
                dataTypes.find(dataType => dataType.clientId == f.dataTypeTranslationGistClientId && dataType.objectId == f.dataTypeTranslationGistObjectId) match {
                  case Some(linkedFieldDataType) => SimpleColumn(f, linkedFieldDataType)
                  case None => throw new ControllerException("")
                }
              })
            case x if x.fields.isEmpty && x.link.isEmpty => SimpleColumn(field, dataType)
            case x if x.fields.isEmpty && x.link.nonEmpty => GroupColumn(field, dataType)
          }
          Some(column)
        case None => None
      }
    }
  }

  def build(fields: Seq[Field], dataTypes: Seq[TranslationGist], entries: Seq[LexicalEntry]): DictionaryTable = {

    val table = new DictionaryTable()

    val columns = buildHeader(fields, dataTypes)

    val rows = entries.map { entry =>
      val rowData: js.Array[GenericCell] = columns.map {
        case column: SimpleColumn => table.getContent(entry.entities, column)
        case column: MasterColumn => table.getContent(entry.entities, column)
        case column: GroupColumn => table.getContent(entry.entities, column)
      }.toJSArray
      Row(entry, rowData.asInstanceOf[js.Array[GenericCell]])
    }

    table.header = columns.toJSArray
    table.rows = rows.toJSArray
    table
  }

  def build(fields: Seq[Field], dataTypes: Seq[TranslationGist]): DictionaryTable = {

    val table = new DictionaryTable()
    val columns = buildHeader(fields, dataTypes)
    table.header = columns.toJSArray
    table.rows = js.Array[Row]()
    table
  }
}

















