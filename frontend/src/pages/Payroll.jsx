import React, { useState, useEffect } from 'react';
import { Row, Col, Card, Form, Button, Table, Badge } from 'react-bootstrap';
import axios from 'axios';
import { Search, ChevronDown, Check, Download, Calendar } from 'lucide-react';
import TopBar from '../components/layout/TopBar';

const Payroll = () => {
  const [step, setStep] = useState(2); // Starting at Step 2 to match design asset
  const [employees, setEmployees] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dateRange, setDateRange] = useState({ start: '2026-03-01', end: '2026-03-15' });

  useEffect(() => {
    const fetchEmployees = async () => {
      try {
        const response = await axios.get('http://localhost:8000/payroll/employees/list');
        setEmployees(response.data);
        setLoading(false);
      } catch (error) {
        console.error("Error fetching employees:", error);
        setLoading(false);
      }
    };
    fetchEmployees();
  }, []);

  const toggleSelect = (id) => {
    setSelectedIds(prev => 
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  };

  const selectAll = () => {
    if (selectedIds.length === employees.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(employees.map(e => e.id));
    }
  };

  // UI Components
  const WizardProgress = () => (
    <div className="bg-white p-4 rounded-4 shadow-sm mb-4 position-relative">
      <div className="d-flex justify-content-between align-items-center px-5">
        {[1, 2, 3, 4].map((num, idx) => (
          <div key={num} className="d-flex flex-column align-items-center position-relative" style={{ zIndex: 2 }}>
            <div 
              className={`rounded-circle d-flex align-items-center justify-content-center fw-bold mb-2`}
              style={{ 
                width: '40px', 
                height: '40px', 
                backgroundColor: step >= num ? '#D29191' : '#FDF4F4', 
                color: step >= num ? 'white' : '#D29191',
                border: step >= num ? 'none' : '2px solid #D29191'
              }}
            >
              {step > num ? <Check size={20} /> : num}
            </div>
            <span className="fw-bold" style={{ fontSize: '12px', color: step >= num ? '#5A4343' : '#A08E8E' }}>
              {['Period', 'Employee', 'Compute', 'Finance'][idx]}
            </span>
          </div>
        ))}
      </div>
      {/* Connector Line */}
      <div 
        className="position-absolute" 
        style={{ 
          top: '44px', 
          left: '10%', 
          right: '10%', 
          height: '2px', 
          backgroundColor: '#FDF4F4', 
          zIndex: 1 
        }}
      >
        <div 
          style={{ 
            width: `${((step - 1) / 3) * 100}%`, 
            height: '100%', 
            backgroundColor: '#D29191', 
            transition: 'width 0.3s ease' 
          }} 
        />
      </div>
    </div>
  );

  return (
    <div className="main-content-sia">
      <TopBar title="Payroll Management" />

      {/* Top Navigation Pills */}
      <div className="d-flex gap-3 mb-4">
        <Button className="rounded-pill px-5 border-0" style={{ backgroundColor: '#D29191', height: '50px', fontWeight: '600' }}>Payroll Generation</Button>
        <Button variant="outline-secondary" className="rounded-pill px-5 bg-white border-0 text-muted shadow-sm" style={{ height: '50px', fontWeight: '600' }}>Payroll Configuration</Button>
        <Button variant="outline-secondary" className="rounded-pill px-5 bg-white border-0 text-muted shadow-sm" style={{ height: '50px', fontWeight: '600' }}>Payslips</Button>
      </div>

      <WizardProgress />

      <Card className="border-0 shadow-sm rounded-4 p-4">
        <h5 className="fw-bold mb-4" style={{ color: '#5A4343' }}>Step 2 : Employee Selection</h5>

        {/* Filters Header */}
        <div className="d-flex gap-3 mb-4">
          <div className="d-flex align-items-center gap-3 bg-white p-2 rounded-3 border px-4 flex-grow-1" style={{ backgroundColor: '#FFF5F5', borderColor: '#F1E1E1' }}>
            <Search size={18} style={{ color: '#D29191' }} />
            <Form.Control 
              type="text" 
              placeholder="Search..." 
              className="border-0 shadow-none p-0" 
              style={{ fontSize: '14px', backgroundColor: 'transparent' }} 
            />
          </div>
          <div className="position-relative">
            <Form.Select className="rounded-3 border-0 px-4" style={{ height: '45px', backgroundColor: '#FFF5F5', color: '#D29191', fontWeight: '500', width: '200px', appearance: 'none' }}>
              <option>All Roles</option>
            </Form.Select>
            <ChevronDown size={16} className="position-absolute" style={{ top: '15px', right: '15px', color: '#D29191' }} />
          </div>
        </div>

        {/* Select All Row */}
        <div className="p-3 border rounded-3 mb-3 d-flex align-items-center gap-3" style={{ backgroundColor: '#FFFFFF' }}>
          <Form.Check 
            type="checkbox" 
            checked={selectedIds.length === employees.length && employees.length > 0} 
            onChange={selectAll}
            style={{ transform: 'scale(1.2)' }}
          />
          <span className="text-muted fw-500" style={{ fontSize: '14px' }}>Select All</span>
        </div>

        {/* Employee Cards List */}
        <div className="d-flex flex-column gap-3">
          {employees.map((emp) => (
            <div 
              key={emp.id} 
              className={`p-3 border rounded-3 d-flex align-items-center gap-4 transition-all`}
              style={{ 
                backgroundColor: selectedIds.includes(emp.id) ? '#FFF5F5' : '#FFFFFF',
                borderColor: selectedIds.includes(emp.id) ? '#D29191' : '#F1E1E1'
              }}
            >
              <Form.Check 
                type="checkbox" 
                checked={selectedIds.includes(emp.id)}
                onChange={() => toggleSelect(emp.id)}
                style={{ transform: 'scale(1.2)' }}
              />
              
              <div className="flex-grow-1">
                <Row className="align-items-center">
                  <Col md={2}>
                    <small className="d-block text-muted text-uppercase mb-1" style={{ fontSize: '10px', fontWeight: '700' }}>Emp No.</small>
                    <span className="fw-bold" style={{ fontSize: '14px' }}>{emp.employeeId}</span>
                  </Col>
                  <Col md={3}>
                    <small className="d-block text-muted text-uppercase mb-1" style={{ fontSize: '10px', fontWeight: '700' }}>Name</small>
                    <span className="fw-bold" style={{ fontSize: '14px' }}>{emp.lastName}, {emp.firstName}</span>
                  </Col>
                  <Col md={3}>
                    <small className="d-block text-muted text-uppercase mb-1" style={{ fontSize: '10px', fontWeight: '700' }}>Department</small>
                    <span className="text-muted" style={{ fontSize: '14px' }}>{emp.department || 'Unassigned'}</span>
                  </Col>
                  <Col md={2}>
                    <small className="d-block text-muted text-uppercase mb-1" style={{ fontSize: '10px', fontWeight: '700' }}>Position</small>
                    <span className="text-muted" style={{ fontSize: '14px' }}>{emp.position || 'Staff'}</span>
                  </Col>
                  <Col md={2} className="text-end">
                    <small className="d-block text-muted text-uppercase mb-1" style={{ fontSize: '10px', fontWeight: '700' }}>Type</small>
                    <Badge 
                      bg={emp.isActive ? 'success' : 'warning'} 
                      className={`px-3 py-1 ${emp.isActive ? 'bg-success-subtle text-success border border-success' : 'bg-warning-subtle text-warning border border-warning'}`}
                      style={{ borderRadius: '6px', fontSize: '11px' }}
                    >
                      {emp.isActive ? 'Regular' : 'Probationary'}
                    </Badge>
                  </Col>
                </Row>
              </div>
            </div>
          ))}
        </div>

        {/* Action Buttons */}
        <div className="d-flex justify-content-end gap-3 mt-5">
          <Button 
            variant="outline-secondary" 
            className="rounded-pill px-5 border-0" 
            style={{ fontWeight: '600' }}
            onClick={() => setStep(prev => Math.max(1, prev - 1))}
          >
            Back
          </Button>
          <Button 
            className="rounded-pill px-5 border-0 shadow-sm" 
            style={{ backgroundColor: '#D29191', fontWeight: '600' }}
            onClick={() => setStep(prev => Math.min(4, prev + 1))}
          >
            Next Step
          </Button>
        </div>
      </Card>
    </div>
  );
};

export default Payroll;
