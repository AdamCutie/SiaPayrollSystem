import React, { useState, useEffect } from 'react';
import { Row, Col, Card, Table, Badge, Button, Nav, Spinner, Alert } from 'react-bootstrap';
import axios from 'axios';
import { Check, X, Clock, FileText, AlertCircle } from 'lucide-react';
import TopBar from '../components/layout/TopBar';

const Approvals = () => {
  const [activeTab, setActiveTab] = useState('overtime');
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchTabRecord = async (tab) => {
    setLoading(true);
    setError(null);
    try {
      let endpoint = '';
      if (tab === 'overtime') endpoint = 'http://localhost:8000/payroll/attendance/overtime';
      else if (tab === 'leaves') endpoint = 'http://localhost:8000/payroll/leaves/logs?period='; // Real-time HR source
      else if (tab === 'penalties') endpoint = 'http://localhost:8000/payroll/attendance/penalties';

      const response = await axios.get(endpoint);
      setData(response.data);
      setLoading(false);
    } catch (err) {
      console.error(err);
      setError("Failed to fetch records.");
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTabRecord(activeTab);
  }, [activeTab]);

  const getStatusBadge = (status) => {
    const s = status?.toLowerCase();
    if (s === 'approved' || s === 'applied' || s === 'completed') return <Badge bg="success-subtle" className="text-success border border-success px-3">Approved</Badge>;
    if (s === 'rejected' || s === 'denied' || s === 'declined') return <Badge bg="danger-subtle" className="text-danger border border-danger px-3">Rejected</Badge>;
    if (s === 'waived') return <Badge bg="info-subtle" className="text-info border border-info px-3">Waived</Badge>;
    return <Badge bg="warning-subtle" className="text-warning border border-warning px-3">Pending</Badge>;
  };

  const renderOvertimeTable = () => (
    <Table hover responsive className="align-middle">
      <thead className="bg-light">
        <tr>
          <th>Date</th>
          <th>Employee</th>
          <th>Amount</th>
          <th className="text-end">Status</th>
        </tr>
      </thead>
      <tbody>
        {data.map(ot => (
          <tr key={ot.id || ot._id}>
            <td>{ot.date ? new Date(ot.date).toLocaleDateString() : 'N/A'}</td>
            <td className="fw-bold">{ot.full_name || 'Employee'}</td>
            <td className="text-success fw-bold">₱{(ot.total_pay || 0).toLocaleString()}</td>
            <td className="text-end">{getStatusBadge(ot.status)}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  );

  const renderLeavesTable = () => (
    <Table hover responsive className="align-middle">
      <thead className="bg-light">
        <tr>
          <th>Employee</th>
          <th>Period</th>
          <th>Type</th>
          <th className="text-end">Status</th>
        </tr>
      </thead>
      <tbody>
        {data.map(leave => (
          <tr key={leave._id}>
            <td className="fw-bold">{leave.fullName || 'Employee'}</td>
            <td>
              <small>
                {leave.startDate ? new Date(leave.startDate).toLocaleDateString() : '?'} - 
                {leave.endDate ? new Date(leave.endDate).toLocaleDateString() : '?'}
              </small>
            </td>
            <td><Badge bg="light" className="text-dark border">{leave.leaveType || 'Leave'}</Badge></td>
            <td className="text-end">{getStatusBadge(leave.status)}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  );

  const renderPenaltiesTable = () => (
    <Table hover responsive className="align-middle">
      <thead className="bg-light">
        <tr>
          <th>Date</th>
          <th>Employee</th>
          <th>Reason</th>
          <th>Amount</th>
          <th className="text-end">Status</th>
        </tr>
      </thead>
      <tbody>
        {data.map(p => (
          <tr key={p.id || p._id}>
            <td>{p.date ? new Date(p.date).toLocaleDateString() : 'N/A'}</td>
            <td className="fw-bold">{p.full_name || 'Employee'}</td>
            <td>{p.reason || p.penalty_type || 'Penalty'}</td>
            <td className="text-danger fw-bold">-₱{(p.amount || 0).toLocaleString()}</td>
            <td className="text-end">{getStatusBadge(p.status)}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  );

  return (
    <div className="main-content-sia">
      <TopBar title="Monitoring & Approvals" />
      
      <Row className="mb-4">
        <Col md={12}>
          <div className="bg-white p-2 rounded-pill shadow-sm d-inline-flex gap-1 mb-4 overflow-auto max-w-100">
            <Button 
              onClick={() => setActiveTab('overtime')}
              className={`rounded-pill px-4 border-0 ${activeTab === 'overtime' ? 'shadow-sm' : ''}`}
              style={{ backgroundColor: activeTab === 'overtime' ? '#D29191' : 'transparent', color: activeTab === 'overtime' ? 'white' : '#A08E8E', fontSize: '13px', fontWeight: '600' }}
            >
              <Clock size={16} className="me-2"/> Overtime
            </Button>
            <Button 
              onClick={() => setActiveTab('leaves')}
              className={`rounded-pill px-4 border-0 ${activeTab === 'leaves' ? 'shadow-sm' : ''}`}
              style={{ backgroundColor: activeTab === 'leaves' ? '#D29191' : 'transparent', color: activeTab === 'leaves' ? 'white' : '#A08E8E', fontSize: '13px', fontWeight: '600' }}
            >
              <FileText size={16} className="me-2"/> Leave Monitoring (HR)
            </Button>
            <Button 
              onClick={() => setActiveTab('penalties')}
              className={`rounded-pill px-4 border-0 ${activeTab === 'penalties' ? 'shadow-sm' : ''}`}
              style={{ backgroundColor: activeTab === 'penalties' ? '#D29191' : 'transparent', color: activeTab === 'penalties' ? 'white' : '#A08E8E', fontSize: '13px', fontWeight: '600' }}
            >
              <AlertCircle size={16} className="me-2"/> Penalties
            </Button>
          </div>

          <Card className="border-0 shadow-sm rounded-4">
            <Card.Body className="p-4">
              {loading ? (
                <div className="text-center py-5"><Spinner animation="border" variant="secondary" /></div>
              ) : error ? (
                <Alert variant="danger">{error}</Alert>
              ) : data.length === 0 ? (
                <div className="text-center py-5 text-muted">No {activeTab} records found for this period.</div>
              ) : (
                <>
                  {activeTab === 'overtime' && renderOvertimeTable()}
                  {activeTab === 'leaves' && renderLeavesTable()}
                  {activeTab === 'penalties' && renderPenaltiesTable()}
                </>
              )}
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Approvals;
