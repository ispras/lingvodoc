# Keycloak

This folder contains keycloak installation files.

## Getting started

This project contains all keycloak artifacts for deploy. Folder "scripts" contains JS-based ABAC policies for lingvodoc. You may run ```jar --create --file "custom-scripts.jar" --no-manifest -C "auth/lingvodoc-policies/scripts" .``` to create jar archive "custom-scripts.jar" for deploy. Also, this folder contains basic realm and authorization config for lingvodoc client.

The needed files for running are the following:
```
-- keycloak
   |__ custom-scripts.jar #prebuild policies
   |__ realm-export.json  #realm configuration with clients auth and users
```
To run keycloak:

- `docker-compose up`

Keycloak will be available at http://localhost:9090/ and http://localhost:8080/

## Migrate users


After successful running you may migrate users by alembic script. Please, be sure that keycloak service is healthy.

- `alembic upgrade 477131175d56`

## Building policies

For building new JS attribute policies clone "<project name>" and then build:

```
jar --create --file "custom-scripts.jar" --no-manifest -C "auth/lingvodoc-policies/scripts" .
```

If you want to add new JS policy you need create new script, change meta info and build it. If you use new attribute, don't forget to add it to the Keycloak->Clients->lingvodoc->Client scopes->lingvodoc-dedicated->Add Mapper(bu configuration)->User Attribute

Keycloak docs: <https://www.keycloak.org/docs-api/20.0.1/javadocs/org/keycloak/authorization/policy/evaluation/package-summary.html>

## Updates

After any updates, please, export and save Realm configs.

## Useful api calls

**GET USER TOKEN**
```
curl --request POST \
  --url http://localhost:9090/realms/lingvodoc/protocol/openid-connect/token \
  --header 'Content-Type: application/x-www-form-urlencoded' \
  --data client_id=lingvodoc \
  --data grant_type=password \
  --data 'client_secret=' \
  --data username= \
  --data password=
```
**GET PAT CLIENT TOKEN**
```
curl --request POST \
  --url http://localhost:9090/realms/lingvodoc/protocol/openid-connect/token \
  --header 'Content-Type: application/x-www-form-urlencoded' \
  --data grant_type=client_credentials \
  --data client_id=lingvodoc \
  --data 'client_secret=**********'
```
**CHECK PERMISSION**
```
curl --request POST \
  --url 'http://localhost:9090/realms/lingvodoc/protocol/openid-connect/token?=' \
  --header 'Authorization: Bearer USER_TOKEN' \
  --header 'Content-Type: application/x-www-form-urlencoded' \
  --data grant_type=urn:ietf:params:oauth:grant-type:uma-ticket \
  --data audience=lingvodoc \
  --data 'permission=dictionary/144/3#urn:lingvodoc:scopes:approve' \
  --data response_mode=permissions   #(OR decision HERE)
```
**GET REESOURCE ID BY NAME**
```
curl --request GET \
  --url 'http://localhost:9090/realms/lingvodoc/authz/protection/resource_set?name=dictionary/144/3' \
  --header 'Authorization: Bearer CLIENT_TOKEN' \
  --header 'Content-Type: application/x-www-form-urlencoded' \
  --data grant_type=urn:ietf:params:oauth:grant-type:uma-ticket \
  --data audience=lingvodoc
```

**GET REESOURCE BY ID**
```
curl --request GET \
  --url http://localhost:9090/realms/lingvodoc/authz/protection/resource_set/RESOURCE_ID \
  --header 'Authorization: Bearer CLIENT_TOKEN' \
  --header 'Content-Type: application/x-www-form-urlencoded' \
  --data grant_type=urn:ietf:params:oauth:grant-type:uma-ticket \
  --data audience=lingvodoc
```

### Useful links

* Useful scripts for UMA <https://github.com/please-openit/uma2-bash-client>
* Example with UMA access by resource id <https://github.com/keycloak/keycloak-quickstarts/tree/latest/app-authz-photoz>
* Evaluation API <https://www.keycloak.org/docs-api/21.1.1/javadocs/org/keycloak/authorization/policy/evaluation/package-summary.html>
* Python keycloak lib docs (look at the test examples) <https://github.com/marcospereirampj/python-keycloak>
* About permissions <https://www.keycloak.org/docs/latest/authorization_services/index.html#_service_overview>
