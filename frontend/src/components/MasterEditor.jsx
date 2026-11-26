import React,{useState} from 'react';
import {api} from '../services/api';
const list=v=>(v||'').split(';').map(x=>x.trim()).filter(Boolean);
export default function MasterEditor({dataset,headers,record,catalogue,onClose,onSaved}){
 const [row,setRow]=useState(record||Object.fromEntries(headers.map(k=>[k,k==='Status'?'Active':k==='Sequence'?'1':k==='Time_Zone'?'Asia/Singapore':k==='Preferred_Language'?'English':k==='Preferred_Consultation_Mode'?'Online':'']))),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const set=(k,v)=>setRow(r=>({...r,[k]:v}));
 const immutable=k=>!!record&&(k===headers[0]||(['topics','curriculum'].includes(dataset)&&k==='Module_Code'));
 const qcode=row.Qualification||row.Qualification_Code;
 const modules=catalogue.modules.filter(m=>m.is_active&&(!qcode||dataset==='curriculum'||catalogue.curriculum.some(c=>c.is_active&&c.qualification__code===qcode&&c.module__code===m.code)));
 function changeQualification(k,v){setRow(r=>({...r,[k]:v,...(dataset==='learners'?{Current_Module_Code:'',Current_Module_Codes:''}:{})}));}
 async function submit(e){e.preventDefault();setBusy(true);setError('');try{await api(`master/${dataset}/`,{method:'POST',body:JSON.stringify({row,original:record||null})});await onSaved();}catch(e){setError(e.message)}finally{setBusy(false)}}
 return <form className="editor" onSubmit={submit}><div className="heading"><h2>{record?'Edit':'Add'} {dataset==='curriculum'?'curriculum assignment':dataset.slice(0,-1)}</h2><button type="button" className="secondary" onClick={onClose}>Close</button></div>{headers.map(k=>{let opts=null;
 if(k==='Status')opts=['Active','Inactive'].map(code=>({code,name:code}));
 if(k==='Qualification'||(dataset==='curriculum'&&k==='Qualification_Code'))opts=catalogue.qualifications.filter(q=>q.is_active||q.code===row[k]);
 if(k==='Module_Code'&&['topics','curriculum'].includes(dataset))opts=catalogue.modules.filter(m=>m.is_active||m.code===row[k]);
 if(k==='Current_Module_Code')opts=modules.filter(m=>list(row.Current_Module_Codes).includes(m.code));
 if(k==='Current_Module_Codes')return <fieldset key={k}><legend>Current modules</legend>{modules.map(m=><label className="check" key={m.code}><input type="checkbox" checked={list(row[k]).includes(m.code)} onChange={e=>{const values=e.target.checked?[...list(row[k]),m.code]:list(row[k]).filter(x=>x!==m.code);setRow(r=>({...r,[k]:values.join('; '),Current_Module_Code:values.includes(r.Current_Module_Code)?r.Current_Module_Code:values[0]||''}))}}/>{m.code} — {m.name}</label>)}</fieldset>;
 if(opts)return <label key={k}>{k.replaceAll('_',' ')}<select required disabled={immutable(k)} value={row[k]} onChange={e=>changeQualification(k,e.target.value)}><option value="">Select…</option>{opts.map(o=><option key={o.code} value={o.code}>{o.name===o.code?o.code:o.code+' — '+o.name}</option>)}</select></label>;
 return <label key={k}>{k.replaceAll('_',' ')}<input required={k!=='Department'} disabled={immutable(k)} type={k==='Sequence'?'number':k==='Email'?'email':'text'} min={k==='Sequence'?1:undefined} value={row[k]||''} onChange={e=>set(k,e.target.value)}/></label>})}{error&&<p className="warning">{error}</p>}<div className="editor-actions"><button type="button" className="secondary" onClick={onClose}>Cancel</button><button disabled={busy}>{busy?'Saving…':'Save'}</button></div></form>
}
