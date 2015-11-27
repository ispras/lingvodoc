function responseHandler($timeout, $modal) {

    function show(status, message, t) {

        var timeout = t || 2000;

        var controller = function($scope, $modalInstance) {
            $scope.status = status;
            $scope.message = message;

            $scope.ok = function() {
                $modalInstance.close();
            };
        };

        var inst = $modal.open({
            animation: true,
            templateUrl: 'responseHandlerModal.html',
            controller: controller,
            size: 'sm',
            backdrop: 'static',
            keyboard: false
        });

        $timeout(function() {
            inst.dismiss();
        }, timeout);
    }

    function success(message) {
        show('success', message, 5000);
    }

    function error(message) {
        show('error', message, 5000);
    }

    function yesno(status, message, callback) {

        var controller = function($scope, $modalInstance) {
            $scope.status = status;
            $scope.message = message;

            $scope.yes = function() {
                $modalInstance.close(true);
            };

            $scope.no = function() {
                $modalInstance.close(false);
            };
        };

        $modal.open({
            animation: true,
            templateUrl: 'responseHandlerYesNoModal.html',
            controller: controller,
            size: 'lg',
            backdrop: 'static',
            keyboard: false
        }).result.then(function(result) {
                callback(result);
        }, function() {
                callback(false);
        });
    }

    return {
        'success': success,
        'error': error,
        'yesno': yesno
    };
}