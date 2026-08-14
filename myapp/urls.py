from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView
from django.contrib.sitemaps.views import sitemap
from myapp import views


urlpatterns = [
    path("admin/", admin.site.urls),
    path('', views.homepage,name='home'),
    path('order_post/', views.order_post),
    path('raz_pay/<amount>', views.raz_pay),
    path('userpayment_post/', views.userpayment_post),
    path('emailenquiry/', views.emailenquiry),
    path('blog/', views.blog_page,name='blog'),
    path('send-otp/', views.send_otp, name='send_otp'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
]