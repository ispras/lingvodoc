/**
 * Base class for all controllers with waveform element
 * @param $scope
 * @constructor
 */
function WaveSurferController($scope) {

    var activeUrl = null;

    $scope.play = function(url) {

        if (!$scope.wavesurfer) {
            return;
        }

        activeUrl = url;

        $scope.wavesurfer.once('ready', function() {
            $scope.wavesurfer.play();
            $scope.$apply();
        });

        $scope.wavesurfer.load(activeUrl);
    };

    $scope.playPause = function() {
        $scope.wavesurfer.playPause();
    };

    $scope.isPlaying = function(url) {
        return url == activeUrl;
    };

    $scope.isMediaFileAvailable = function() {
        return activeUrl != null;
    };

    // signal handlers
    $scope.$on('wavesurferInit', function(e, wavesurfer, container) {

        $scope.wavesurfer = wavesurfer;

        $scope.wavesurfer.on('play', function() {
            $scope.paused = false;
        });

        $scope.wavesurfer.on('pause', function() {
            $scope.paused = true;
        });

        $scope.wavesurfer.on('finish', function() {
            $scope.paused = true;
            $scope.wavesurfer.seekTo(0);
            $scope.$apply();
        });

        //$scope.wavesurfer.on('ready', function () {
        //
        //    var spectrogramContainer =_.find(container[0].parentElement.children, function(e) {
        //        return e.tagName.toUpperCase() == 'WAVESURFER-SPECTROGRAM';
        //    });
        //
        //    if (spectrogramContainer) {
        //        var spectrogram = Object.create(WaveSurfer.Spectrogram);
        //        spectrogram.init({
        //            wavesurfer: $scope.wavesurfer,
        //            container: spectrogramContainer,
        //            fftSamples: 128
        //        });
        //    }
        //});

    });

    $scope.$on('modal.closing', function(e) {
        $scope.wavesurfer.stop();
        $scope.wavesurfer.destroy();
    });
}
