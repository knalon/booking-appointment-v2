import React from 'react';
import {createRoot} from 'react-dom/client';
import AdminPage from './pages/AdminPage';
import LearnerPage from './pages/LearnerPage';
import FacultyPage from './pages/FacultyPage';
import './style.css';
createRoot(document.getElementById('root')).render(window.location.pathname.startsWith("/faculty")?<FacultyPage/>:window.location.pathname.startsWith("/learner")?<LearnerPage/>:<AdminPage/>);
