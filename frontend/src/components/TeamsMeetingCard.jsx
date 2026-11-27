import React from 'react';
export default function TeamsMeetingCard({appointment:a}){
 const t=a.teams;if(!t)return null;
 const labels={queued:'Meeting creation queued',sending:'Creating Teams meeting',ready:'Teams meeting ready',blocked:'Meeting configuration needs attention',review_required:'Organiser calendar requires manual review',withdrawn:'Meeting creation withdrawn'};
 return <div className="panel" style={{padding:12,margin:'12px 0'}}><strong>Microsoft Teams</strong><p role="status">{labels[t.status]||t.status}{t.test_mode?' · Test mode':''}</p>{t.detail&&<p className="muted">{t.detail}</p>}{t.join_url&&<a href={t.join_url} target="_blank" rel="noopener noreferrer">Join Microsoft Teams meeting</a>}{t.test_mode&&<p className="muted">Test invitations go only to configured approved test recipients. The appointment participants can use this link, subject to Teams admission rules.</p>}</div>
}
