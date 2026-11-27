import React,{useEffect,useState} from 'react';
import NotificationBell from '../components/NotificationBell';
import Appointments from '../components/Appointments';
import ReviewMessages from '../components/ReviewMessages';
import {api,request} from '../services/api';
import NLPPage from './NLPPage';
export default function LearnerPage(){
 const [tab,setTab]=useState('chat'),[focus,setFocus]=useState(null);
 const [ready,setReady]=useState(false),[checking,setChecking]=useState(true),[username,setUsername]=useState(''),[password,setPassword]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{api('auth/csrf/').then(()=>request('/api/nlp/status/')).then(c=>setReady(!c.staff_preview&&c.learners.length>0)).catch(()=>{}).finally(()=>setChecking(false))},[]);
 if(checking)return <main className="login">Checking session…</main>;
 if(!ready)return <main className="login"><h1>Learner consultation</h1><p>Use your assigned demo learner username and password. Staff accounts cannot access consultation chat.</p><form className="editor" onSubmit={async e=>{e.preventDefault();setError('');setBusy(true);try{await api('auth/csrf/');await request('/api/nlp/login/',{method:'POST',body:JSON.stringify({username,password})});setReady(true);setPassword('')}catch(e){setError(e.message)}finally{setBusy(false)}}}><label>Username<input required autoComplete="username" value={username} onChange={e=>setUsername(e.target.value)}/></label><label>Password<input required type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)}/></label>{error&&<p role="alert">{error}</p>}<button disabled={busy}>Sign in</button></form><a href="/">Management sign in</a></main>;
 return <main style={{maxWidth:1200,margin:'auto',padding:24}}><header className="heading"><h1>Learner consultation</h1><div className="appointment-header-actions"><NotificationBell onOpenAppointments={id=>{setFocus(id);setTab('appointments')}} onOpenReview={id=>{setFocus(id);setTab('reviews')}}/><button className="secondary" onClick={async()=>{try{await api('auth/logout/',{method:'POST',body:'{}'});setReady(false)}catch(e){setError(e.message)}}}>Sign out</button></div></header>{error&&<p role="alert">{error}</p>}<div className="actions"><button className={tab==='chat'?'':'secondary'} onClick={()=>setTab('chat')}>Consultation</button><button className={tab==='appointments'?'':'secondary'} onClick={()=>setTab('appointments')}>My appointments</button><button className={tab==='reviews'?'':'secondary'} onClick={()=>{setFocus(null);setTab('reviews')}}>Review messages</button></div><div hidden={tab!=='chat'}><NLPPage/></div>{tab==='appointments'&&<Appointments focusId={focus}/>} {tab==='reviews'&&<ReviewMessages focusId={focus}/>}</main>
}
