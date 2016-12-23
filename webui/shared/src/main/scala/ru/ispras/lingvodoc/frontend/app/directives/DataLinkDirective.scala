package ru.ispras.lingvodoc.frontend.app.directives

import com.greencatsoft.angularjs._
import org.scalajs.dom.Element
import org.scalajs.dom.raw.HTMLLinkElement


@injectable("downloadLink")
class DataLinkDirective extends AttributeDirective {

  private[this] def setUrl(element: HTMLLinkElement, mimeType: String, blob: String): Unit = {
    if (blob.nonEmpty && mimeType.nonEmpty) {
      element.href = s"data:$mimeType;base64,$blob"
    }
  }

  override def link(scope: ScopeType, elements: Seq[Element], attrs: Attributes): Unit = {
    val element = elements.head.asInstanceOf[HTMLLinkElement]
    attrs("blob") foreach { blob =>
      attrs("type") foreach { mimeType =>
        setUrl(element, mimeType, blob)
      }
    }

    attrs.$observe("blob", (blob: String) => {
      attrs("type") foreach { mimeType =>
        setUrl(element, mimeType, blob)
      }
    })
  }
}
