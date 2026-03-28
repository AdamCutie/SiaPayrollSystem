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
            placeholder="Search for anything..." 
            className="border-0 shadow-none p-0" 
            style={{ fontSize: '14px', backgroundColor: 'transparent' }} 
          />
        </div>
        <div className="d-flex gap-3">
          <Form.Select className="rounded-pill shadow-sm border-0 px-4" style={{ backgroundColor: '#FFF5F5', color: '#D29191', fontWeight: '500', width: 'auto' }}>
            <option>All Departments</option>
          </Form.Select>
          <Form.Select className="rounded-pill shadow-sm border-0 px-4" style={{ backgroundColor: '#FFF5F5', color: '#D29191', fontWeight: '500', width: 'auto' }}>
            <option>All Status</option>
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
            {employees.length > 0 ? employees.map((emp) => (
              <tr key={emp.id} style={{ borderBottom: '1px solid #F8F9FA' }}>
                <td className="ps-5 py-4 fw-bold">{emp.employeeId}</td>
                <td>{emp.lastName}, {emp.firstName}</td>
                <td>{emp.department || 'Unassigned'}</td>
                <td>{emp.position || 'Staff'}</td>
                <td>
                  <Badge 
                    bg={emp.isActive ? 'success' : 'secondary'} 
                    className={`px-3 py-2 ${emp.isActive ? 'bg-success-subtle text-success border border-success' : 'bg-secondary-subtle text-secondary border border-secondary'}`}
                    style={{ fontWeight: '500', borderRadius: '50px' }}
                  >
                    {emp.isActive ? 'Regular' : 'Inactive'}
                  </Badge>
                </td>
                <td className="pe-5 text-muted">
                  {emp.joiningDate ? new Date(emp.joiningDate).toLocaleDateString() : 'N/A'}
                </td>
              </tr>
            )) : (
              <tr>
                <td colSpan="6" className="text-center py-5 text-muted">No employees found.</td>
              </tr>
            )}
          </tbody>
        </Table>
      </Card>
    </div>
  );
};

export default Employees;
