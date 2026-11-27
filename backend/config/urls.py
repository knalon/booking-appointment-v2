from django.contrib import admin
from django.urls import path, include

from apps.data_imports.admin_views import imports_page

admin.site.index_template = "data_imports/admin_index.html"

urlpatterns = [
    path("admin/master-data/", admin.site.admin_view(imports_page), name="admin-imports"),
    path("admin/", admin.site.urls),
    path("api/directory/", include("apps.directory.urls")),
    path("api/imports/", include("apps.data_imports.urls")),
    path("api/nlp/", include("apps.nlp.urls")),
    path("api/matching/", include("apps.matching.urls")),
    path("api/coordinator/", include("apps.coordinator.urls")),
    path("api/scheduling/", include("apps.scheduling.urls")),
]
