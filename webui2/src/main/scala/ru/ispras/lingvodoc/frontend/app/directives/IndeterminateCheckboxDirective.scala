package ru.ispras.lingvodoc.frontend.app.directives

import com.greencatsoft.angularjs.core.ModelController
import com.greencatsoft.angularjs._
import org.scalajs.dom.Element
import org.scalajs.jquery.JQueryEventObject

import scala.scalajs.js
import scala.scalajs.js.{Any, UndefOr}
import scala.scalajs.js.JSConverters._
import org.scalajs.dom.console
import org.scalajs.jquery.jQuery


@injectable("indeterminate")
class IndeterminateCheckboxDirective extends AttributeDirective with Requires {

  this.requirements += "ngModel"
  override def link(scope: ScopeType, elems: Seq[Element], attrs: Attributes, controllers: Either[Controller[_], Any]*): Unit = {
    val states = Seq[String]("unchecked", "checked", "clear")
    val element = jQuery(elems.head)

    val isChecked = element.prop("checked").asInstanceOf[Boolean]
    val isIndeterminate = element.prop("indeterminate").asInstanceOf[Boolean]

    val result = controllers collectFirst {
      case Right(c) => c.asInstanceOf[ModelController[js.Any]]
    } ensuring (_.isDefined)

    result foreach { ctrl =>

        ctrl.$formatters = js.Array[js.Function]()
        ctrl.$parsers = js.Array[js.Function]()

        ctrl.$render = () => {
          var currentValue = ctrl.$viewValue
          currentValue.toOption foreach { cv =>

            if (cv == states(0)) {
              element.data("istate", states(0))
              element.prop("checked", false)
              element.prop("indeterminate", false)
            } else {
              if (cv == states(1)) {
                element.data("istate", states(1))
                element.prop("checked", true)
                element.prop("indeterminate", false)
              } else {
                if (cv == states(2)) {
                  element.data("istate", states(2))
                  element.prop("checked", false)
                  element.prop("indeterminate", true)
                }
              }
            }
          }
        }

        element.on("click", (e: JQueryEventObject) => {
          val target = jQuery(e.target)
          val currentState = target.data("istate").asInstanceOf[UndefOr[String]]
          val newState = currentState.toOption.flatMap { state =>
            states.zipWithIndex.find(_._1 == state) map { case (_, index) =>
              val newStateIndex = (index + 1) % 3
              states(newStateIndex)
            }
          }

          newState foreach { n =>
            if (states(1) == n) {
              target.prop("checked", true)
              target.prop("indeterminate", false)
            } else {
              if (states(0) == n) {
                target.prop("checked", false)
                target.prop("indeterminate", false)
              } else {
                if (states(2) == n) {
                  target.prop("checked", false)
                  target.prop("indeterminate", true)
                }
              }
            }
            target.data("istate", n)
            ctrl.$setViewValue(Some(n.asInstanceOf[js.Any]).orUndefined)

          }
        })
    }
  }
}
