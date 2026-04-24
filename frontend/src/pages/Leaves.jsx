import React, { useState, useEffect } from 'react';
import { Table, Badge, Button, Spinner, Alert } from 'react-bootstrap';
import api from '../api/auth';
import 'bootstrap/dist/css/bootstrap.min.css';

const Leaves = () => {
  const [leavesData, setLeavesData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchLeaves = async () => {
      try {
        const response = await api.get('/leaves/logs');
        setLeavesData(response.data);
        setLoading(false);
      } catch (err) {
        setError('Failed to fetch synced leave applications. Please ensure the backend server is running.');
        setLoading(false);
        console.error("Error fetching leaves:", err);
      }
    };
    fetchLeaves();
  }, []);

  const getStatusBadge = (status) => {
    if (status === 'Approved') return 'success';
    if (status === 'Rejected') return 'danger';
    return 'warning'; // Pending
  };

  const renderContent = () => {
    if (loading) {
      return <div className="text-center p-5"><Spinner animation="border" role="status"><span className="visually-hidden">Loading...</span></Spinner></div>;
    }
    if (error) {
      return <Alert variant="danger">{error}</Alert>;
    }
    if (leavesData.length === 0) {
        return <div className="text-center p-5 text-muted">No leave applications found in synced payroll data.</div>;
    }
    return (
      <Table responsive hover className="align-middle">
        <thead>
          <tr>
            <th>Employee</th>
            <th>Start Date</th>
            <th>End Date</th>
            <th>Type</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {leavesData.map((leave) => (
            <tr key={leave._id}>
              <td className="fw-bold">{leave.fullName || 'Employee'}</td>
              <td>{new Date(leave.startDate).toLocaleDateString()}</td>
              <td>{new Date(leave.endDate).toLocaleDateString()}</td>
              <td><Badge bg="light" className="text-dark border">{leave.leaveType}</Badge></td>
              <td>
                <Badge bg={getStatusBadge(leave.status)}>
                  {leave.status || 'Pending'}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
    );
  };

  return (
    <div className="main-content-sia">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2 className="fw-bold m-0">Leave History</h2>
        <small className="text-muted">Read-only from synced payroll mirror</small>
      </div>
      <div className="bg-white p-4 rounded-4 shadow-sm">
        {renderContent()}
      </div>
    </div>
  );
};

export default Leaves;
