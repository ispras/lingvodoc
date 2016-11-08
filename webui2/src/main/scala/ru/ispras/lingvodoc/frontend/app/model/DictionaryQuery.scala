package ru.ispras.lingvodoc.frontend.app.model

import derive.key
import upickle.Js
import upickle.default._
import scala.scalajs.js.JSConverters._


import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class DictionaryQuery() {
  var author: Option[Int] = None
  var userCreated: Option[Seq[Int]] = None
}

object DictionaryQuery {
  implicit val writer = upickle.default.Writer[DictionaryQuery] {
    q: DictionaryQuery =>

      var values = Seq[(String, Js.Value)]()

      q.author foreach {
        author => values = values :+ ("author", Js.Num(author))
      }

      q.userCreated foreach {
        userCreated =>
          values = values :+ ("user_created", Js.Arr(userCreated.map(v => Js.Num(v)): _*))
      }

      Js.Obj(values: _*)
  }

  implicit val reader = upickle.default.Reader[DictionaryQuery] {
    case js: Js.Obj =>

      val q = DictionaryQuery()

      q.author = js.value.find(_._1 == "author") match {
        case Some(l) => Some(readJs[Int](l._2))
        case None => None
      }

      q.userCreated = js.value.find(_._1 == "user_created") match {
        case Some(l) => Some(readJs[Seq[Int]](l._2))
        case None => None
      }
      q
  }
}

