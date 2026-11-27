import React,{useEffect,useState} from 'react';
import {request} from '../services/api';
const path='/api/coordinator/learner-cases/';
export default function ReviewMessages({focusId}){
 const [rows,R]=useState([]),[error,E]=useState('');
 useEffect(()=>{let live=true;const load=()=>request(path).then(x=>{if(live){R(x);E('')}}).catch(e=>{if(live)E(e.message)});load();const timer=setInterval(load,15000);return()=>{live=false;clearInterval(timer)}},[]);
 useEffect(()=>{if(focusId)document.getElementById('review-'+focusId)?.scrollIntoView({block:'nearest'})},[focusId,rows.length]);
 return <section className="panel"><h2>Consultation review messages</h2><p className="muted">Your coordinator or Programme Manager can assist if a consultation cannot be arranged automatically.</p>{error&&<p role="alert" className="warning">{error}</p>}{!rows.length&&<p>No review cases yet.</p>}{rows.map(c=><article id={'review-'+c.id} key={c.id} className={'appointment-card '+(c.id===focusId?'appointment-focused':'')}><div className="heading"><strong>{c.difficulty||c.reason}</strong><span>{c.status.replaceAll('_',' ')}</span></div><p>{c.qualification} · {c.module||'General assistance'} · {c.reason}</p>{!c.events.length&&<p>Awaiting coordinator response.</p>}{c.events.map((e,i)=><div className="review-event" key={i}><small>{new Date(e.created_at).toLocaleString()}</small><p>{e.detail}</p></div>)}</article>)}</section>
}
