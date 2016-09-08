package ru.ispras.lingvodoc.frontend.extras.facades

import scala.scalajs.js
import scala.collection.mutable
import js.JSConverters._

class BootstrapContextMenu(s: MenuOption*) {
  var options = s
  def toJS: js.Array[js.Any] = options.map(_.toJS).toJSArray
}

class MenuOption(val itemText: js.Dynamic, val action: js.Dynamic, val disable: Option[js.Dynamic] = None) {
  def toJS: js.Any = {
    var optionSeq = mutable.Seq(itemText, action)
    optionSeq = disable match {
      case Some(dis) => optionSeq :+ dis
      case None => optionSeq
    }
    optionSeq.toJSArray.asInstanceOf[js.Dynamic]
  }
}

object MenuOption {
  // action and disable param is $itemScope
  def apply(itemText: String, action: (js.Function1[js.Dynamic, Unit]),
           disable: Option[js.Function1[js.Dynamic, Boolean]] = None) = new MenuOption(
    itemText.asInstanceOf[js.Dynamic],
    action.asInstanceOf[js.Dynamic],
    disable.map(_.asInstanceOf[js.Dynamic])
  )
  def apply(itemText: (js.Function1[js.Dynamic, String]),
            action: (js.Function1[js.Dynamic, Unit])) = new MenuOption(
    itemText.asInstanceOf[js.Dynamic],
    action.asInstanceOf[js.Dynamic]
  )
  def apply(itemText: (js.Function1[js.Dynamic, String]),
            action: (js.Function1[js.Dynamic, Unit]),
            disable: Option[js.Function1[js.Dynamic, Boolean]]) = new MenuOption(
    itemText.asInstanceOf[js.Dynamic],
    action.asInstanceOf[js.Dynamic],
    disable.map(_.asInstanceOf[js.Dynamic])
  )
//  // for use with $event and model. action and disable params are $itemScope, $event, model
//  def apply(itemText: String, action: (js.Function3[js.Dynamic, js.Dynamic, js.Dynamic, Unit]),
//            disable: Option[js.Function3[js.Dynamic, js.Dynamic, js.Dynamic, Unit]] = None) = new MenuOption(
//    itemText.asInstanceOf[js.Dynamic],
//    action.asInstanceOf[js.Dynamic],
//    disable.map(_.asInstanceOf[js.Dynamic])
//  )
}
