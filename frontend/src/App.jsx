import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Sidebar from './components/layout/Sidebar';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Employees from './pages/Employees';
import Payroll from './pages/Payroll';
import Attendance from './pages/Attendance';
import Approvals from './pages/Approvals';
import ActivityLogs from './pages/ActivityLogs';
import Settings from './pages/Settings';
import ProfileModal from './components/layout/ProfileModal';
import 'bootstrap/dist/css/bootstrap.min.css';

/**
 * Protected Route Wrapper
 */
const ProtectedLayout = ({ children }) => {
  const { isAuthenticated } = useAuth();
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="d-flex" style={{ backgroundColor: '#F9F9F9', minHeight: '100vh' }}>
      <Sidebar />
      <div className="flex-grow-1" style={{ marginLeft: '260px', minWidth: 0 }}>
        {children}
      </div>
      <ProfileModal />
    </div>
  );
};

/**
 * Main Application Component Logic
 */
const AppRoutes = () => {
  const { isAuthenticated } = useAuth();

  return (
    <Routes>
      {/* Public Route */}
      <Route 
        path="/login" 
        element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <Login />} 
      />

      {/* Protected Routes */}
      <Route path="/" element={<ProtectedLayout><Navigate to="/dashboard" replace /></ProtectedLayout>} />
      <Route path="/dashboard" element={<ProtectedLayout><Dashboard /></ProtectedLayout>} />
      <Route path="/employee" element={<ProtectedLayout><Employees /></ProtectedLayout>} />
      <Route path="/payroll" element={<ProtectedLayout><Payroll /></ProtectedLayout>} />
      <Route path="/attendance" element={<ProtectedLayout><Attendance /></ProtectedLayout>} />
      <Route path="/approvals" element={<ProtectedLayout><Approvals /></ProtectedLayout>} />
      <Route path="/activity-logs" element={<ProtectedLayout><ActivityLogs /></ProtectedLayout>} />
      <Route path="/settings" element={<ProtectedLayout><Settings /></ProtectedLayout>} />

      {/* Fallback */}
      <Route path="*" element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />} />
    </Routes>
  );
};

export default function App() {
  return (
    <AuthProvider>
      <Router>
        <AppRoutes />
      </Router>
    </AuthProvider>
  );
}
