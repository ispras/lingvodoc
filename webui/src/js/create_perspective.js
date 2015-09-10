'use strict';

var app = angular.module('CreatePerspective', ['ngDraggable']);


app.controller('MainCtrl', ['$scope', function ($scope) {

    $scope.draggableObjects = [{name:'one'}, {name:'two'}, {name:'three'}];
        $scope.droppedObjects = [];

        $scope.onDropComplete=function(data,evt){
            var index = $scope.droppedObjects.indexOf(data);
            if (index == -1) {
                $scope.droppedObjects.push(data);
            }

            console.log("Drop success");
        };
        $scope.onDragSuccess=function(data, evt){
            var index = $scope.droppedObjects.indexOf(data);
            if (index > -1) {
                $scope.droppedObjects.splice(index, 1);
            }

            console.log("Drag success");
        };

        $scope.onDragStop=function(data, evt){
            console.log("Drag stop");
        };


        var inArray = function(array, obj) {
            var index = array.indexOf(obj);
        }
}]);