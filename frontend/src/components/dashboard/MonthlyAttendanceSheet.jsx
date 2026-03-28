import React, { useState, useEffect } from 'react';
import { Table, Card, Badge, Spinner, Alert, Form, Row, Col, Button } from 'react-bootstrap';
import axios from 'axios';
import { Calendar, ChevronLeft, ChevronRight, User } from 'lucide-react';

const MonthlyAttendanceSheet = () => {
  const [employees, setEmployees] = useState([]);
  const [selectedEmp, setSelectedEmp] = useState('');
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [year, setYear] = useState(new Date().getFullYear());
  const [sheet, setSheet] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Fetch employees for the dropdown
  useEffect(() => {
    const fetchEmps = async () => {
      try {
        const res = await axios.get('http://localhost:8000/payroll/employees/list');
        setEmployees(res.data);
        if (res.data.length > 0) setSelectedEmp(res.data[0].id);
      } catch (err) {
        console.error("Failed to fetch employees", err);
      }
    };
    fetchEmps();
  }, []);

  // Fetch the sheet when emp, month, or year changes
  useEffect(() => {
    if (!selectedEmp) return;

    const fetchSheet = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await axios.get(`http://localhost:8000/payroll/attendance/sheet/${selectedEmp}?month=${month}&year=${year}`);
        setSheet(res.data);
        setLoading(false);
      } catch (err) {
        setError("Failed to load attendance sheet.");
        setLoading(false);
      }
    };
    fetchSheet();
  }, [selectedEmp, month, year]);

  const getStatusBadge = (status) => {
    switch (status) {
      case 'Present': return <Badge bg="success-subtle" className="text-success border border-success px-3">Present</Badge>;
      case 'Absent': return <Badge bg="danger-subtle" className="text-danger border border-danger px-3">Absent</Badge>;
      case 'On Leave': return <Badge bg="info-subtle" className="text-info border border-info px-3">On Leave</Badge>;
      case 'Holiday': return <Badge bg="warning-subtle" className="text-warning border border-warning px-3">Holiday</Badge>;
      case 'Weekend': return <Badge bg="light" className="text-muted border px-3">Weekend</Badge>;
      default: return <Badge bg="secondary">{status}</Badge>;
    }
  };

  return (
    <div className="mt-4">
      {/* Controls */}
      <Card className="border-0 shadow-sm rounded-4 p-4 mb-4">
        <Row className="align-items-end g-3">
          <Col md={4}>
            <Form.Group>
              <Form.Label className="fw-bold text-muted small">SELECT EMPLOYEE</Form.Label>
              <Form.Select 
                value={selectedEmp} 
                onChange={(e) => setSelectedEmp(e.target.value)}
                className="rounded-pill border-0 shadow-sm px-4"
                style={{ height: '45px' }}
              >
                {employees.map(emp => (
                  <option key={emp.id} value={emp.id}>{emp.lastName}, {emp.firstName} ({emp.employeeId})</option>
                ))}
              </Form.Select>
            </Form.Group>
          </Col>
          <Col md={3}>
            <Form.Group>
              <Form.Label className="fw-bold text-muted small">MONTH</Form.Label>
              <Form.Select 
                value={month} 
                onChange={(e) => setMonth(parseInt(e.target.value))}
                className="rounded-pill border-0 shadow-sm px-4"
                style={{ height: '45px' }}
              >
                {['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'].map((m, idx) => (
                  <option key={m} value={idx + 1}>{m}</option>
                ))}
              </Form.Select>
            </Form.Group>
          </Col>
          <Col md={2}>
            <Form.Group>
              <Form.Label className="fw-bold text-muted small">YEAR</Form.Label>
              <Form.Control 
                type="number" 
                value={year} 
                onChange={(e) => setYear(parseInt(e.target.value))}
                className="rounded-pill border-0 shadow-sm px-4"
                style={{ height: '45px' }}
              />
            </Form.Group>
          </Col>
          <Col md={3} className="text-end">
             {sheet && (
               <div className="d-flex gap-2 justify-content-end">
                 <div className="text-center bg-success-subtle rounded-3 p-2 px-3 border border-success">
                    <div className="fw-bold text-success" style={{ fontSize: '18px' }}>{sheet.present_count}</div>
                    <div className="text-success small fw-bold">PRESENT</div>
                 </div>
                 <div className="text-center bg-danger-subtle rounded-3 p-2 px-3 border border-danger">
                    <div className="fw-bold text-danger" style={{ fontSize: '18px' }}>{sheet.absent_count}</div>
                    <div className="text-danger small fw-bold">ABSENT</div>
                 </div>
               </div>
             )}
          </Col>
        </Row>
      </Card>

      {/* Sheet Table */}
      <Card className="border-0 shadow-sm rounded-4 overflow-hidden">
        {loading ? (
          <div className="text-center py-5"><Spinner /></div>
        ) : error ? (
          <Alert variant="danger" className="m-4">{error}</Alert>
        ) : sheet ? (
          <Table hover responsive className="m-0">
            <thead style={{ backgroundColor: '#FFF5F5' }}>
              <tr className="text-muted small text-uppercase">
                <th className="ps-4 py-3">Day</th>
                <th>Date</th>
                <th>Status</th>
                <th>Remarks / Log ID</th>
              </tr>
            </thead>
            <tbody>
              {sheet.days.map((day) => (
                <tr key={day.date} style={{ backgroundColor: day.status === 'Weekend' ? '#FBFBFB' : 'transparent' }}>
                  <td className="ps-4 fw-bold text-muted">Day {new Date(day.date).getDate()}</td>
                  <td>{new Date(day.date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}</td>
                  <td>{getStatusBadge(day.status)}</td>
                  <td className="text-muted small">
                    {day.status === 'Present' ? `Log: ${day.log_id.substring(0,8)}...` : day.remarks || '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : null}
      </Card>
    </div>
  );
};

export default MonthlyAttendanceSheet;
