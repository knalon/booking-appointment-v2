from datetime import timedelta

from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ImportBatch
from .services import parse_and_validate_csv, plan, confirm_import_batch, expire_stale_batches


class CSVImportPreviewView(APIView):
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, dataset):
        expire_stale_batches()
        if dataset not in ImportBatch.Dataset.values:
            return Response({"detail": "Unknown dataset."}, status=status.HTTP_400_BAD_REQUEST)
        uploaded = request.FILES.get("file")
        if not uploaded or not uploaded.name.lower().endswith(".csv"):
            return Response({"detail": "Upload a .csv file using the 'file' field."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            records, errors = parse_and_validate_csv(uploaded, dataset)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        (created_count, updated_count, unchanged_count), digest = plan(dataset, records) if not errors else ((0, 0, 0), "")
        batch = ImportBatch.objects.create(
            dataset=dataset,
            source_filename=uploaded.name[:255],
            state=ImportBatch.State.INVALID if errors else ImportBatch.State.PREVIEWED,
            records=records if not errors else [],
            errors=errors,
            total_rows=len(records),
            valid_rows=len(records) - len({error["row"] for error in errors}),
            created_count=created_count,
            updated_count=updated_count,
            unchanged_count=unchanged_count,
            preview_digest=digest,
            created_by=request.user,
            expires_at=timezone.now() + timedelta(hours=24),
        )
        return Response({
            "batch_id": str(batch.id),
            "dataset": batch.dataset,
            "filename": batch.source_filename,
            "state": batch.state,
            "total_rows": batch.total_rows,
            "valid_rows": batch.valid_rows,
            "invalid_rows": len({error["row"] for error in errors}),
            "would_create": created_count,
            "would_update": updated_count,
            "would_unchanged": unchanged_count,
            "errors": errors[:200],
            "errors_truncated": len(errors) > 200,
            "expires_at": batch.expires_at.isoformat(),
            "can_confirm": not errors,
        }, status=status.HTTP_201_CREATED)


class CSVImportConfirmView(APIView):
    permission_classes = [IsAdminUser]
    parser_classes = [JSONParser]

    def post(self, request, batch_id):
        batch = get_object_or_404(ImportBatch, pk=batch_id, created_by=request.user)
        try:
            created_count, updated_count, unchanged_count = confirm_import_batch(batch, request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except IntegrityError:
            return Response({"detail": "Database conflict. No changes saved; preview again."}, status=409)
        batch.refresh_from_db()
        return Response({
            "batch_id": str(batch.id),
            "dataset": batch.dataset,
            "state": batch.state,
            "created": created_count,
            "updated": updated_count,
            "unchanged": unchanged_count,
            "total_imported": created_count + updated_count + unchanged_count,
            "confirmed_at": batch.confirmed_at.isoformat() if batch.confirmed_at else None,
        }, status=status.HTTP_200_OK)


class ImportBatchDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, batch_id):
        expire_stale_batches()
        batch = get_object_or_404(ImportBatch, pk=batch_id, created_by=request.user)
        return Response({
            "batch_id": str(batch.id),
            "dataset": batch.dataset,
            "filename": batch.source_filename,
            "state": batch.state,
            "total_rows": batch.total_rows,
            "valid_rows": batch.valid_rows,
            "errors": batch.errors[:200],
            "created": batch.created_count,
            "updated": batch.updated_count,
            "unchanged": batch.unchanged_count,
            "created_at": batch.created_at.isoformat(),
            "expires_at": batch.expires_at.isoformat(),
            "confirmed_at": batch.confirmed_at.isoformat() if batch.confirmed_at else None,
        })

from django.http import HttpResponse
from .services import HEADERS, MODELS, export_row
import csv

class CSVExportView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, dataset):
        if dataset not in HEADERS:
            return Response({'detail':'Unknown dataset.'},status=400)
        model,key,_=MODELS[dataset]
        if dataset == "faculty" and any(f.additional_modules_taught for f in model.objects.all()):
            return Response({"detail":"Unresolved legacy teaching assignments exist. Import the revised faculty CSV before exporting."},status=409)
        response=HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition']=f'attachment; filename="{dataset}.csv"'
        response.write('\ufeff')
        writer=csv.DictWriter(response,fieldnames=HEADERS[dataset]);writer.writeheader()
        for obj in model.objects.order_by(key): writer.writerow(export_row(dataset,obj))
        return response
