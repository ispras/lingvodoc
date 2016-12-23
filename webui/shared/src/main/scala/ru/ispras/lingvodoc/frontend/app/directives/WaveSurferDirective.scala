package ru.ispras.lingvodoc.frontend.app.directives

import com.greencatsoft.angularjs.core.Parse
import com.greencatsoft.angularjs.{Attributes, ElementDirective, injectable}
import org.scalajs.dom.Element
import ru.ispras.lingvodoc.frontend.extras.facades.{WaveSurfer, WaveSurferOpts}

import scala.scalajs.js

@injectable("wavesurfer")
class WaveSurferDirective(parse: Parse) extends ElementDirective {
  override def link(scope: ScopeType, elements: Seq[Element], attrs: Attributes): Unit = {
    val element: Element = elements.head
    import org.scalajs.jquery.jQuery
    jQuery(element).css("display", "block")

    val wso = WaveSurferOpts(element, waveColor = "violet", progressColor = "purple",
      cursorWidth = 2, cursorColor = "red", fillParent = true, height = 64, barWidth = 1)
    val waveSurfer = WaveSurfer.create(wso)

    val handler = attrs("onReady").toOption.map(parse(_))
    handler.foreach(_(scope, js.Dynamic.literal("$waveSurfer" -> waveSurfer)))
  }
}
