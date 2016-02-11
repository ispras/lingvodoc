package ru.ispras.lingvodoc.frontend.app.model

import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class LexicalEntry(override val clientId: Int,
                        override val objectId: Int,
                        var parentClientId: Int,
                        var parentObjectId: Int,
                        var level: String,
                        var published: Boolean,
                        var markedForDeletion: Boolean) extends Object(clientId, objectId) {

  var values: Seq[Value] = Seq[Value]()
}
