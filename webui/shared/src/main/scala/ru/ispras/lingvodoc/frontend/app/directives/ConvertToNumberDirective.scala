package ru.ispras.lingvodoc.frontend.app.directives

import com.greencatsoft.angularjs._
import com.greencatsoft.angularjs.core.ModelController
import org.scalajs.dom.Element

import scala.scalajs.js

@injectable("convertToNumber")
class ConvertToNumberDirective() extends AttributeDirective with Requires  {

  this.requirements += "ngModel"
  override def link(scope: ScopeType, elems: Seq[Element], attrs: Attributes, controllers: Either[Controller[_], js.Any]*) {

    val result = controllers collectFirst {
      case Right(c) => c.asInstanceOf[ModelController[js.Any]]
    } ensuring (_.isDefined)

    result match {
      case Some(modelController) =>
        val convert = (value: Any) => {
          value match {
            case s: String => s.toInt
            case s: Int => s
            case _ => 0
          }
        }

        val format = (value: Any) => {
          value match {
            case s: String => s
            case s: Int => s.toString
            case _ => ""
          }
        }
        modelController.$parsers.push(convert)
        modelController.$formatters.push(format)
      case None =>
    }
  }
}