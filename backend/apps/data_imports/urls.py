from django.urls import path
from .views import CSVImportPreviewView, CSVImportConfirmView, ImportBatchDetailView, CSVExportView

urlpatterns = [
    path("<str:dataset>/export/", CSVExportView.as_view(), name="csv-export"),
    path("<str:dataset>/preview/", CSVImportPreviewView.as_view(), name="csv-import-preview"),
    path("batches/<uuid:batch_id>/confirm/", CSVImportConfirmView.as_view(), name="csv-import-confirm"),
    path("batches/<uuid:batch_id>/", ImportBatchDetailView.as_view(), name="csv-import-batch-detail"),
]
