package ru.ispras.lingvodoc.frontend.app.controllers.common

import ru.ispras.lingvodoc.frontend.app.model._

import scala.scalajs.js
import scala.scalajs.js.{Array, UndefOr}
import scala.scalajs.js.annotation.{JSExport, JSExportAll}
import scala.scalajs.js.JSConverters._
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.exceptions.{ControllerException, ModelException}
import ru.ispras.lingvodoc.frontend.app.utils.{GUIDGenerator, Utils}



@JSExportAll
abstract class Column(field: Field, dataType: TranslationGist) {
  def getType(): String
  def getName(): String
  def getField(): Field = field

  val internalId = GUIDGenerator.generate()

  def checkDataTypeName(dataTypeName: String): Boolean = {
    dataType.atoms.find(a => a.localeId == 2) match {
      case Some(atom) => atom.content.equals(dataTypeName)
      case None =>
        false
    }
  }
}

@JSExportAll
case class SimpleColumn(field: Field, dataType: TranslationGist) extends Column(field, dataType) {
  override def getType(): String = "Simple"

  override def getName(): String = {
    field.translation
  }
}

@JSExportAll
case class MasterColumn(field: Field, dataType: TranslationGist, linkedColumns: js.Array[SimpleColumn]) extends Column(field, dataType) {

  override def getType(): String = "Master"

  override def getName(): String = {
    field.translation
  }
}

@JSExportAll
case class GroupColumn(field: Field, dataType: TranslationGist) extends Column(field, dataType) {

  override def getType(): String = "Group"

  override def getName(): String = {
    field.translation
  }
}

@JSExportAll
abstract class Value(entity: Entity) {
  def getType(): String
  def getContent(): String

  val internalId = GUIDGenerator.generate()

  def getEntity(): Entity = {
    entity
  }
}

@JSExportAll
case class TextValue(entity: Entity, dataType: TranslationGist, values: js.Array[Value]) extends Value(entity) {
  override def getType(): String = "Text"
  override def getContent(): String = entity.content
}


@JSExportAll
case class GroupValue(entity: Entity, dataType: TranslationGist, link: Link) extends Value(entity) {
  override def getType(): String = "Group"
  override def getContent(): String = "group"
}


@JSExportAll
abstract class GenericCell(values: js.Array[Value], field: Field) {
  def getType(): String
  def getValues() = values
  def getField() = field

  val internalId = GUIDGenerator.generate()
}

@JSExportAll
case class Cell(values: js.Array[Value], field: Field) extends GenericCell(values, field) {
  override def getType(): String = "content"
}

@JSExportAll
case class GroupCell(values: js.Array[Value], field: Field) extends GenericCell(values, field) {
  override def getType(): String = "group"
}


@JSExportAll
case class Row(entry: LexicalEntry, cells: js.Array[GenericCell])


class DictionaryTable(private val fields: Seq[Field], private val dataTypes: Seq[TranslationGist]) {

  private var linkedPerspectives: Seq[Perspective] = Seq[Perspective]()

  @JSExport
  var header: js.Array[Column] = js.Array()

  @JSExport
  var rows: js.Array[Row] = js.Array()



  protected def getContent(entities: Seq[Entity], column: SimpleColumn): GenericCell = {
    val values: js.Array[Value] = entities.toJSArray.filter(entity => entity.fieldClientId == column.field.clientId && entity.fieldObjectId == column.field.objectId).map(entity => {
      TextValue(entity, column.dataType, js.Array())
    })
    Cell(values, column.field)
  }

  protected def getContent(entities: Seq[Entity], column: MasterColumn): GenericCell = {
    val values: js.Array[Value] = entities.toJSArray.filter(entity => entity.fieldClientId == column.field.clientId && entity.fieldObjectId == column.field.objectId).map(entity => {
      var subEntities = Seq[Value]()
      // create list of sub-entities
      for (e <- entity.entities) {
        val slaveColumnOpt = column.linkedColumns.find(f => f.field.clientId == e.fieldClientId && f.field.objectId == e.fieldObjectId)
        if (slaveColumnOpt.nonEmpty) {
          subEntities = subEntities :+ TextValue(e, slaveColumnOpt.get.dataType, js.Array())
        }
      }
      TextValue(entity, column.dataType, subEntities.toJSArray)
    })
    Cell(values, column.field)
  }

  protected def getContent(entities: Seq[Entity], column: GroupColumn): GenericCell = {
    val values: Array[Value] = entities.toJSArray.filter(entity => entity.fieldClientId == column.field.clientId && entity.fieldObjectId == column.field.objectId).map(entity => {
      GroupValue(entity, column.dataType, entity.link.get)
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


  protected def findField(fields: Seq[Field], fieldId: CompositeId): Option[Field] = {
    fields.find(f => f.clientId == fieldId.clientId && f.objectId == fieldId.objectId ) match {
      case Some(field) => Some(field)
      case None =>
        var result: Option[Field] = None
        for (v <- fields) {
          v match {
            case sv: Field => findField(sv.fields, fieldId) match {
              case Some(x) => result = Some(x)
              case None =>
            }
            case _ => None
          }
        }
        result
    }
  }

  protected def findValue(values: Seq[Value], entity: Entity): Option[Value] = {
    values.find(v => v.getEntity.getId == entity.getId) match {
      case Some(value) => Some(value)
      case None =>
        var result: Option[Value] = None
        for (v <- values) {
          v match {
            case sv: TextValue => findValue(sv.values, entity) match {
              case Some(x) => result = Some(x)
              case None =>
            }
            case _ => None
          }
        }
        result
    }
  }


  protected def entityToValue(entity: Entity): Value = {
    findField(fields, CompositeId(entity.fieldClientId, entity.fieldObjectId)) match {
      case Some(field) =>
      dataTypes.find { d => d.clientId == field.dataTypeTranslationGistClientId && d.objectId == field.dataTypeTranslationGistObjectId } match {
        case Some(dataType) =>

          val entities = entity.entities.map(e => entityToValue(e))

          Utils.getDataTypeName(dataType) match {
            case "Text" => TextValue(entity, dataType, entities)
            case "Sound" => TextValue(entity, dataType, entities)
            case "Markup" => TextValue(entity, dataType, entities)
            case "Image" => TextValue(entity, dataType, entities)
            case "Link" => GroupValue(entity, dataType, entity.link.get)
            case "Grouping Tag" => TextValue(entity, dataType, entities)
          }
        case None => throw new ModelException("Entity refers to the unknown data type!")
      }
      case None =>
        throw new ModelException("Entity refers to the unknown field!")
    }
  }

  def addEntity(value: Value, entity: Entity) = {
    value match {
      case v: TextValue => v.values.push(entityToValue(entity))
      case _ => throw new ModelException("Attempt to add nested value to value which do not support nested values!")
    }
  }


  def addEntity(entry: LexicalEntry, parentEntity: Entity, entity: Entity) = {
    rows.find { row => row.entry.getId == entry.getId } match {
      case Some(row) =>
        row.cells.foreach(cell =>
          findValue(cell.getValues(), parentEntity) match {
            case Some(value) =>
              value match {
                case v: TextValue =>
                  if (v.entity.clientId == entity.parentClientId && v.entity.clientId == entity.parentClientId) {
                    v.values.push(entityToValue(entity))
                  }
                case _ =>
              }
            case None =>
          }
        )
      case None =>
    }

  }

  def addEntity(entry: LexicalEntry, entity: Entity) = {
    rows.find { row => row.entry.getId == entry.getId } match {
      case Some(row) =>
        row.cells.find(cell => cell.getField.clientId == entity.fieldClientId && cell.getField.objectId == entity.fieldObjectId) match {
          case Some(cell) => cell.getValues.push(entityToValue(entity))
          case None =>
        }
      case None =>
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

    val table = new DictionaryTable(fields, dataTypes)

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

    val table = new DictionaryTable(fields, dataTypes)
    val columns = buildHeader(fields, dataTypes)
    table.header = columns.toJSArray
    table.rows = js.Array[Row]()
    table
  }
}

















