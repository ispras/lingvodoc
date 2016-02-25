package ru.ispras.lingvodoc.frontend.extras

import scala.xml.Node

package object elan {
  implicit class XmlEnhancements(x: xml.NodeSeq) {
    def findElementbyAttrValue(attrName: String, attrValue: String): Option[Node] = {
      val elem = x.filter((prop: Node) => (prop \@ attrName) == attrValue)
      elem.headOption
    }
  }
}

