import csv, io, json, hashlib
from datetime import date
from django.db import transaction
from django.utils import timezone
from apps.directory.models import Qualification, AcademicModule, AcademicTopic, QualificationModule, FacultyProfile, FacultyExpertise, LearnerProfile
from .models import ImportBatch
from .validation import (_validate_faculty, _validate_learner, _split_list, _parse_time, MAX_UPLOAD_BYTES, MAX_ROWS, FACULTY_HEADERS, LEARNER_HEADERS)

HEADERS = {'qualifications':['Qualification_Code','Qualification_Name','Status'], 'modules':['Module_Code','Module_Name','Department','Status'], 'curriculum':['Qualification_Code','Module_Code','Sequence','Status'], 'topics':['Topic_Code','Module_Code','Topic_Name','Status'], 'faculty':FACULTY_HEADERS, 'learners':LEARNER_HEADERS}
MODELS = {'qualifications':(Qualification,'code','Qualification_Code'), 'modules':(AcademicModule,'code','Module_Code'), 'curriculum':(QualificationModule,'pk','Qualification_Code'), 'topics':(AcademicTopic,'code','Topic_Code'), 'faculty':(FacultyProfile,'faculty_id','Faculty_ID'), 'learners':(LearnerProfile,'learner_id','Learner_ID')}
LIST_FIELDS = {'Qualifications','Modules_Taught','Consultation_Modes','Languages','Working_Days','Preferred_Consultation_Mode','Preferred_Language','Qualification_Codes','Current_Module_Codes'}

def split(s): return sorted(set(_split_list(s)))
def join(xs): return '; '.join(sorted(set(xs)))
def related(qs): return join(qs.values_list('code',flat=True))
def status(active): return 'Active' if active else 'Inactive'
def hhmm(t): return t.strftime('%H:%M') if t else ''
def mapping_json(mappings):
    return json.dumps(sorted(mappings,key=lambda m:m['module_code']),sort_keys=True,ensure_ascii=False,separators=(',',':'))

def lookup(dataset,row):
    if dataset == 'curriculum':
        return QualificationModule.objects.filter(qualification__code=row['Qualification_Code'],module__code=row['Module_Code']).first()
    model,key,idfield=MODELS[dataset]
    return model.objects.filter(**{key:row[idfield]}).first()


def canonical(row):
    row = dict(row)
    for field in LIST_FIELDS & row.keys(): row[field] = join(split(row[field]))
    if 'Expertise_Mappings' in row:
        mappings=json.loads(row['Expertise_Mappings'])
        for m in mappings:
            m['topics']=sorted(set(m.get('topics',[])))
            m['qualifications']=sorted(set(m.get('qualifications',[])))
            m['verified_by']=m.get('verified_by','')
            m['last_reviewed']=m.get('last_reviewed') or ''
        row['Expertise_Mappings']=mapping_json(mappings)
    if 'Sequence' in row: row['Sequence']=str(int(row['Sequence']))
    if 'Teaching_Experience_Years' in row: row['Teaching_Experience_Years']=str(int(row['Teaching_Experience_Years']))
    for field in ('Working_Hours_Start','Working_Hours_End'):
        if field in row: row[field]=hhmm(_parse_time(row[field],field)) if row[field] else ''
    return row

def export_row(dataset,obj):
    if dataset=='qualifications': return dict(Qualification_Code=obj.code,Qualification_Name=obj.name,Status=status(obj.is_active))
    if dataset=='modules': return dict(Module_Code=obj.code,Module_Name=obj.name,Department=obj.department,Status=status(obj.is_active))
    if dataset=='curriculum': return dict(Qualification_Code=obj.qualification.code,Module_Code=obj.module.code,Sequence=str(obj.sequence),Status=status(obj.is_active))
    if dataset=='topics': return dict(Topic_Code=obj.code,Module_Code=obj.module.code,Topic_Name=obj.name,Status=status(obj.is_active))
    if dataset=='faculty':
        maps=[]
        for m in obj.expertise_mappings.select_related('module').all():
            maps.append(dict(module_code=m.module.code,topics=sorted(m.catalogue_topics.values_list('code',flat=True)),expertise_level=m.expertise_level,qualifications=sorted(m.qualifications.values_list('code',flat=True)),verified_by=m.verified_by,last_reviewed=m.last_reviewed.isoformat() if m.last_reviewed else '',eligible_for_consultation=m.eligible_for_consultation))
        return dict(Faculty_ID=obj.faculty_id,Full_Name=obj.full_name,Email=obj.email,Department=obj.department,Qualifications=related(obj.qualifications),Modules_Taught=related(obj.modules_taught),Expertise_Mappings=mapping_json(maps),Teaching_Experience_Years=str(obj.teaching_experience_years),Consultation_Modes=join(obj.consultation_modes),Languages=join(obj.languages),Time_Zone=obj.time_zone,Working_Days=join(obj.working_days),Working_Hours_Start=hhmm(obj.working_hours_start),Working_Hours_End=hhmm(obj.working_hours_end),Status=obj.status)
    return dict(Learner_ID=obj.learner_id,Full_Name=obj.full_name,Email=obj.email,Qualification=obj.qualification.code if obj.qualification else '',Current_Module_Code=obj.current_module.code if obj.current_module else '',Current_Module_Codes=related(obj.current_modules),Time_Zone=obj.time_zone,Preferred_Consultation_Mode=join(obj.preferred_consultation_modes),Preferred_Language=join(obj.preferred_languages),Status=obj.status)

def refs(model,codes,field,errors):
    found=set(model.objects.filter(code__in=codes).values_list('code',flat=True))
    for code in sorted(set(codes)-found): errors.append((field,f'Unknown code: {code}. Import catalogue first.'))

def validate_row(dataset,row):
    errors=[]
    model,key,idfield=MODELS[dataset]
    ident=row.get(idfield,'')
    if not ident or len(ident)>30: errors.append((idfield,'Required identifier, maximum 30 characters.'))
    if row.get('Status') not in {'Active','Inactive'}: errors.append(('Status','Use Active or Inactive.'))
    if row.get('Status')=='Inactive':
        if dataset=='qualifications' and (LearnerProfile.objects.filter(qualification__code=ident,status='Active').exists() or FacultyProfile.objects.filter(qualifications__code=ident,status='Active').exists() or FacultyExpertise.objects.filter(qualifications__code=ident,eligible_for_consultation=True).exists()): errors.append(('Status','Reassign active learners and faculty and revoke affected expertise before archiving this qualification.'))
        if dataset=='modules' and (LearnerProfile.objects.filter(current_modules__code=ident,status='Active').exists() or FacultyProfile.objects.filter(modules_taught__code=ident,status='Active').exists() or FacultyExpertise.objects.filter(module__code=ident,eligible_for_consultation=True).exists() or QualificationModule.objects.filter(module__code=ident,is_active=True).exists()): errors.append(('Status','Remove active curriculum, teaching, enrolment and approved expertise references first.'))
        if dataset=='topics' and FacultyExpertise.objects.filter(catalogue_topics__code=ident,eligible_for_consultation=True).exists(): errors.append(('Status','Remove topic from approved expertise or revoke eligibility first.'))
    if dataset=='curriculum':
        refs(Qualification,[row.get('Qualification_Code','')],'Qualification_Code',errors)
        refs(AcademicModule,[row.get('Module_Code','')],'Module_Code',errors)
        try:
            if not 1 <= int(row.get('Sequence','')) <= 999: raise ValueError()
        except ValueError: errors.append(('Sequence','Use an integer from 1 to 999.'))
        return errors
    if dataset=='topics':
        import re
        if not re.fullmatch(r'[A-Z0-9][A-Z0-9_-]{0,29}',ident): errors.append((idfield,'Invalid topic code.'))
        name=row.get('Topic_Name',''); module=row.get('Module_Code','')
        if not name or len(name)>160: errors.append(('Topic_Name','Required name, maximum 160 characters.'))
        refs(AcademicModule,[module],'Module_Code',errors)
        if AcademicTopic.objects.filter(code=ident).exclude(module__code=module).exists(): errors.append(('Module_Code','Existing topic cannot move to another module.'))
        if AcademicTopic.objects.filter(module__code=module,name__iexact=name).exclude(code=ident).exists(): errors.append(('Topic_Name','Topic name already exists in this module.'))
        return errors
    if dataset in ('qualifications','modules'):
        import re
        if not re.fullmatch(r'[A-Z0-9][A-Z0-9_-]{0,29}',ident): errors.append((idfield,'Use uppercase letters, digits, hyphens or underscores.'))
        field='Qualification_Name' if dataset=='qualifications' else 'Module_Name'
        if not row.get(field) or len(row[field])>160: errors.append((field,'Required name, maximum 160 characters.'))
        if dataset=='qualifications' and Qualification.objects.filter(name=row.get(field,'')).exclude(code=ident).exists(): errors.append((field,'Name belongs to another qualification code.'))
        if dataset=='modules':
            if len(row.get('Department',''))>120: errors.append(('Department','Maximum 120 characters.'))
        return errors
    original=(_validate_faculty if dataset=='faculty' else _validate_learner)(row,0)
    errors.extend((e['field'],e['message']) for e in original)
    for field,limit in [('Full_Name',160),('Email',254),('Department',120),('Time_Zone',80)]:
        if len(row.get(field,''))>limit: errors.append((field,f'Maximum {limit} characters.'))
    modes=split(row.get('Consultation_Modes' if dataset=='faculty' else 'Preferred_Consultation_Mode',''))
    if not modes or set(modes)-{'Online','Face-to-face'}: errors.append(('Consultation_Mode','Use Online or Face-to-face.'))
    if dataset=='faculty':
        if set(split(row.get('Working_Days','')))-{'Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'}: errors.append(('Working_Days','Invalid weekday.'))
        refs(Qualification,split(row.get('Qualifications','')),'Qualifications',errors)
        refs(AcademicModule,split(row.get('Modules_Taught','')),'Modules_Taught',errors)
        qcodes=split(row.get('Qualifications','')); mcodes=split(row.get('Modules_Taught',''))
        allowed=set(QualificationModule.objects.filter(qualification__code__in=qcodes,qualification__is_active=True,module__is_active=True,is_active=True).values_list('module__code',flat=True))
        if row.get('Status')=='Active' and set(mcodes)-allowed: errors.append(('Modules_Taught','Teaching modules must belong to selected active qualifications.'))
        try:
            mappings=json.loads(row['Expertise_Mappings'])
            if not isinstance(mappings,list): raise ValueError('Expected array')
            for m in mappings:
                if not isinstance(m,dict): raise ValueError('Expected object')
                allowed={'module_code','topics','expertise_level','qualifications','verified_by','last_reviewed','eligible_for_consultation'}
                if set(m)-allowed: raise ValueError('Unexpected expertise mapping attributes; use v6 template.')
                for k in ('topics','qualifications'):
                    if not isinstance(m.get(k,[]),list) or any(not isinstance(x,str) or not x.strip() for x in m.get(k,[])): raise ValueError(f'{k} must contain non-empty strings')
                if not isinstance(m.get('module_code'),str) or not isinstance(m.get('verified_by',''),str) or len(m.get('verified_by',''))>160: raise ValueError('Invalid module code or verifier')
                if m.get('eligible_for_consultation') and (not m.get('qualifications') or not m.get('verified_by') or not m.get('last_reviewed')): raise ValueError('Eligible expertise requires verifier and review date')
                if m.get('eligible_for_consultation') and (not AcademicModule.objects.filter(code=m['module_code'],is_active=True).exists() or AcademicTopic.objects.filter(code__in=m.get('topics',[]),is_active=False).exists()): errors.append(('Expertise_Mappings','Approved expertise requires active module and topics.'))
                refs(AcademicModule,[m['module_code']],'Expertise_Mappings',errors)
                refs(AcademicTopic,m.get('topics',[]),'Expertise_Mappings',errors)
                if AcademicTopic.objects.filter(code__in=m.get('topics',[])).exclude(module__code=m['module_code']).exists(): errors.append(('Expertise_Mappings','Topic belongs to a different module.'))
                refs(Qualification,m.get('qualifications',[]),'Expertise_Mappings',errors)
                if set(m.get('qualifications',[]))-set(split(row.get('Qualifications',''))): errors.append(('Expertise_Mappings','Expertise qualifications must be listed in faculty qualifications.'))
                for pc in m.get('qualifications',[]):
                    if not QualificationModule.objects.filter(qualification__code=pc,module__code=m['module_code'],is_active=True,qualification__is_active=True,module__is_active=True).exists() and m.get('eligible_for_consultation'): errors.append(('Expertise_Mappings',f'Module {m["module_code"]} not in active curriculum {pc}.'))
        except (ValueError,TypeError,KeyError,AttributeError) as e: errors.append(('Expertise_Mappings',str(e)))
    else:
        refs(Qualification,[row.get('Qualification','')],'Qualification',errors)
        codes=split(row.get('Current_Module_Codes',''))
        refs(AcademicModule,codes,'Current_Module_Codes',errors)
        if row.get('Current_Module_Code') not in codes: errors.append(('Current_Module_Code','Primary module must be among current modules.'))
        for code in codes:
            if not QualificationModule.objects.filter(qualification__code=row.get('Qualification',''),module__code=code,is_active=True,qualification__is_active=True,module__is_active=True).exists(): errors.append(('Current_Module_Codes',f'{code} is not in the active qualification curriculum.'))
    return errors

def validate_records(dataset,records):
    errors=[]; seen=set(); emails=set(); names=set(); idfield=MODELS[dataset][2]
    for i,row in enumerate(records,2):
        issues=validate_row(dataset,row)
        key=(row.get('Qualification_Code','').casefold(),row.get('Module_Code','').casefold()) if dataset=='curriculum' else row.get(idfield,'').casefold()
        if key in seen: issues.append((idfield,'Duplicate identifier in file.'))
        seen.add(key)
        if 'Email' in row:
            e=row['Email'].casefold()
            if e in emails: issues.append(('Email','Duplicate email in file.'))
            emails.add(e)
        if dataset in ('qualifications','topics'):
            n=row['Qualification_Name'].casefold() if dataset=='qualifications' else (row['Module_Code'].casefold(),row['Topic_Name'].casefold())
            if n in names: issues.append(('Qualification_Name','Duplicate name in catalogue scope.'))
            names.add(n)
        errors.extend(dict(row=i,field=f,message=m) for f,m in issues)
    if dataset=='curriculum' and not errors:
        # Check the final effective curriculum, allowing sequence swaps in one upload.
        changes={(r['Qualification_Code'],r['Module_Code']):(int(r['Sequence']),r['Status']=='Active') for r in records}
        existing={(x.qualification.code,x.module.code):(x.sequence,x.is_active) for x in QualificationModule.objects.select_related('qualification','module') if x.qualification.code in {r['Qualification_Code'] for r in records}}
        existing.update(changes)
        slots=set()
        for (pc,mc),(seq,active) in existing.items():
            if active and (pc,seq) in slots: errors.append(dict(row=2,field='Sequence',message=f'Duplicate active sequence {seq} in {pc}. Include all affected rows in the upload.'))
            if active: slots.add((pc,seq))
        for i,r in enumerate(records,2):
            if r['Status']=='Inactive' and LearnerProfile.objects.filter(qualification__code=r['Qualification_Code'],current_modules__code=r['Module_Code'],status='Active').exists(): errors.append(dict(row=i,field='Status',message='Active learners currently use this module. Reassign them before archiving.'))
        for i,r in enumerate(records,2):
            if r['Status']=='Inactive':
                pc,mc=r['Qualification_Code'],r['Module_Code']
                if FacultyExpertise.objects.filter(module__code=mc,qualifications__code=pc,eligible_for_consultation=True).exists(): errors.append(dict(row=i,field='Status',message='Revoke or reassign approved expertise first.'))
                for f in FacultyProfile.objects.filter(qualifications__code=pc,modules_taught__code=mc,status='Active'):
                    if not QualificationModule.objects.filter(qualification__in=f.qualifications.all(),module__code=mc,is_active=True).exclude(qualification__code=pc).exists(): errors.append(dict(row=i,field='Status',message=f'Reassign teaching module for {f.faculty_id} first.'))
    return errors

def parse_and_validate_csv(uploaded_file,dataset):
    if uploaded_file.size>MAX_UPLOAD_BYTES: raise ValueError('Maximum CSV size is 5 MB.')
    try: text=uploaded_file.read().decode('utf-8-sig')
    except UnicodeDecodeError: raise ValueError('CSV must be UTF-8.')
    try:
        reader=csv.DictReader(io.StringIO(text),strict=True)
        if len(reader.fieldnames or [])!=len(HEADERS[dataset]) or set(reader.fieldnames or [])!=set(HEADERS[dataset]): raise ValueError('Expected headers: '+', '.join(HEADERS[dataset]))
        records=[]
        for row in reader:
            if None in row or any(v is None for v in row.values()): raise ValueError(f'Wrong column count near CSV line {reader.line_num}.')
            records.append({k:v.strip() for k,v in row.items()})
            if len(records)>MAX_ROWS: raise ValueError('Maximum 5000 rows.')
    except csv.Error as exc: raise ValueError(f'Invalid CSV: {exc}')
    if not records: raise ValueError('CSV contains no data rows.')
    return records,validate_records(dataset,records)

def plan(dataset,records):
    model,key,idfield=MODELS[dataset]; counts=[0,0,0]; changes=[]
    for row in records:
        obj=lookup(dataset,row)
        old=export_row(dataset,obj) if obj else None
        unresolved=obj.additional_modules_taught if dataset=='faculty' and obj else []
        same=old==canonical(row) and not unresolved
        kind=0 if obj is None else (2 if same else 1)
        counts[kind]+=1
        changes.append([row[idfield],row.get('Module_Code') if dataset=='curriculum' else None,old,unresolved,kind])
    # Include referenced catalogue state so a changed reference requires a new preview.
    catalogue=list(Qualification.objects.order_by('code').values('code','name','is_active')) if dataset!='qualifications' else []
    if dataset in ('faculty','learners','topics','curriculum'): catalogue += [export_row('modules',m) for m in AcademicModule.objects.order_by('code')]
    if dataset in ('curriculum','faculty','learners'): catalogue += [export_row('curriculum',c) for c in QualificationModule.objects.select_related('qualification','module').order_by('qualification__code','module__code')]
    if dataset=='faculty': catalogue += [export_row('topics',t) for t in AcademicTopic.objects.order_by('code')]
    digest=hashlib.sha256(json.dumps([changes,catalogue],sort_keys=True,default=str).encode()).hexdigest()
    return tuple(counts),digest

def save_row(dataset,row):
    def progs(codes): return Qualification.objects.filter(code__in=codes)
    def mod(code): return AcademicModule.objects.get(code=code)
    if dataset=='qualifications': Qualification.objects.update_or_create(code=row['Qualification_Code'],defaults={'name':row['Qualification_Name'],'is_active':row['Status']=='Active'}); return
    if dataset=='modules':
        obj,_=AcademicModule.objects.update_or_create(code=row['Module_Code'],defaults={'name':row['Module_Name'],'department':row['Department'],'is_active':row['Status']=='Active'});return
    if dataset=='curriculum':
        QualificationModule.objects.update_or_create(qualification=Qualification.objects.get(code=row['Qualification_Code']),module=mod(row['Module_Code']),defaults=dict(sequence=int(row['Sequence']),is_active=row['Status']=='Active'));return
    if dataset=='topics':
        AcademicTopic.objects.update_or_create(code=row['Topic_Code'],defaults=dict(module=mod(row['Module_Code']),name=row['Topic_Name'],is_active=row['Status']=='Active'));return
    if dataset=='faculty':
        obj,_=FacultyProfile.objects.update_or_create(faculty_id=row['Faculty_ID'],defaults=dict(full_name=row['Full_Name'],email=row['Email'],department=row['Department'],teaching_experience_years=int(row['Teaching_Experience_Years']),consultation_modes=split(row['Consultation_Modes']),languages=split(row['Languages']),time_zone=row['Time_Zone'],working_days=split(row['Working_Days']),working_hours_start=_parse_time(row['Working_Hours_Start'],'start') if row['Working_Hours_Start'] else None,working_hours_end=_parse_time(row['Working_Hours_End'],'end') if row['Working_Hours_End'] else None,status=row['Status'],additional_modules_taught=[]))
        obj.qualifications.set(progs(split(row['Qualifications'])));obj.modules_taught.set(AcademicModule.objects.filter(code__in=split(row['Modules_Taught'])))
        ids=[]
        for m in json.loads(row['Expertise_Mappings']):
            expertise,_=FacultyExpertise.objects.update_or_create(faculty=obj,module=mod(m['module_code']),defaults=dict(expertise_level=m['expertise_level'],verified_by=m.get('verified_by',''),last_reviewed=date.fromisoformat(m['last_reviewed']) if m.get('last_reviewed') else None,eligible_for_consultation=m['eligible_for_consultation']))
            expertise.catalogue_topics.set(AcademicTopic.objects.filter(code__in=m.get('topics',[]),module=expertise.module))
            expertise.qualifications.set(progs(m.get('qualifications',[])));ids.append(expertise.pk)
        for e in obj.expertise_mappings.exclude(pk__in=ids):
            e.qualifications.remove(*list(e.qualifications.exclude(code__in=split(row['Qualifications']))));e.eligible_for_consultation=False;e.save(update_fields=['eligible_for_consultation'])
        return
    learner,_=LearnerProfile.objects.update_or_create(learner_id=row['Learner_ID'],defaults=dict(full_name=row['Full_Name'],email=row['Email'],qualification=Qualification.objects.get(code=row['Qualification']),current_module=mod(row['Current_Module_Code']),time_zone=row['Time_Zone'],preferred_consultation_modes=split(row['Preferred_Consultation_Mode']),preferred_languages=split(row['Preferred_Language']),status=row['Status']))
    learner.current_modules.set(AcademicModule.objects.filter(code__in=split(row['Current_Module_Codes'])))

def expire_stale_batches():
    ImportBatch.objects.filter(state__in=['previewed','invalid'],expires_at__lte=timezone.now()).update(state='expired',records=[])

@transaction.atomic
def confirm_import_batch(batch,user):
    locked=ImportBatch.objects.select_for_update().get(pk=batch.pk,created_by=user)
    if locked.state!='previewed' or locked.expires_at<=timezone.now() or locked.errors: raise ValueError('Preview is invalid, expired or already processed. Upload again.')
    # Serialize existing master-data writes across import confirmations.
    for model in (Qualification,AcademicModule,QualificationModule,AcademicTopic,FacultyProfile,LearnerProfile): list(model.objects.select_for_update().order_by('pk').values_list('pk',flat=True))
    errors=validate_records(locked.dataset,locked.records)
    if errors: raise ValueError('Catalogue or data changed: '+errors[0]['message'])
    counts,digest=plan(locked.dataset,locked.records)
    if digest!=locked.preview_digest: raise ValueError('Data changed since preview. Upload again.')
    model,key,idfield=MODELS[locked.dataset]
    for row in locked.records:
        obj=lookup(locked.dataset,row)
        if obj and export_row(locked.dataset,obj)==canonical(row) and not (locked.dataset=='faculty' and obj.additional_modules_taught): continue
        save_row(locked.dataset,row)
    locked.created_count,locked.updated_count,locked.unchanged_count=counts
    locked.state='confirmed';locked.confirmed_at=timezone.now();locked.records=[];locked.save()
    return counts
