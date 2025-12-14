
// JavaScript policy for Keycloak.
//
// To use this, pack this with the META-INF into a .jar, place it into Keycloak installation into the
// /providers subdirectory, and restart Keycloak.
//
// Packing into a .jar:
//
//  zip -r policy.jar META-INF/ resource-acl.js

var context = $evaluation.getContext();
var identity = context.getIdentity();
var permission = $evaluation.getPermission();
var policy = $evaluation.getPolicy();
var resource = permission.getResource();
var scopes =  permission.getScopes();

try {
    /*
    print(context);
    print(identity);
    print(permission);
    print(policy);
    print(resource);
    print(scopes);

    print('start');
    print('resource', resource.getName());
    print('scopes', scopes);
    print('scopes.toArray()', scopes.toArray());
    print('scopes.toArray()[0]', scopes.toArray()[0]);

    var scope = scopes.toArray()[0].getName();
    print('scope', scope);

    var index = scope.lastIndexOf(':');
    var action = index === -1 ? scope : scope.substring(index + 1);
    print('action', action)

    var id = identity.getId();
    print('id', id);

    var attributes = resource.getAttributes();
    print('attributes', attributes);

    var attribute = action + ':' + id;
    print('attribute', attribute)

    var check1 = resource.getAttribute(attribute)
    var check2 = resource.getAttribute('x');
    print('check1', check1);
    print('check2', check2);
    */

    var scope = scopes.toArray()[0].getName();

    var index = scope.lastIndexOf(':');
    var action = index === -1 ? scope : scope.substring(index + 1);

    var id = identity.getId();

    var attribute = action + ':' + id;
    var check = resource.getAttribute(attribute);

    if (check) {
        $evaluation.grant();
    } else {
        $evaluation.deny();
    }

} catch (exception) {
    print('exception', exception);
    $evaluation.deny();
}
