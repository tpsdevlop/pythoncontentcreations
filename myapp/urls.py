# In your_app_name/urls.py
from django.urls import path
from . import views
from .views import QuestionView, TemplatesView,RenderTemplateView
urlpatterns = [
    path('save-data/', views.save_data, name='save_data'),
    path('load-data/', views.load_data, name='load_data'),
    path('save-json/', views.save_json, name='save_json'),
    path('get-dropdown-data/', views.get_dropdown_data, name='get_dropdown_data'),
    path('upload-file/', views.upload_file, name='upload_file'),
    path('questions/', QuestionView.as_view(), name='questions'),
    path('templates/', TemplatesView.as_view(), name='templates'),
    path('render-template/<str:template_name>', RenderTemplateView.as_view(), name='render_template'),
]