from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("chat/start/", views.start_chat, name="start_chat"),
    path("chat/<uuid:token>/", views.chat_page, name="chat_page"),
    path("chat/<uuid:token>/send/", views.chat_send, name="chat_send"),
    path("chat/<uuid:token>/whatsapp/", views.whatsapp_redirect, name="whatsapp_redirect"),
]
