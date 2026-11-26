from datetime import timedelta
from django.contrib import admin
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.db import IntegrityError
from .models import ImportBatch
from .services import HEADERS, parse_and_validate_csv, plan, confirm_import_batch, expire_stale_batches


def imports_page(request):
    expire_stale_batches()
    error=None; batch=None
    if request.method=='POST':
        action=request.POST.get('action')
        try:
            if action=='confirm':
                batch=get_object_or_404(ImportBatch,pk=request.POST.get('batch_id'),created_by=request.user)
                confirm_import_batch(batch,request.user)
                return redirect('admin-imports')
            dataset=request.POST.get('dataset'); uploaded=request.FILES.get('file')
            if dataset not in HEADERS or not uploaded or not uploaded.name.lower().endswith('.csv'): raise ValueError('Choose a dataset and CSV file.')
            records,errors=parse_and_validate_csv(uploaded,dataset)
            counts,digest=plan(dataset,records) if not errors else ((0,0,0),'')
            batch=ImportBatch.objects.create(dataset=dataset,source_filename=uploaded.name[:255],state='invalid' if errors else 'previewed',records=records if not errors else [],errors=errors,total_rows=len(records),valid_rows=len(records)-len({e['row'] for e in errors}),created_count=counts[0],updated_count=counts[1],unchanged_count=counts[2],preview_digest=digest,created_by=request.user,expires_at=timezone.now()+timedelta(hours=24))
        except (ValueError,IntegrityError) as exc:
            error=str(exc) if isinstance(exc,ValueError) else 'Database conflict. No changes saved; preview again.'
    context={**admin.site.each_context(request),'title':'Master data CSV management','datasets':HEADERS.keys(),'batch':batch,'error':error,'history':ImportBatch.objects.filter(created_by=request.user)[:30]}
    return render(request,'data_imports/management.html',context)
