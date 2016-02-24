module.exports = function(grunt) {
    grunt.initConfig({
        sass: {
            dev: {
                options: {
                    style: 'expanded'
                },
                files: {
                    '../lingvodoc/static/css/lingvodoc.css': 'src/sass/lingvodoc.scss'
                }
            },
            dist: {
                options: {
                    style: 'compressed',
                    loadPath: 'bower_components/bootstrap-sass/assets/stylesheets'
                },
                files: {
                    '../lingvodoc/static/css/lingvodoc.css': 'src/sass/lingvodoc.scss'
                }

            }

        },
        watch: {
            sass: {
                files: 'src/sass/*.scss',
                tasks: ['sass:dev']
            }
        },
        copy: {
            main: {
                files: [
                    {
                        expand: true,
                        flatten: true,
                        src: ['bower_components/bootstrap-sass/assets/fonts/bootstrap/*'],
                        dest: '../lingvodoc/static/fonts/bootstrap/',
                        filter: 'isFile'
                    },
                    {
                        expand: true,
                        flatten: true,
                        src: ['src/templates/*'],
                        dest: '../lingvodoc/templates/',
                        filter: 'isFile'
                    }
                ]
            }
        },
        uglify: {
            options: {
                compress: false,
                mangle: false,
                beautify: true
            },
            login: {
                src: [
                    'bower_components/jquery/dist/jquery.js',
                    'bower_components/lodash/lodash.js',
                    'bower_components/angular/angular.js',
                    'bower_components/bootstrap-sass/assets/javascripts/bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap-tpls.js',
                    'bower_components/bootstrap-validator/dist/validator.js',
                    'src/js/response_handler.js'
                ],
                dest: '../lingvodoc/static/js/login.js'
            },
            home: {
                src: [
                    'bower_components/jquery/dist/jquery.js',
                    'bower_components/lodash/lodash.js',
                    'bower_components/angular/angular.js',
                    'bower_components/bootstrap-sass/assets/javascripts/bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap-tpls.js',
                    'src/js/util.js',
                    'src/js/api.js',
                    'src/js/response_handler.js',
                    'src/js/home.js'
                ],
                dest: '../lingvodoc/static/js/home.js'
            },
            dashboard: {
                src: [
                    'bower_components/jquery/dist/jquery.js',
                    'bower_components/lodash/lodash.js',
                    'bower_components/angular/angular.js',
                    'bower_components/bootstrap-sass/assets/javascripts/bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap-tpls.js',
                    'bower_components/ngmap/build/scripts/ng-map.js',
                    'src/js/util.js',
                    'src/js/api.js',
                    'src/js/response_handler.js',
                    'src/js/dashboard.js'
                ],
                dest: '../lingvodoc/static/js/dashboard.js'
            },
            languages: {
                src: [
                    'bower_components/jquery/dist/jquery.js',
                    'bower_components/lodash/lodash.js',
                    'bower_components/angular/angular.js',
                    'bower_components/bootstrap-sass/assets/javascripts/bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap-tpls.js',
                    'bower_components/autocomplete/script/autocomplete.js',
                    'src/js/util.js',
                    'src/js/api.js',
                    'src/js/languages.js',
                    'src/js/response_handler.js'
                ],
                dest: '../lingvodoc/static/js/languages.js'
            },
            createdictionary: {
                src: [
                    'bower_components/jquery/dist/jquery.js',
                    'bower_components/lodash/lodash.js',
                    'bower_components/angular/angular.js',
                    'bower_components/bootstrap-sass/assets/javascripts/bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap-tpls.js',
                    'bower_components/angular-route/angular-route.js',
                    'bower_components/angular-ui-router/release/angular-ui-router.js',
                    'bower_components/angular-animate/angular-animate.js',
                    'bower_components/autocomplete/script/autocomplete.js',
                    'src/js/util.js',
                    'src/js/api.js',
                    'src/js/response_handler.js',
                    'src/js/create_dictionary.js'
                ],
                dest: '../lingvodoc/static/js/create-dictionary.js'
            },
            viewdictionary: {
                src: [
                    'bower_components/jquery/dist/jquery.js',
                    'bower_components/lodash/lodash.js',
                    'bower_components/angular/angular.js',
                    'bower_components/bootstrap-sass/assets/javascripts/bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap-tpls.js',
                    'bower_components/wavesurfer.js/dist/wavesurfer.min.js',
                    'bower_components/wavesurfer.js/dist/plugin/wavesurfer.regions.min.js',
                    'bower_components/wavesurfer.js/dist/plugin/wavesurfer.spectrogram.min.js',
                    'src/js/model.js',
                    'src/js/elan.js',
                    'src/js/util.js',
                    'src/js/api.js',
                    'src/js/response_handler.js',
                    'src/js/view_dictionary.js',
                    'src/js/lingvowave.js'
                ],
                dest: '../lingvodoc/static/js/view-dictionary.js'
            },
            publishdictionary: {
                src: [
                    'bower_components/jquery/dist/jquery.js',
                    'bower_components/lodash/lodash.js',
                    'bower_components/angular/angular.js',
                    'bower_components/bootstrap-sass/assets/javascripts/bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap-tpls.js',
                    'bower_components/wavesurfer.js/dist/wavesurfer.min.js',
                    'bower_components/wavesurfer.js/dist/plugin/wavesurfer.regions.min.js',
                    'bower_components/wavesurfer.js/dist/plugin/wavesurfer.spectrogram.min.js',
                    'src/js/model.js',
                    'src/js/elan.js',
                    'src/js/util.js',
                    'src/js/api.js',
                    'src/js/response_handler.js',
                    'src/js/publish_dictionary.js',
                    'src/js/lingvowave.js'
                ],
                dest: '../lingvodoc/static/js/publish-dictionary.js'
            },
            editdictionary: {
                src: [
                    'bower_components/jquery/dist/jquery.js',
                    'bower_components/lodash/lodash.js',
                    'bower_components/angular/angular.js',
                    'bower_components/bootstrap-sass/assets/javascripts/bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap-tpls.js',
                    'bower_components/wavesurfer.js/dist/wavesurfer.min.js',
                    'bower_components/wavesurfer.js/dist/plugin/wavesurfer.regions.min.js',
                    'bower_components/wavesurfer.js/dist/plugin/wavesurfer.spectrogram.min.js',
                    'src/js/model.js',
                    'src/js/elan.js',
                    'src/js/util.js',
                    'src/js/api.js',
                    'src/js/response_handler.js',
                    'src/js/edit_dictionary.js',
                    'src/js/lingvowave.js'
                ],
                dest: '../lingvodoc/static/js/edit-dictionary.js'
            },
            userupload: {
                src: [
                    'bower_components/jquery/dist/jquery.js',
                    'bower_components/lodash/lodash.js',
                    'bower_components/angular/angular.js',
                    'bower_components/bootstrap-sass/assets/javascripts/bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap-tpls.js',
                    'src/js/response_handler.js',
                    'src/js/user_upload.js'
                ],
                dest: '../lingvodoc/static/js/user-upload.js'
            },
            profile: {
                src: [
                    'bower_components/jquery/dist/jquery.js',
                    'bower_components/lodash/lodash.js',
                    'bower_components/angular/angular.js',
                    'bower_components/bootstrap-sass/assets/javascripts/bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap-tpls.js',
                    'src/js/util.js',
                    'src/js/api.js',
                    'src/js/response_handler.js',
                    'src/js/profile.js'
                ],
                dest: '../lingvodoc/static/js/profile.js'
            },
            organizations: {
                src: [
                    'bower_components/jquery/dist/jquery.js',
                    'bower_components/lodash/lodash.js',
                    'bower_components/angular/angular.js',
                    'bower_components/bootstrap-sass/assets/javascripts/bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap-tpls.js',
                    'src/js/util.js',
                    'src/js/api.js',
                    'src/js/response_handler.js',
                    'src/js/organizations.js'
                ],
                dest: '../lingvodoc/static/js/organizations.js'
            },
            merge_master: {
                src: [
                    'bower_components/jquery/dist/jquery.js',
                    'bower_components/lodash/lodash.js',
                    'bower_components/angular/angular.js',
                    'bower_components/bootstrap-sass/assets/javascripts/bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap-tpls.js',
                    'bower_components/angular-ui-router/release/angular-ui-router.js',
                    'src/js/util.js',
                    'src/js/api.js',
                    'src/js/response_handler.js',
                    'src/js/merge_master.js'
                ],
                dest: '../lingvodoc/static/js/merge-master.js'
            },
            maps: {
                src: [
                    'bower_components/jquery/dist/jquery.js',
                    'bower_components/lodash/lodash.js',
                    'bower_components/angular/angular.js',
                    'bower_components/bootstrap-sass/assets/javascripts/bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap-tpls.js',
                    'bower_components/angular-animate/angular-animate.js',
                    'bower_components/ngmap/build/scripts/ng-map.js',
                    'bower_components/wavesurfer.js/dist/wavesurfer.min.js',
                    'bower_components/wavesurfer.js/dist/plugin/wavesurfer.regions.min.js',
                    'bower_components/wavesurfer.js/dist/plugin/wavesurfer.spectrogram.min.js',
                    'src/js/elan.js',
                    'src/js/lingvowave.js',
                    'src/js/util.js',
                    'src/js/api.js',
                    'src/js/response_handler.js',
                    'src/js/maps.js'
                ],
                dest: '../lingvodoc/static/js/maps.js'
            }
        }
    });


    grunt.loadNpmTasks('grunt-contrib-copy');
    grunt.loadNpmTasks('grunt-contrib-uglify');
    grunt.loadNpmTasks('grunt-contrib-sass');
    grunt.loadNpmTasks('grunt-contrib-watch');
    grunt.registerTask('buildcss', ['sass:dist']);
};
