#!/bin/bash

# deploys needed stuff to project_root/lingvodoc

cp artifacts/desktop/js/* ../lingvodoc/static/js/

cp desktop/src/templates/main.pt ../lingvodoc/views/v2/templates/main.pt

cp artifacts/desktop/templates/*.html ../lingvodoc/static/templates/
cp -r artifacts/desktop/templates/modal/ ../lingvodoc/static/templates/
cp -r artifacts/desktop/templates/include/ ../lingvodoc/static/templates/

cp shared/src/css/*.css ../lingvodoc/static/css/
cp shared/src/images/* ../lingvodoc/static/images/
