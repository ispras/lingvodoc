# Keycloak

This folder contains keycloak installation files.

## Run

The needed files for running are the following:
```
-- keycloak
   |__ custom-scripts.jar #prebuild policies
   |__ realm-export.json  #realm configuration
   |__ authz-config.json  #configuration for lingvodoc client authorization
```
To run keycloak:

- `docker-compose up`

Keycloak will be available at http://localhost:9090/ and http://localhost:8080/

Then, you must import authz-config.json by path: Clients->lingvodoc->Authorization-> Settings

Provide all configurations to the *.ini file to work with lingvodoc api.

## Migrate users


After successful running you may migrate users by alembic script. Please, be sure that keycloak service is healthy.

- `alembic upgrade 477131175d56`

## Building policies

For building new JS attribute policies clone "<project name>" and then build:

- `mvn clean install`

If you want to add new JS policy you need create new script, change meta info and build it. If you use new attribute, don't forget to add it to the Keycloak->Clients->lingvodoc->Client scopes->lingvodoc-dedicated->Add Mapper(bu configuration)->User Attribute
Keycloak docs: <https://www.keycloak.org/docs-api/20.0.1/javadocs/org/keycloak/authorization/policy/evaluation/package-summary.html>

## Updates

After any updates, please, export and save Realm and Authorization(Clients->lingvodoc->Authorization-> Settings) configs.

