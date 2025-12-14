```shell
pushd ~/lingvodoc/keycloak/ && zip -r policy.jar META-INF/ resource-acl.js && mv policy.jar /opt/keycloak/providers/ && popd && KEYCLOAK_ADMIN=admin KEYCLOAK_ADMIN_PASSWORD=admin bin/kc.sh start-dev --db postgres --db-username postgres --db-password postgres
```

```shell
export ADMIN_TOKEN=$(curl --request POST --url http://localhost:8080/realms/master/protocol/openid-connect/token --header 'Content-Type: application/x-www-form-urlencoded' --data client_id=admin-cli --data grant_type=password --data username=admin --data password=admin | jq -r '.access_token')
```

```shell
export LINGVODOC_TOKEN=$(curl --request POST --url http://localhost:8080/realms/lingvodoc/protocol/openid-connect/token --header 'Content-Type: application/x-www-form-urlencoded' --data client_id=lingvodoc --data grant_type=client_credentials --data client_secret=y6TdJnKCclMbHUxaBFwdbxOh88duE4IL | jq -r '.access_token')
```

```shell
curl --request POST --url http://localhost:8080/realms/lingvodoc/protocol/openid-connect/token --header 'Content-Type: application/x-www-form-urlencoded' --data client_id=lingvodoc --data grant_type=password --data client_secret=y6TdJnKCclMbHUxaBFwdbxOh88duE4IL --data username=modis --data password=adhj-b3hc
```

http://localhost:8080/realms/lingvodoc/account

```shell
python3 - << 'PY' "$LINGVODOC_TOKEN"
import sys, base64, json
t = sys.argv[1]
try:
    payload = t.split('.')[1]
    padding = '=' * ((4 - len(payload) % 4) % 4)
    data = base64.urlsafe_b64decode(payload + padding).decode()
    print(json.dumps(json.loads(data), indent=2))
except Exception as e:
    print("decode error:", e)
PY
```