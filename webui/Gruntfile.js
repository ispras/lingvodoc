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

            },

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
                ],
            },
        },
        uglify: {
            options: {
                compress: false,
                mangle: false
            },
            lingvodoc: {
                src: [
                    'bower_components/jquery/dist/jquery.js',
                    'bower_components/angular/angular.js',
                    'bower_components/bootstrap-sass/assets/javascripts/bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap-tpls.js',
                    'bower_components/wavesurfer.js/dist/wavesurfer.min.js',
                    'bower_components/bootstrap-validator/dist/validator.js',
                    'bower_components/angular-route/angular-route.js',
                    'bower_components/angular-ui-router/release/angular-ui-router.js',
                    'bower_components/angular-animate/angular-animate.js',
                    'bower_components/autocomplete/script/autocomplete.js',
                    'src/js/lingvodemo.js',
                    'src/js/edit_dictionary.js',
                    'src/js/view_dictionary.js',
                    'src/js/lingvowave.js',
                    'src/js/dashboard.js',
                    'src/js/languages.js',
                    'src/js/create_dictionary.js',
                    'src/js/blob_upload.js'
                ],
                dest: '../lingvodoc/static/js/lingvodoc.js'
            },
            login: {
                src: [
                    'bower_components/jquery/dist/jquery.js',
                    'bower_components/angular/angular.js',
                    'bower_components/bootstrap-sass/assets/javascripts/bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap-tpls.js',
                    'bower_components/bootstrap-validator/dist/validator.js'
                ],
                dest: '../lingvodoc/static/js/login.js'
            },
            home: {
                src: [
                    'bower_components/jquery/dist/jquery.js',
                    'bower_components/angular/angular.js',
                    'bower_components/bootstrap-sass/assets/javascripts/bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap-tpls.js',
                    'src/js/home.js'
                ],
                dest: '../lingvodoc/static/js/home.js'
            },
            dashboard: {
                src: [
                    'bower_components/jquery/dist/jquery.js',
                    'bower_components/angular/angular.js',
                    'bower_components/bootstrap-sass/assets/javascripts/bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap-tpls.js',
                    'bower_components/wavesurfer.js/dist/wavesurfer.min.js',
                    'bower_components/autocomplete/script/autocomplete.js',
                    'src/js/dashboard.js'
                ],
                dest: '../lingvodoc/static/js/dashboard.js'
            },
            languages: {
                src: [
                    'bower_components/jquery/dist/jquery.js',
                    'bower_components/angular/angular.js',
                    'bower_components/bootstrap-sass/assets/javascripts/bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap-tpls.js',
                    'bower_components/wavesurfer.js/dist/wavesurfer.min.js',
                    'bower_components/autocomplete/script/autocomplete.js',
                    'src/js/languages.js'
                ],
                dest: '../lingvodoc/static/js/languages.js'
            },
            createdictionary: {
                src: [
                    'bower_components/jquery/dist/jquery.js',
                    'bower_components/angular/angular.js',
                    'bower_components/bootstrap-sass/assets/javascripts/bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap-tpls.js',
                    'bower_components/angular-route/angular-route.js',
                    'bower_components/angular-ui-router/release/angular-ui-router.js',
                    'bower_components/angular-animate/angular-animate.js',
                    'bower_components/autocomplete/script/autocomplete.js',
                    'src/js/create_dictionary.js'
                ],
                dest: '../lingvodoc/static/js/create-dictionary.js'
            },
            viewdictionary: {
                src: [
                    'bower_components/jquery/dist/jquery.js',
                    'bower_components/angular/angular.js',
                    'bower_components/bootstrap-sass/assets/javascripts/bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap-tpls.js',
                    'bower_components/wavesurfer.js/dist/wavesurfer.min.js',
                    'src/js/elan.js',
                    'src/js/view_dictionary.js',
                    'src/js/lingvowave.js'
                ],
                dest: '../lingvodoc/static/js/view-dictionary.js'
            },
            editdictionary: {
                src: [
                    'bower_components/jquery/dist/jquery.js',
                    'bower_components/angular/angular.js',
                    'bower_components/bootstrap-sass/assets/javascripts/bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap-tpls.js',
                    'bower_components/wavesurfer.js/dist/wavesurfer.min.js',
                    'src/js/elan.js',
                    'src/js/util.js',
                    'src/js/edit_dictionary.js',
                    'src/js/lingvowave.js'
                ],
                dest: '../lingvodoc/static/js/edit-dictionary.js'
            },
            userupload: {
                src: [
                    'bower_components/jquery/dist/jquery.js',
                    'bower_components/angular/angular.js',
                    'bower_components/bootstrap-sass/assets/javascripts/bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap-tpls.js',
                    'bower_components/wavesurfer.js/dist/wavesurfer.min.js',
                    'src/js/user_upload.js'
                ],
                dest: '../lingvodoc/static/js/user-upload.js'
            }
        }
    });


    grunt.loadNpmTasks('grunt-contrib-copy');
    grunt.loadNpmTasks('grunt-contrib-uglify');
    grunt.loadNpmTasks('grunt-contrib-sass');
    grunt.loadNpmTasks('grunt-contrib-watch');
    grunt.registerTask('buildcss', ['sass:dist']);
};
