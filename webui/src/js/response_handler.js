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

    function success(status, message) {
        show(status, message, 500);
    }

    function error(status, message) {
        show(status, message, 5000);
    }

    return {
        success: success,
        error: error
    };
}