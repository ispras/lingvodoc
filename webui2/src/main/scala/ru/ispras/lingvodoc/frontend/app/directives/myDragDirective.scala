package ru.ispras.lingvodoc.frontend.app.directives

import com.greencatsoft.angularjs.core.{RootScope, Parse, Scope, Location}
import com.greencatsoft.angularjs.{Controller, AttributeDirective, injectable}
import com.greencatsoft.angularjs.Attributes
import org.scalajs.dom
import org.scalajs.dom.Element
import org.scalajs.dom.raw.{DragEvent, MouseEvent, HTMLElement}
import ru.ispras.lingvodoc.frontend.app.controllers.SoundMarkupScope
import scala.scalajs.js
import org.scalajs.dom.{console}


//@injectable("myDrag")
//class myDrag(parse: Parse, rootScope: RootScope) extends AttributeDirective {
//
//  override type ScopeType = SoundMarkupScope
//
//  override def link(scope: ScopeType, elems: Seq[Element], attrs: Attributes) {
//    console.log("linking drag directive")
//    val fn = parse(attrs("myDrag").toOption.get)
//    val elem = elems.head.asInstanceOf[org.scalajs.dom.raw.HTMLElement]
//    elem.onclick = (event: MouseEvent) => fn(scope, js.Dynamic.literal(event = event))
//    elem.textContent = "Some content set from the directive"
//  }
//}
//
//@injectable("myDragDirective")
//class myDragDirective(parse: Parse, rootScope: RootScope) extends AttributeDirective {
//
//  override type ScopeType = SoundMarkupScope
//
//  override def link(scope: ScopeType, elems: Seq[Element], attrs: Attributes) {
//    console.log("linking drag directive")
//    val fn = parse(attrs("myDragDirective").toOption.get)
//    val elem = elems.head.asInstanceOf[org.scalajs.dom.raw.HTMLElement]
//    elem.onclick = (event: MouseEvent) => fn(scope, js.Dynamic.literal(event = event))
//    elem.textContent = "Some content set from the directive"
//  }
//}
//
//@injectable("myDragDirective")
//class myDragDirective(parse: Parse, rootScope: RootScope) extends AttributeDirective {
//
//  override type ScopeType = SoundMarkupScope
//
//  override def link(scope: ScopeType, elems: Seq[Element], attrs: Attributes) {
//    console.log("linking drag directive")
//    val fn = parse(attrs("myDragDirective").toOption.get)
//    val elem = elems.head.asInstanceOf[org.scalajs.dom.raw.HTMLElement]
//    elem.onclick = (event: MouseEvent) => fn(scope, js.Dynamic.literal(event = event))
//    elem.textContent = "Some content set from the directive"
//  }
//}