#!/bin/bash

# deploys needed stuff to project_root/lingvodoc

cp artifacts/webui/js/* ../lingvodoc/static/js/

cp webui/src/templates/main.pt ../lingvodoc/views/v2/templates/main.pt
cp artifacts/webui/templates/main.pt ../lingvodoc/views/v2/templates/main.pt

cp artifacts/webui/templates/*.html ../lingvodoc/static/templates/
cp -r artifacts/webui/templates/modal/ ../lingvodoc/static/templates/
cp -r artifacts/webui/templates/include/ ../lingvodoc/static/templates/

cp shared/src/css/*.css ../lingvodoc/static/css/
cp shared/src/images/* ../lingvodoc/static/images/
