import React, { useState, useEffect } from 'react';
import { Table, Badge, Button, Spinner, Alert } from 'react-bootstrap';
import axios from 'axios';
import 'bootstrap/dist/css/bootstrap.min.css';

const Leaves = () => {
  const [leavesData, setLeavesData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchLeaves = async () => {
      try {
        const response = await axios.get('http://localhost:8000/payroll/leaves/list');
        setLeavesData(response.data);
        setLoading(false);
      } catch (err) {
        setError('Failed to fetch leave applications. Please ensure the backend server is running.');
        setLoading(false);
        console.error("Error fetching leaves:", err);
      }
    };
    fetchLeaves();
  }, []);

  const getStatusBadge = (status) => {
    switch (status) {
      case 'Approved': return 'success';
      case 'Pending': return 'warning';
      case 'Rejected': return 'danger';
      default: return 'secondary';
    }
  };

  const renderContent = () => {
    if (loading) {
      return <div className="text-center p-5"><Spinner animation="border" role="status"><span className="visually-hidden">Loading...</span></Spinner></div>;
    }
    if (error) {
      return <Alert variant="danger">{error}</Alert>;
    }
    if (leavesData.length === 0) {
        return <div className="text-center p-5 text-muted">No leave applications found.</div>;
    }
    return (
      <Table responsive hover>
        <thead>
          <tr>
            <th>Employee</th>
            <th>Start Date</th>
            <th>End Date</th>
            <th>Type</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {leavesData.map((leave) => (
            <tr key={leave.id}>
              <td>{leave.full_name}</td>
              <td>{new Date(leave.start_date).toLocaleDateString()}</td>
              <td>{new Date(leave.end_date).toLocaleDateString()}</td>
              <td>{leave.leave_type}</td>
              <td>
                <Badge bg={getStatusBadge(leave.status)}>{leave.status}</Badge>
              </td>
              <td>
                <Button variant="link" size="sm">View</Button>
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
        <h2 className="fw-bold m-0">Leave Applications</h2>
        <Button variant="primary">New Leave Request</Button>
      </div>
      <div className="bg-white p-4 rounded-4 shadow-sm">
        {renderContent()}
      </div>
    </div>
  );
};

export default Leaves;
