#!/bin/bash

# deploys needed stuff to project_root/lingvodoc

cp webui/target/scala-2.11/* ../lingvodoc/static/js/

cp shared/src/templates/main.pt ../lingvodoc/views/v2/templates/main.pt

cp shared/src/templates/*.html ../lingvodoc/static/templates/
cp -r shared/src/templates/modal/ ../lingvodoc/static/templates/
cp -r shared/src/templates/include/ ../lingvodoc/static/templates/

cp shared/src/css/*.css ../lingvodoc/static/css/
cp shared/src/images/* ../lingvodoc/static/images/
