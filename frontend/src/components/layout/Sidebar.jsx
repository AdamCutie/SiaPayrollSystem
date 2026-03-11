import React from 'react';
import { Nav } from 'react-bootstrap';
import { LayoutDashboard, Users, CreditCard, Calendar, FileText } from 'lucide-react';

const Sidebar = () => {
  return (
    <div className="sidebar-sia">
      <div className="logo-container p-4 text-center">
        <h4 className="fw-bold m-0" style={{ color: '#D29191' }}>Sia Essentials</h4>
      </div>
      
      <Nav className="flex-column gap-1">
        <div className="px-4 mb-2 mt-3">
          <small className="text-uppercase fw-bold text-muted" style={{ fontSize: '11px', letterSpacing: '1px' }}>Main</small>
        </div>
        <Nav.Link className="nav-link-sia active"><LayoutDashboard size={20}/> Dashboard</Nav.Link>
        
        <div className="px-4 mb-2 mt-4">
          <small className="text-uppercase fw-bold text-muted" style={{ fontSize: '11px', letterSpacing: '1px' }}>Management</small>
        </div>
        <Nav.Link className="nav-link-sia"><Users size={20}/> Employee</Nav.Link>
        <Nav.Link className="nav-link-sia"><CreditCard size={20}/> Payroll</Nav.Link>
        <Nav.Link className="nav-link-sia"><Calendar size={20}/> Attendance</Nav.Link>
        <Nav.Link className="nav-link-sia"><FileText size={20}/> Leaves</Nav.Link>
      </Nav>
    </div>
  );
};

export default Sidebar;
