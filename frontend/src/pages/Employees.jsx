import React, { useState, useEffect } from 'react';
import { Row, Col, Table, Card, Badge, Form } from 'react-bootstrap';
import axios from 'axios';
import { Search, Download, Building2 } from 'lucide-react';
import TopBar from '../components/layout/TopBar';
import DepartmentCard from '../components/employees/DepartmentCard';

const Employees = () => {
  const [employees, setEmployees] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Filters State
  const [searchQuery, setSearchQuery] = useState('');
  const [deptFilter, setDeptFilter] = useState('All Departments');
  const [statusFilter, setStatusFilter] = useState('All Status');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [empRes, deptRes] = await Promise.all([
          axios.get('http://localhost:8000/payroll/employees/list'),
          axios.get('http://localhost:8000/payroll/departments/summary')
        ]);
        setEmployees(empRes.data);
        setDepartments(deptRes.data);
        setLoading(false);
      } catch (error) {
        console.error("Error fetching employee data:", error);
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  // --- Filtering Logic ---
  const filteredEmployees = employees.filter(emp => {
    // 1. Search Query (Name or ID)
    const matchesSearch = 
      `${emp.firstName} ${emp.lastName}`.toLowerCase().includes(searchQuery.toLowerCase()) ||
      emp.employeeId.includes(searchQuery);
    
    // 2. Department Filter
    const matchesDept = deptFilter === 'All Departments' || emp.department === deptFilter;
    
    // 3. Status Filter (Normalization logic included)
    const displayStatus = emp.contractType === 'Regular' ? 'Regular' : 'Probationary';
    const matchesStatus = statusFilter === 'All Status' || displayStatus === statusFilter;

    return matchesSearch && matchesDept && matchesStatus;
  });

  if (loading) return <div className="p-5 text-center">Loading Employees...</div>;

  return (
    <div className="main-content-sia">
      <TopBar title="Employee Management" />

      {/* Department Section Title */}
      <div className="d-flex justify-content-between align-items-center mb-4">
        <div className="d-flex align-items-center gap-3">
          <div 
            className="rounded-3 d-flex align-items-center justify-content-center" 
            style={{ width: '40px', height: '40px', backgroundColor: '#D29191', color: 'white' }}
          >
            <Building2 size={24} />
          </div>
          <h4 className="fw-bold m-0" style={{ color: '#5A4343' }}>Department</h4>
        </div>
        <button className="btn btn-sm px-4 py-2 rounded-pill shadow-sm" style={{ backgroundColor: '#D29191', color: 'white', fontWeight: '500' }}>
          <Download size={16} className="me-2" /> Export Department Report (PDF)
        </button>
      </div>

      {/* Horizontal Department Cards */}
      <div className="d-flex gap-4 mb-5 overflow-auto pb-3 custom-scrollbar">
        {departments.map((dept, idx) => (
          <DepartmentCard key={idx} name={dept.name} count={dept.employee_count} />
        ))}
      </div>

      {/* Search and Filters */}
      <div className="d-flex justify-content-between align-items-center mb-4">
        <div className="d-flex align-items-center gap-3 bg-white p-2 rounded-pill shadow-sm px-4 flex-grow-1" style={{ maxWidth: '400px' }}>
          <Search size={18} className="text-muted" />
          <Form.Control 
            type="text" 
            placeholder="Search name or ID..." 
            className="border-0 shadow-none p-0" 
            style={{ fontSize: '14px', backgroundColor: 'transparent' }}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <div className="d-flex gap-3">
          <Form.Select 
            className="rounded-pill shadow-sm border-0 px-4" 
            style={{ backgroundColor: '#FFF5F5', color: '#D29191', fontWeight: '500', width: 'auto' }}
            value={deptFilter}
            onChange={(e) => setDeptFilter(e.target.value)}
          >
            <option>All Departments</option>
            {departments.map(d => <option key={d.name} value={d.name}>{d.name}</option>)}
          </Form.Select>
          <Form.Select 
            className="rounded-pill shadow-sm border-0 px-4" 
            style={{ backgroundColor: '#FFF5F5', color: '#D29191', fontWeight: '500', width: 'auto' }}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option>All Status</option>
            <option value="Regular">Regular</option>
            <option value="Probationary">Probationary</option>
          </Form.Select>
        </div>
      </div>

      {/* Employee List Table */}
      <Card className="border-0 shadow-sm rounded-4 overflow-hidden mb-5">
        <Table hover responsive className="m-0 align-middle">
          <thead style={{ backgroundColor: '#FFF9F9' }}>
            <tr className="text-muted" style={{ fontSize: '12px', textTransform: 'uppercase' }}>
              <th className="ps-5 py-4">Employee ID</th>
              <th>Name</th>
              <th>Department</th>
              <th>Role</th>
              <th>Status</th>
              <th className="pe-5">Joining Date</th>
            </tr>
          </thead>
          <tbody style={{ fontSize: '14px', color: '#5A4343' }}>
            {filteredEmployees.length > 0 ? filteredEmployees.map((emp) => (
              <tr key={emp.id} style={{ borderBottom: '1px solid #F8F9FA' }}>
                <td className="ps-5 py-4 fw-bold">{emp.employeeId}</td>
                <td>{emp.lastName}, {emp.firstName}</td>
                <td>{emp.department || 'Unassigned'}</td>
                <td>{emp.role || 'Staff'}</td>
                <td>
                  <Badge 
                    bg={emp.contractType === 'Regular' ? 'success-subtle' : 'warning-subtle'} 
                    className={`px-3 py-2 ${emp.contractType === 'Regular' ? 'text-success border border-success' : 'text-warning border border-warning'}`}
                    style={{ fontWeight: '500', borderRadius: '50px' }}
                  >
                    {emp.contractType === 'Regular' ? 'Regular' : 'Probationary'}
                  </Badge>
                </td>
                <td className="pe-5 text-muted">
                  {emp.hiredDate ? new Date(emp.hiredDate).toLocaleDateString() : 'N/A'}
                </td>
              </tr>
            )) : (
              <tr>
                <td colSpan="6" className="text-center py-5 text-muted">No employees match your filters.</td>
              </tr>
            )}
          </tbody>
        </Table>
      </Card>
    </div>
  );
};

export default Employees;
