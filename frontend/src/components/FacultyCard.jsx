import React from 'react';
import './faculty-cards.css';
export default function FacultyCard({candidate:c,scheduled=false}){
 const initials=c.name.trim().split(/\s+/).slice(0,2).map(x=>x[0]).join('').toUpperCase();
 return <article className="faculty-card"><div className="faculty-card-top"><div className="faculty-avatar" aria-hidden="true">{initials}</div><h3>{c.name}</h3><p className="muted">{c.department}</p><span className="faculty-band">{c.academic_band} academic match</span></div><dl><dt>Expertise</dt><dd>{c.expertise_level}</dd><dt>Teaching</dt><dd>{c.teaching_years} years</dd><dt>Languages</dt><dd>{c.languages.join(', ')}</dd><dt>Modes</dt><dd>{c.modes.join(', ')}</dd></dl>{!scheduled&&<footer>Availability will be checked in the next stage.</footer>}</article>
}
