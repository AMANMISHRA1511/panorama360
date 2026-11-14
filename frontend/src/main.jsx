import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { UIProvider } from './context/UIContext';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import Home from './pages/Home';
import Auth from './pages/Auth';
import Upload from './pages/Upload';
import Capture from './pages/Capture';
import Processing from './pages/Processing';
import Gallery from './pages/Gallery';
import View from './pages/View';
import Share from './pages/Share';
import './style.css';
function App() {return <BrowserRouter><UIProvider><AuthProvider><Routes>
  <Route element={<Layout/>}><Route index element={<Home/>}/><Route path="/login" element={<Auth/>}/><Route path="/s/:token" element={<Share/>}/>
    <Route element={<ProtectedRoute/>}><Route path="/upload" element={<Upload/>}/><Route path="/capture" element={<Capture/>}/><Route path="/processing/:id" element={<Processing/>}/><Route path="/gallery" element={<Gallery/>}/><Route path="/view/:id" element={<View/>}/></Route>
    <Route path="*" element={<div className="page site-container center-state"><h1>Lost in the panorama?</h1><p>That page isn't here.</p><a href="/">Return home</a></div>}/>
  </Route>
</Routes></AuthProvider></UIProvider></BrowserRouter>}
createRoot(document.getElementById('root')).render(<React.StrictMode><App/></React.StrictMode>);
