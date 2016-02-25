enablePlugins(ScalaJSPlugin)

name := "lingvodoc2 frontend"

scalaVersion := "2.11.7"
scalacOptions += "-deprecation"

libraryDependencies += "org.scala-js" %%% "scalajs-dom" % "0.8.0"
libraryDependencies += "com.lihaoyi" %%% "upickle" % "0.3.6"
libraryDependencies += "com.greencatsoft" %%% "scalajs-angular" % "0.6"
libraryDependencies += "org.scala-lang.modules" %% "scala-xml" % "1.0.2"
