
package ru.ispras.lingvodoc.frontend.app.model

import upickle.Js

import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class CompositeId(override val clientId: Int, override val objectId: Int) extends Object(clientId, objectId)


object CompositeId {

  def fromObject[T <: Object](o: T): CompositeId = {
    CompositeId(o.clientId, o.objectId)
  }

  implicit val writer = upickle.default.Writer[CompositeId] {
    id: CompositeId =>
      Js.Obj(
        ("client_id", Js.Num(id.clientId)),
        ("object_id", Js.Num(id.objectId)))
  }

  implicit val reader = upickle.default.Reader[CompositeId] {
    case js: Js.Obj =>
      val clientId = js("client_id").num.toInt
      val objectId = js("object_id").num.toInt
      CompositeId(clientId, objectId)
  }

  /**
    * Ordering of identifiers first by clientId, then by objectId.
    *
    * Implementation based on info in StackOverflow question http://stackoverflow.com/questions/19345030/
    * easy-idiomatic-way-to-define-ordering-for-a-simple-case-class, answer http://stackoverflow.com/a/
    * 19348339/2016856.
    */
  implicit def orderingByClientIdObjectId[A <: CompositeId]: Ordering[A] =
    Ordering.by(composite_id => (composite_id.clientId, composite_id.objectId))
}

