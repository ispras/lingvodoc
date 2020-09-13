# creating users (keys are hidden)
mc admin user add minio lingvodoc_main_access_key_username_not_real_here_of_course lingvodoc_main_secret_key_not_real_here_of_course
mc admin user add minio lingvodoc_tsu_access_key_username_not_real_here_of_course lingvodoc_tsu_secret_key_not_real_here_of_course
mc admin user add minio lingvodoc_staging_access_key_username_not_real_here_of_course lingvodoc_staging_secret_key_not_real_here_of_course
mc admin user add minio lingvodoc_dev_access_key_username_not_real_here_of_course lingvodoc_dev_secret_key_not_real_here_of_course

# that sets public access to objects
mc policy set download "minio/lingvodoc-temp-files/lingvodoc.ispras.ru/*"
mc policy set download "minio/lingvodoc-temp-files/lingvodoc.tsu.ru/*"
mc policy set download "minio/lingvodoc-temp-files/staging/*"
mc policy set download "minio/lingvodoc-temp-files/dev/*"

# retention policy for subpaths
mc ilm import minio/lingvodoc-temp-files < ./retention_policies.json

# access policies for subpaths (uploading for futher usage)
mc admin policy add minio lingvodoc_temp_objects_rw_prod_main ./lingvodoc_temp_objects_rw_prod_main.json
mc admin policy add minio lingvodoc_temp_objects_rw_prod_tomsk ./lingvodoc_temp_objects_rw_prod_tomsk.json
mc admin policy add minio lingvodoc_temp_objects_rw_staging ./lingvodoc_temp_objects_rw_staging.json
mc admin policy add minio lingvodoc_temp_objects_rw_dev ./lingvodoc_temp_objects_rw_dev.json

# access policies setting
mc admin policy set "minio/lingvodoc-temp-files/lingvodoc.ispras.ru/*" lingvodoc_temp_objects_rw_prod_main user=lingvodoc_main_access_key_username_not_real_here_of_course
mc admin policy set "minio/lingvodoc-temp-files/lingvodoc.tsu.ru/*" lingvodoc_temp_objects_rw_prod_tomsk user=lingvodoc_temp_objects_rw_prod_tomsk
mc admin policy set "minio/lingvodoc-temp-files/staging/*" lingvodoc_temp_objects_rw_staging user=lingvodoc_temp_objects_rw_prod_tomsk
mc admin policy set "minio/lingvodoc-temp-files/dev/*" lingvodoc_temp_objects_rw_dev user=lingvodoc_temp_objects_rw_prod_tomsk
