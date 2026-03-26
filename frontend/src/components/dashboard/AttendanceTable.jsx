import React, { useState, useEffect } from 'react';
import { Table, Card, Badge, Spinner, Alert } from 'react-bootstrap';
import axios from 'axios';

const AttendanceTable = () => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const response = await axios.get('http://localhost:8000/payroll/attendance/logs');
        setLogs(response.data);
        setLoading(false);
      } catch (err) {
        setError("Could not load attendance logs. The backend server may be offline.");
        setLoading(false);
        console.error("Error fetching logs:", err);
      }
    };
    fetchLogs();
  }, []);

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
      return (
        <tr>
          <td colSpan="6" className="text-center py-5 text-muted">
            <small>No attendance logs found in the database.</small>
          </td>
        </tr>
      );
    }

    return logs.map((log) => (
      <tr key={log.id}>
        <td className="ps-4">{new Date(log.date).toLocaleDateString()}</td>
        <td className="fw-bold">{log.employee_number}</td>
        <td>{log.full_name}</td>
        <td>{log.department}</td>
        <td>{log.duration_hours} hours</td>
        <td className="pe-4">
          <Badge 
            bg={log.status === 'Approved' ? 'success' : 'warning'} 
            className={`px-3 py-2 ${log.status === 'Approved' ? 'bg-success-subtle text-success border border-success' : 'bg-warning-subtle text-warning border border-warning'}`}
            style={{ fontWeight: '500' }}
          >
            {log.status}
          </Badge>
        </td>
      </tr>
    ));
  };

  return (
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
  );
};

export default AttendanceTable;
