from django.contrib import admin
from .models import ImportBatch

@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ("id", "dataset", "source_filename", "state", "total_rows", "created_by", "created_at", "expires_at")
    list_filter = ("dataset", "state", "created_at")
    search_fields = ("id", "source_filename", "created_by__username")
    readonly_fields = ("id", "dataset", "source_filename", "state", "records", "errors", "total_rows", "valid_rows", "created_count", "updated_count", "unchanged_count", "preview_digest", "created_by", "created_at", "expires_at", "confirmed_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
