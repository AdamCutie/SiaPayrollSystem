import React, { useState, useEffect } from 'react';
import { Table, Card, Badge, Spinner, Alert, Form } from 'react-bootstrap';
import { useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';

const AttendanceTable = ({ showFilters = false, defaultPeriod = 'today' }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [period, setPeriod] = useState(defaultPeriod);
  const [selectedMonth, setSelectedMonth] = useState('');

  const isDashboard = location.pathname === '/' || location.pathname === '/dashboard';

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        setLoading(true);
        let url = 'http://localhost:8000/payroll/attendance/logs';
        if (selectedMonth) {
          url += `?month=${selectedMonth}`;
        } else {
          url += `?period=${period}`;
        }
        
        const response = await axios.get(url);
        setLogs(response.data);
        setLoading(false);
      } catch (err) {
        setError("Could not load attendance logs.");
        setLoading(false);
      }
    };
    fetchLogs();
  }, [period, selectedMonth]);

  const FilterControls = () => (
    <div className="d-flex justify-content-between align-items-center mb-4">
      <div className="d-flex gap-2">
        {[
          { label: 'Today', value: 'today' },
          { label: 'Yesterday', value: 'yesterday' },
          { label: 'Last 7 Days', value: 'lastweek' },
          { label: 'All Time', value: '' }
        ].map((btn) => (
          <button
            key={btn.value}
            onClick={() => { setPeriod(btn.value); setSelectedMonth(''); }}
            className="btn rounded-pill px-4 shadow-sm border-0"
            style={{ 
              backgroundColor: !selectedMonth && period === btn.value ? '#D29191' : '#FFFFFF',
              color: !selectedMonth && period === btn.value ? 'white' : '#A08E8E',
              fontWeight: '600', fontSize: '13px'
            }}
          >
            {btn.label}
          </button>
        ))}
      </div>

      <div style={{ width: '200px' }}>
        <Form.Select 
          value={selectedMonth} 
          onChange={(e) => { setSelectedMonth(e.target.value); setPeriod(''); }}
          className="rounded-pill border-0 shadow-sm px-4"
          style={{ fontSize: '13px', fontWeight: '600', height: '40px' }}
        >
          <option value="">Specific Month</option>
          {['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'].map((m, idx) => (
            <option key={m} value={idx + 1}>{m}</option>
          ))}
        </Form.Select>
      </div>
    </div>
  );

  const renderTableContent = () => {
    if (loading) {
      return (
        <tr>
          <td colSpan="6" className="text-center py-5">
            <Spinner animation="border" size="sm" />
            <span className="ms-2">Loading logs...</span>
          </td>
        </tr>
      );
    }

    if (error) {
      return (
        <tr>
          <td colSpan="6">
            <Alert variant="danger" className="m-3 text-center">{error}</Alert>
          </td>
        </tr>
      );
    }

    if (logs.length === 0) {
      const periodLabel = selectedMonth ? 'this month' : (period || 'all time');
      return (
        <tr>
          <td colSpan="6" className="text-center py-5 text-muted">
            <div className="mb-2">No attendance logs found for <strong>{periodLabel}</strong>.</div>
            <small>Note: System is searching based on the actual current date (March 2026).</small>
          </td>
        </tr>
      );
    }

    return logs.map((log) => (
      <tr 
        key={log._id}
        onClick={() => isDashboard && navigate('/attendance')}
        style={{ cursor: isDashboard ? 'pointer' : 'default' }}
        className={isDashboard ? 'attendance-row-hover' : ''}
      >
        <td className="ps-4">{log.date ? new Date(log.date).toLocaleDateString() : 'N/A'}</td>
        <td className="fw-bold">{log.employeeId}</td>
        <td>{log.employeeName || 'Employee'}</td>
        <td>{log.department || 'N/A'}</td>
        <td>Completed</td>
        <td className="pe-4">
          <Badge 
            bg="success" 
            className="px-3 py-2 bg-success-subtle text-success border border-success"
            style={{ fontWeight: '500' }}
          >
            Approved
          </Badge>
        </td>
      </tr>
    ));
  };

  return (
    <div>
      {showFilters && <FilterControls />}
      <Card className="border-0 shadow-sm rounded-4 overflow-hidden">
      <Table hover responsive className="m-0 align-middle">
        <thead style={{ backgroundColor: '#FFF5F5' }}>
          <tr className="text-muted" style={{ fontSize: '12px', textTransform: 'uppercase' }}>
            <th className="ps-4 py-3">Date</th>
            <th>Employee No.</th>
            <th>Name</th>
            <th>Department</th>
            <th>Duration</th>
            <th className="pe-4">Action</th>
          </tr>
        </thead>
        <tbody style={{ fontSize: '14px' }}>
          {renderTableContent()}
        </tbody>
      </Table>
    </Card>
    </div>
  );
};

export default AttendanceTable;
