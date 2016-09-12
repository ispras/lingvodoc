#!/bin/bash

# deploys needed stuff to project_root/lingvodoc

cp target/scala-2.11/* ../lingvodoc/static/js/

cp src/templates/main.pt ../lingvodoc/views/v2/templates/main.pt

cp src/templates/*.html ../lingvodoc/static/templates/
cp -r src/templates/modal/ ../lingvodoc/static/templates/
cp -r src/templates/include/ ../lingvodoc/static/templates/


cp src/css/*.css ../lingvodoc/static/css/