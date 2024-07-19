from django.contrib import admin
from django.urls import path
from test1 import views


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/save-json', views.save_json, name='save_json'),
    path('files/<str:concept>/<str:filename>', views.get_file, name='get_file'),
    path('user/<str:email>', views.check_email, name='check_email'),
    path('file_content/<str:folder_name>/<str:filename>', views.file_content, name='file_content'),
    path('submitReview',views.submitReview,name='submitReview'),
    path('n_q_folder_contents/<str:folder_name>', views.n_q_folder_contents, name='folder_contents'),
    path('a_q_folder_contents/<str:folder_name>', views.a_q_folder_contents, name='folder_contents'),
    path('n_t_folder_contents/<str:folder_name>', views.n_t_folder_contents, name='folder_contents'),
    path('a_t_folder_contents/<str:folder_name>', views.a_t_folder_contents, name='folder_contents'),
    path('files/<concept>', views.get_files_in_folder, name='get_files'),
    path('api/get-file', views.get_blob_file, name='get_blob_file'),
]
