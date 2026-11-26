import React,{useEffect,useState} from 'react';
import NotificationBell from '../components/NotificationBell';
import Appointments from '../components/Appointments';
import {api,request} from '../services/api';
import FacultyCalendar from '../components/FacultyCalendar';
import './faculty-workspace.css';
const base='/api/scheduling/faculty/';
export default function FacultyPage(){
 const [tab,setTab]=useState('calendar'),[focus,setFocus]=useState(null);
 const [profile,setProfile]=useState(undefined),[username,U]=useState(''),[password,P]=useState(''),[error,E]=useState(''),[busy,B]=useState(false);
 useEffect(()=>{api('auth/csrf/').then(()=>request(base+'session/')).then(setProfile).catch(()=>setProfile(null))},[]);
 async function login(e){e.preventDefault();B(true);E('');try{await api('auth/csrf/');await request(base+'login/',{method:'POST',body:JSON.stringify({username,password})});setProfile(await request(base+'session/'));P('')}catch(e){E(e.message)}finally{B(false)}}
 if(profile===undefined)return <main className="login">Checking session…</main>;
 if(!profile)return <main className="login"><p className="eyebrow">INSTITUTIONAL SERVICES</p><h1>Faculty workspace</h1><form className="editor" onSubmit={login}><label>Username<input required autoComplete="username" value={username} onChange={e=>U(e.target.value)}/></label><label>Password<input required type="password" autoComplete="current-password" value={password} onChange={e=>P(e.target.value)}/></label>{error&&<p role="alert">{error}</p>}<button disabled={busy}>Sign in</button></form><p><a href="/">Management</a> · <a href="/learner">Learner</a></p></main>;
 return <main className="faculty-workspace"><header className="faculty-header"><div><p className="eyebrow">FACULTY WORKSPACE</p><h1>{profile.full_name}</h1><p>{profile.faculty_id} · {profile.department} · @{profile.username}</p></div><div className="appointment-header-actions"><NotificationBell onOpenAppointments={id=>{setFocus(id);setTab('appointments')}}/><button className="secondary" onClick={async()=>{try{await api('auth/logout/',{method:'POST',body:'{}'});setProfile(null);E('')}catch(e){E(e.message)}}}>Sign out</button></div></header>{error&&<p role="alert">{error}</p>}<div className="actions"><button className={tab==='calendar'?'':'secondary'} onClick={()=>setTab('calendar')}>My calendar</button><button className={tab==='appointments'?'':'secondary'} onClick={()=>setTab('appointments')}>My appointments</button></div>{tab==='calendar'?<FacultyCalendar profile={profile}/>:<Appointments focusId={focus}/>}</main>
}
