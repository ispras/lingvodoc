package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{Scope, Timeout}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import ru.ispras.lingvodoc.frontend.app.controllers.common.{DictionaryTable, Value}
import ru.ispras.lingvodoc.frontend.app.controllers.traits.{LoadingPlaceholder, SimplePlay}
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, ModalInstance, ModalService}

import scala.scalajs.js.JSConverters._
import org.scalajs.dom.console

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}

@js.native
trait EditGroupingTagScope extends Scope {

}

@injectable("EditGroupingTagModalController")
class EditGroupingTagModalController(scope: EditGroupingTagScope, modal: ModalService,
                                     instance: ModalInstance[Unit],
                                     backend: BackendService,
                                     val timeout: Timeout,
                                     params: js.Dictionary[js.Function0[js.Any]])
  extends AbstractController[EditGroupingTagScope](scope)
    with AngularExecutionContextProvider
    with SimplePlay
    with LoadingPlaceholder {


  private[this] val dictionaryClientId = params("dictionaryClientId").asInstanceOf[Int]
  private[this] val dictionaryObjectId = params("dictionaryObjectId").asInstanceOf[Int]
  private[this] val perspectiveClientId = params("perspectiveClientId").asInstanceOf[Int]
  private[this] val perspectiveObjectId = params("perspectiveObjectId").asInstanceOf[Int]
  private[this] val lexicalEntry = params("lexicalEntry").asInstanceOf[LexicalEntry]
  private[this] val field = params("field").asInstanceOf[Field]
  private[this] val values = params("values").asInstanceOf[js.Array[Value]]
  private[this] val dictionaryId = CompositeId(dictionaryClientId, dictionaryObjectId)
  private[this] val perspectiveId = CompositeId(perspectiveClientId, perspectiveObjectId)
  private[this] val lexicalEntryId = CompositeId.fromObject(lexicalEntry)
  private[this] val fieldId = CompositeId.fromObject(field)


  private[this] var dataTypes = Seq[TranslationGist]()
  private[this] var perspectiveFields = Seq[Field]()



  @JSExport
  def connect() = {

  }

  @JSExport
  def remove() = {

  }



  @JSExport
  def close() = {
    instance.dismiss(())
  }

  override protected def onLoaded[T](result: T): Unit = {}

  override protected def onError(reason: Throwable): Unit = {}

  override protected def preRequestHook(): Unit = {}

  override protected def postRequestHook(): Unit = {}


  doAjax(() => {
    backend.dataTypes() flatMap { allDataTypes =>
      dataTypes = allDataTypes
      // get fields of main perspective
      backend.getFields(dictionaryId, perspectiveId) flatMap { fields =>
        perspectiveFields = fields
        backend.connectedLexicalEntries(lexicalEntryId, fieldId) map { connectedEntries =>
          DictionaryTable.build(perspectiveFields, dataTypes, connectedEntries)
        }
      }
    }
  })


}
