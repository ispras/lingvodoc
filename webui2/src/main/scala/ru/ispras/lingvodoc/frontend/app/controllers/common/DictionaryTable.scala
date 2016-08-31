package ru.ispras.lingvodoc.frontend.app.controllers.common

import ru.ispras.lingvodoc.frontend.app.model.{Entity, Field, LexicalEntry}


import scala.scalajs.js
import scala.scalajs.js.Array
import scala.scalajs.js.annotation.{JSExport, JSExportAll}
import scala.scalajs.js.JSConverters._
import org.scalajs.dom.console


@JSExportAll
abstract class Column {
  def getName(): String
}

@JSExportAll
case class SimpleColumn(entityType: String, dataType: String, displayName: String) extends Column {
  override def getName(): String = displayName
}

@JSExportAll
case class GroupColumn(group: String, columns: js.Array[Column], displayName: String) extends Column {
  override def getName(): String = displayName
}

@JSExportAll
case class MasterColumn(entityType: String, dataType: String, slaveColumns: js.Array[SimpleColumn], displayName: String) extends Column {
  override def getName(): String = displayName
}


@JSExportAll
case class Value(content: String, dataType: String, values: js.Array[Value]) {
  def getContent(): String = content
}


@JSExportAll
abstract class GenericContent {
  def getType(): String
}


@JSExportAll
case class Content(values: js.Array[Value]) extends GenericContent {
  override def getType(): String = "content"
}

@JSExportAll
case class GroupContent(contents: js.Array[Content]) extends GenericContent {
  override def getType(): String = "group"
}


@JSExportAll
case class Row(cells: js.Array[GenericContent])


class DictionaryTable {

  private var fields = Seq[Field]()

  @JSExport
  var header: js.Array[Column] = js.Array()

  @JSExport
  var rows: js.Array[Row] = js.Array()


  private def createColumn(field: Field): Column = {
    field match {
      case c if c.fields.nonEmpty => MasterColumn(field.translation, field.translation, field.fields.toSeq.map(f => SimpleColumn(f.translation, f.translation, f.translation)).toJSArray, field.translation)
      case c if c.fields.isEmpty => SimpleColumn(field.translation, field.translation, field.translation)
    }
  }


  private def addColumn(field: Field) = {
    val h = createColumn(field)
    header.push(h)
  }

  private def getContent(entities: Seq[Entity], column: SimpleColumn): Content = {
    val values: js.Array[Value] = entities.toJSArray.filter(entity => entity.entityType.equals(column.entityType)).map(entity => {
      Value(entity.content, column.dataType, js.Array[Value]())
    })
    Content(values)
  }

  private def getContent(entities: Seq[Entity], column: MasterColumn): Content = {
    val values: js.Array[Value] = entities.toJSArray.filter(entity => entity.entityType.equals(column.entityType)).map(entity => {
      var subEntities = Seq[Value]()
      // create list of sub-entities
      for (e <- entity.entities) {
        val slaveColumnOpt = column.slaveColumns.find(f => f.entityType.equals(e.entityType))
        if (slaveColumnOpt.nonEmpty) {
          subEntities = subEntities :+ Value(e.content, slaveColumnOpt.get.dataType, js.Array())
        }
      }
      Value(entity.content, column.dataType, subEntities.toJSArray)
    })
    Content(values)
  }

  private def addRow(entry: LexicalEntry) = {

    val cccc: Array[GenericContent] = header.map {
      case column: SimpleColumn => getContent(entry.entities, column)
      case column: MasterColumn => getContent(entry.entities, column)

      case column: GroupColumn =>
        val contents = column.columns.map {
          case c: SimpleColumn => getContent(entry.entities, c)
          case c: MasterColumn => getContent(entry.entities, c)
        }
        GroupContent(contents)
    }

    rows = rows :+ Row(cccc)
  }
}

object DictionaryTable {
  def apply(fields: Seq[Field], entries: Seq[LexicalEntry]): DictionaryTable = {

    val table = new DictionaryTable()

    // save raw fields
    table.fields = fields

    // create table header
    for (field <- fields.toList) {
      table.addColumn(field)
    }

    // build table content
    for (entry <- entries) {
      table.addRow(entry)
    }

    table
  }

  def build(columns: Seq[Column], cells: Seq[GenericContent]): DictionaryTable = {
    val table = new DictionaryTable()
    table.header = columns.toJSArray
    table.rows = (Row(cells.toJSArray) :: Nil).toJSArray
    table
  }



}