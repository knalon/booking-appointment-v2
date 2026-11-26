import React from 'react';
import './faculty-cards.css';
export default function FacultyCard({candidate:c,scheduled=false}){
 const initials=c.name.trim().split(/\s+/).slice(0,2).map(x=>x[0]).join('').toUpperCase();
 const reasons=['Verified expertise in your subject',c.match_type==='exact_topic'?'Verified expertise in the relevant catalogue topic':'Recommended based on relevant module expertise',c.currently_teaching?'Currently teaches your module':null,c.preferred_faculty_match?'Matches your requested faculty':null].filter(Boolean);
 return <article className="faculty-card"><div className="faculty-card-top"><div className="faculty-avatar" aria-hidden="true">{initials}</div><h3>{c.name}</h3><p className="muted">{c.department}</p><span className="faculty-band">{scheduled?(c.final_band?c.final_band+' overall match':'Availability not matched'):c.academic_band+' academic match'}</span></div><dl><dt>Expertise</dt><dd>{c.expertise_level}</dd><dt>Teaching</dt><dd>{c.teaching_years} years</dd><dt>Languages</dt><dd>{c.languages.join(', ')}</dd><dt>Modes</dt><dd>{c.modes.join(', ')}</dd></dl><div className="faculty-reasons"><strong>Why recommended?</strong><ul>{reasons.map(r=><li key={r}>{r}</li>)}</ul></div><footer>{scheduled?'See compatible slots below.':'Check availability below.'}</footer></article>
}
