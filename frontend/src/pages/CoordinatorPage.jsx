import React,{useEffect,useState} from 'react';
import {api,request} from '../services/api';
import NotificationBell from '../components/NotificationBell';
import CoordinatorCases from '../components/CoordinatorCases';
import Appointments from '../components/Appointments';
import '../components/coordinator.css';
const base='/api/coordinator/';
export default function CoordinatorPage(){
 const [profile,P]=useState(undefined),[username,U]=useState(''),[password,W]=useState(''),[error,E]=useState(''),[busy,B]=useState(false),[tab,T]=useState('cases'),[focus,F]=useState(null);
 useEffect(()=>{api('auth/csrf/').then(()=>request(base+'session/')).then(P).catch(()=>P(null))},[]);
 async function login(e){e.preventDefault();B(true);E('');try{await api('auth/csrf/');await request(base+'login/',{method:'POST',body:JSON.stringify({username,password})});P(await request(base+'session/'));W('')}catch(e){E(e.message)}finally{B(false)}}
 if(profile===undefined)return <main className="login">Checking session…</main>;
 if(!profile)return <main className="login"><p className="eyebrow">INSTITUTIONAL SERVICES</p><h1>Coordinator workspace</h1><p>Coordinator and Programme Manager sign in</p><form className="editor" onSubmit={login}><label>Username<input required autoComplete="username" value={username} onChange={e=>U(e.target.value)}/></label><label>Password<input required type="password" autoComplete="current-password" value={password} onChange={e=>W(e.target.value)}/></label>{error&&<p className="warning" role="alert">{error}</p>}<button disabled={busy}>Sign in</button></form><p><a href="/">Management</a> · <a href="/faculty">Faculty</a> · <a href="/learner">Learner</a></p></main>;
 return <main className="coordinator-workspace"><header className="heading"><div><p className="eyebrow">{profile.role==='programme_manager'?'PROGRAMME MANAGER':'COORDINATOR'} WORKSPACE</p><h1>{profile.full_name}</h1><p>@{profile.username} · {profile.qualifications.join(', ')||'No qualification assigned'}</p></div><div className="appointment-header-actions"><NotificationBell onOpenReview={id=>{F(id);T('cases')}} onOpenAppointments={id=>{F(id);T('appointments')}}/><button className="secondary" onClick={async()=>{try{await api('auth/logout/',{method:'POST',body:'{}'});P(null);E('')}catch(e){E(e.message)}}}>Sign out</button></div></header>{error&&<p className="warning" role="alert">{error}</p>}<div className="actions"><button className={tab==='cases'?'':'secondary'} onClick={()=>{F(null);T('cases')}}>Review queue</button><button className={tab==='appointments'?'':'secondary'} onClick={()=>{F(null);T('appointments')}}>Appointments</button></div>{tab==='cases'?<CoordinatorCases profile={profile} focusId={focus}/>:<Appointments focusId={focus} endpoint={base+'appointments/'} readOnly/>}</main>
}
