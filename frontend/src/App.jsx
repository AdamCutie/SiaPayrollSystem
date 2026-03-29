import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './components/layout/Sidebar';
import Dashboard from './pages/Dashboard';
import Employees from './pages/Employees';
import Payroll from './pages/Payroll';
import Attendance from './pages/Attendance';
import Approvals from './pages/Approvals';
import Settings from './pages/Settings';
import 'bootstrap/dist/css/bootstrap.min.css';

/**
 * Main Application Component
 */
export default function App() {
  return (
    <Router>
      <div className="d-flex" style={{ backgroundColor: '#F9F9F9', minHeight: '100vh' }}>
        <Sidebar />

        <div className="flex-grow-1" style={{ marginLeft: '260px', minWidth: 0 }}>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/employee" element={<Employees />} />
            <Route path="/payroll" element={<Payroll />} />
            <Route path="/attendance" element={<Attendance />} />
            <Route path="/approvals" element={<Approvals />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </div>
      </div>
    </Router>
  );
}
