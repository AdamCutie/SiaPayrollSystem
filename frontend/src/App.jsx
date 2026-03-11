import React from 'react';
import Sidebar from './components/layout/Sidebar';
import Dashboard from './pages/Dashboard';
import 'bootstrap/dist/css/bootstrap.min.css';

/**
 * Main Application Component
 * Orchestrates the overall layout: Sidebar + Main Content.
 */
export default function App() {
  return (
    <div className="d-flex" style={{ backgroundColor: '#F9F9F9', minHeight: '100vh' }}>
      {/* 1. Sidebar - Fixed Navigation hub */}
      <Sidebar />

      {/* 2. Main Content Area - Dynamic content based on active route */}
      <div className="flex-grow-1" style={{ marginLeft: '260px', minWidth: 0 }}>
        <Dashboard />
      </div>
    </div>
  );
}
