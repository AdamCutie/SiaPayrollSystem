import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Users, CreditCard, Calendar, FileText, Settings, CheckCircle } from 'lucide-react';

const Sidebar = () => {
  return (
    <div className="sidebar-sia">
      <div className="logo-container p-4 text-center">
        <h4 className="fw-bold m-0" style={{ color: '#D29191' }}>Sia Essentials</h4>
      </div>
      
      <div className="nav flex-column gap-1">
        <div className="px-4 mb-2 mt-3">
          <small className="text-uppercase fw-bold text-muted" style={{ fontSize: '11px', letterSpacing: '1px' }}>Main</small>
        </div>
        <NavLink 
          to="/dashboard" 
          className={({ isActive }) => `nav-link-sia ${isActive ? 'active' : ''}`}
        >
          <LayoutDashboard size={20}/> Dashboard
        </NavLink>
        
        <div className="px-4 mb-2 mt-4">
          <small className="text-uppercase fw-bold text-muted" style={{ fontSize: '11px', letterSpacing: '1px' }}>Management</small>
        </div>
        <NavLink 
          to="/employee" 
          className={({ isActive }) => `nav-link-sia ${isActive ? 'active' : ''}`}
        >
          <Users size={20}/> Employee
        </NavLink>
        <NavLink 
          to="/payroll" 
          className={({ isActive }) => `nav-link-sia ${isActive ? 'active' : ''}`}
        >
          <CreditCard size={20}/> Payroll
        </NavLink>
        <NavLink 
          to="/attendance" 
          className={({ isActive }) => `nav-link-sia ${isActive ? 'active' : ''}`}
        >
          <Calendar size={20}/> Attendance
        </NavLink>
        <NavLink 
          to="/approvals" 
          className={({ isActive }) => `nav-link-sia ${isActive ? 'active' : ''}`}
        >
          <CheckCircle size={20}/> Approvals
        </NavLink>
        <NavLink 
          to="/settings" 
          className={({ isActive }) => `nav-link-sia ${isActive ? 'active' : ''}`}
        >
          <Settings size={20}/> Settings
        </NavLink>
      </div>
    </div>
  );
};

export default Sidebar;
