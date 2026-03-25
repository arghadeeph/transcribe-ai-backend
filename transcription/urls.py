from django.urls import path
from .views import TranscribeView
from .views_2 import UploadV2View, stream_v2, TranslateView, stream_translate


urlpatterns = [
    path('v1/transcribe/', TranscribeView.as_view()),
    path('v2/upload/', UploadV2View.as_view()),
    path('v2/stream/', stream_v2),
    path('v2/translate/', TranslateView.as_view()),
    path("v2/stream-translate/", stream_translate),
]