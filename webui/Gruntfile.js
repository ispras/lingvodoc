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
                    {expand: true, flatten: true, src: ['bower_components/bootstrap-sass/assets/fonts/bootstrap/*'], dest: '../lingvodoc/static/fonts/bootstrap/', filter: 'isFile'},
                    {expand: true, flatten: true, src: ['src/templates/*'], dest: '../lingvodoc/templates/', filter: 'isFile'}
                ],
            },
        },
        uglify: {
            options: {
                compress: false
            },
            lingvodoc: {
                src: [
                    'bower_components/jquery/dist/jquery.js',
                    'bower_components/angular/angular.js',
                    'bower_components/ngDraggable/ngDraggable.js',
                    'bower_components/bootstrap-sass/assets/javascripts/bootstrap.js',
                    'bower_components/angular-bootstrap/ui-bootstrap.js',
                    'bower_components/wavesurfer.js/dist/wavesurfer.min.js',
                    'bower_components/bootstrap-validator/dist/validator.js',
                    'src/js/lingvodemo.js',
                    'src/js/lingvodocedit.js',
                    'src/js/lingvodocview.js',
                    'src/js/lingvowave.js',
                    'src/js/create_perspective.js',
                    'src/js/dashboard.js'

                ],
                dest: '../lingvodoc/static/js/lingvodoc.js'
            }
        }
    });
    grunt.loadNpmTasks('grunt-contrib-copy');
    grunt.loadNpmTasks('grunt-contrib-uglify');
    grunt.loadNpmTasks('grunt-contrib-sass');
    grunt.loadNpmTasks('grunt-contrib-watch');
    grunt.registerTask('buildcss', ['sass:dist']);
};
