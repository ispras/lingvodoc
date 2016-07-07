enablePlugins(ScalaJSPlugin)

name := "lingvodoc2 frontend"

scalaVersion := "2.11.7"
scalacOptions += "-deprecation"

resolvers += "Sonatype OSS Snapshots" at "https://oss.sonatype.org/content/repositories/snapshots"

libraryDependencies += "org.scala-js" %%% "scalajs-dom" % "0.8.0"
libraryDependencies += "com.lihaoyi" %%% "upickle" % "0.3.6"
libraryDependencies += "com.greencatsoft" %%% "scalajs-angular" % "0.6"
libraryDependencies += "io.surfkit" %%% "scalajs-google-maps" % "0.1-SNAPSHOT"
libraryDependencies += "org.scala-lang.modules" % "scala-xml_2.11" % "1.0.5"


libraryDependencies += "org.webjars" % "jquery" % "2.2.1"
libraryDependencies += "org.webjars" % "angularjs" % "1.4.6"
libraryDependencies += "org.webjars" % "bootstrap" % "3.3.6"
libraryDependencies += "org.webjars" % "angular-ui-bootstrap" % "0.13.4"


jsDependencies += "org.webjars" % "jquery" % "2.2.1" / "jquery.js"
jsDependencies += "org.webjars" % "angularjs" % "1.4.6" / "angular.js" dependsOn "jquery.js"
jsDependencies += "org.webjars" % "angularjs" % "1.4.6" / "angular-route.js" dependsOn "angular.js"
jsDependencies += "org.webjars" % "bootstrap" % "3.3.6" / "bootstrap.js" dependsOn "angular.js"
jsDependencies += "org.webjars" % "angular-ui-bootstrap" % "0.13.4" / "ui-bootstrap.js" dependsOn "bootstrap.js"
jsDependencies += "org.webjars" % "angular-ui-bootstrap" % "0.13.4" / "ui-bootstrap-tpls.js" dependsOn "ui-bootstrap.js"

