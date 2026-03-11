import React from 'react';
import Sidebar from './components/layout/Sidebar';
import Dashboard from './pages/Dashboard';
import 'bootstrap/dist/css/bootstrap.min.css';

/**
 * Main Application Component
 * Assembler for the Dashboard Layout mirroring Figma designs.
 */
export default function App() {
  return (
    <div className="d-flex" style={{ backgroundColor: '#F9F9F9', minHeight: '100vh' }}>
      {/* Sidebar - Persistent Navigation */}
      <Sidebar />

      {/* Main Container - Adjusted for Sidebar Width */}
      <div className="flex-grow-1" style={{ marginLeft: '260px', padding: '0' }}>
        <Dashboard />
      </div>
    </div>
  );
}
