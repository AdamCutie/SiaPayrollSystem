import React, { useState, useEffect } from 'react';
import { Row, Col, Card, Table, Badge, Button, Spinner, Alert } from 'react-bootstrap';
import axios from 'axios';
import { Clock, FileText, AlertCircle } from 'lucide-react';
import TopBar from '../components/layout/TopBar';

const Approvals = () => {
  const [activeTab, setActiveTab] = useState('overtime');
  const [period, setPeriod] = useState('today');
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchTabRecord = async (tab, selectedPeriod) => {
    setLoading(true);
    setError(null);
    try {
      let endpoint = '';
      const dateParams = `?period=${selectedPeriod}`;

      if (tab === 'overtime') endpoint = `http://localhost:8000/payroll/attendance/overtime${dateParams}`;
      else if (tab === 'leaves') endpoint = `http://localhost:8000/payroll/leaves/logs${dateParams}`;
      else if (tab === 'penalties') endpoint = `http://localhost:8000/payroll/attendance/penalties${dateParams}`;
      else if (tab === 'undertime') endpoint = `http://localhost:8000/payroll/attendance/undertime${dateParams}`;
      else if (tab === 'payroll') endpoint = `http://localhost:8000/payroll/processing/history${dateParams}`;

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
    fetchTabRecord(activeTab, period);
  }, [activeTab, period]);

  const getStatusBadge = (status) => {
    const s = status?.toLowerCase();
    if (s === 'approved' || s === 'applied' || s === 'completed' || s === 'finalized') return <Badge bg="success-subtle" className="text-success border border-success px-3">Approved</Badge>;
    if (s === 'rejected' || s === 'denied' || s === 'declined') return <Badge bg="danger-subtle" className="text-danger border border-danger px-3">Rejected</Badge>;
    if (s === 'waived') return <Badge bg="info-subtle" className="text-info border border-info px-3">Waived</Badge>;
    if (s === 'detected' || s === 'synced') return <Badge bg="secondary" className="text-dark border px-3">Detected</Badge>;
    return <Badge bg="warning-subtle" className="text-warning border border-warning px-3">Pending</Badge>;
  };

  const formatDuration = (decimalHours) => {
    const hours = Math.floor(decimalHours || 0);
    const minutes = Math.round(((decimalHours || 0) - hours) * 60);
    if (hours === 0) return `${minutes} mins`;
    return `${hours} hr${hours > 1 ? 's' : ''} ${minutes > 0 ? `${minutes} min${minutes > 1 ? 's' : ''}` : ''}`;
  };

  const renderUndertimeTable = () => (
    <Table hover responsive className="align-middle">
      <thead className="bg-light">
        <tr>
          <th>Date</th>
          <th>Employee</th>
          <th>Undertime</th>
          <th>Reason</th>
          <th>Estimated Deduction</th>
          <th className="text-end">Status</th>
        </tr>
      </thead>
      <tbody>
        {data.map(u => (
          <tr key={u._id || u.id}>
            <td>{u.date ? new Date(u.date).toLocaleDateString() : 'N/A'}</td>
            <td>
              <div className="fw-bold">{u.full_name || 'Employee'}</div>
              <small className="text-muted">{u.employeeId}</small>
            </td>
            <td className="fw-bold text-danger">{formatDuration(u.hours)}</td>
            <td className="small text-muted">{u.reason || '-'}</td>
            <td className="text-danger fw-bold">-PHP {(u.total_deduction || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
            <td className="text-end">{getStatusBadge(u.status || 'Synced')}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  );

  const renderPayrollTable = () => (
    <Table hover responsive className="align-middle">
      <thead className="bg-light">
        <tr>
          <th>Employee</th>
          <th>Period</th>
          <th>Net Pay</th>
          <th>Remarks</th>
          <th className="text-end">Status</th>
        </tr>
      </thead>
      <tbody>
        {data.map(p => (
          <tr key={p?._id || p?.id}>
            <td>
              <div className="fw-bold">{p?.full_name || 'N/A'}</div>
              <small className="text-muted">{p?.employee_number || '-'}</small>
            </td>
            <td>
              <small>
                {p?.pay_period_start ? new Date(p.pay_period_start).toLocaleDateString() : '?'} - {p?.pay_period_end ? new Date(p.pay_period_end).toLocaleDateString() : '?'}
              </small>
            </td>
            <td className="fw-bold text-success">PHP {(p?.net_pay ?? 0).toLocaleString()}</td>
            <td>
              <div className="small text-muted" style={{ maxWidth: '250px' }}>
                {p?.remarks || '-'}
              </div>
            </td>
            <td className="text-end">{getStatusBadge(p?.status)}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  );

  const renderOvertimeTable = () => (
    <Table hover responsive className="align-middle">
      <thead className="bg-light">
        <tr>
          <th>Date</th>
          <th>Employee</th>
          <th>Hours</th>
          <th>Reason</th>
          <th>Estimated Pay</th>
          <th className="text-end">Status</th>
        </tr>
      </thead>
      <tbody>
        {data.map(ot => (
          <tr key={ot.id || ot._id}>
            <td>{ot.date ? new Date(ot.date).toLocaleDateString() : 'N/A'}</td>
            <td className="fw-bold">{ot.fullName || 'Employee'}</td>
            <td className="fw-bold text-primary">{formatDuration(ot.hours)}</td>
            <td className="small text-muted">{ot.reason || '-'}</td>
            <td className="text-success fw-bold">+PHP {(ot.total_pay || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
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
          <th>Late Time</th>
          <th>Reason</th>
          <th>Estimated Penalty</th>
          <th className="text-end">Status</th>
        </tr>
      </thead>
      <tbody>
        {data.map(p => (
          <tr key={p.id || p._id}>
            <td>{p.date ? new Date(p.date).toLocaleDateString() : 'N/A'}</td>
            <td className="fw-bold">{p.full_name || 'Employee'}</td>
            <td className="fw-bold text-warning">{formatDuration(p.late_hours)}</td>
            <td>
              <div>{p.reason || p.penalty_type || 'Penalty'}</div>
              {p.source && <small className="text-muted">{p.source}</small>}
            </td>
            <td className="text-danger fw-bold">-PHP {(p.amount || 0).toLocaleString()}</td>
            <td className="text-end">{getStatusBadge(p.status)}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  );

  return (
    <div className="main-content-sia">
      <TopBar title="Monitoring" />

      <Row className="mb-4">
        <Col md={12}>
          <Alert variant="light" className="border rounded-4 shadow-sm">
            Leave and overtime approvals are managed in HR. Finance oversees payroll monitoring, including approvals and data adjustments.
          </Alert>

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
              <FileText size={16} className="me-2"/> Leave Monitoring
            </Button>
            <Button
              onClick={() => setActiveTab('penalties')}
              className={`rounded-pill px-4 border-0 ${activeTab === 'penalties' ? 'shadow-sm' : ''}`}
              style={{ backgroundColor: activeTab === 'penalties' ? '#D29191' : 'transparent', color: activeTab === 'penalties' ? 'white' : '#A08E8E', fontSize: '13px', fontWeight: '600' }}
            >
              <AlertCircle size={16} className="me-2"/> Penalties
            </Button>
            <Button
              onClick={() => setActiveTab('undertime')}
              className={`rounded-pill px-4 border-0 ${activeTab === 'undertime' ? 'shadow-sm' : ''}`}
              style={{ backgroundColor: activeTab === 'undertime' ? '#D29191' : 'transparent', color: activeTab === 'undertime' ? 'white' : '#A08E8E', fontSize: '13px', fontWeight: '600' }}
            >
              <Clock size={16} className="me-2"/> Undertime
            </Button>
            <Button
              onClick={() => setActiveTab('payroll')}
              className={`rounded-pill px-4 border-0 ${activeTab === 'payroll' ? 'shadow-sm' : ''}`}
              style={{ backgroundColor: activeTab === 'payroll' ? '#D29191' : 'transparent', color: activeTab === 'payroll' ? 'white' : '#A08E8E', fontSize: '13px', fontWeight: '600' }}
            >
              <FileText size={16} className="me-2"/> Payroll Status
            </Button>
          </div>

          <div className="ms-3 bg-light p-1 rounded-pill d-inline-flex gap-1 mb-4 shadow-sm border">
            <Button
              variant={period === 'today' ? 'secondary' : 'light'}
              size="sm"
              className="rounded-pill px-3 border-0"
              onClick={() => setPeriod('today')}
              style={{ fontSize: '12px', fontWeight: period === 'today' ? '700' : 'normal' }}
            >
              Today
            </Button>
            <Button
              variant={period === 'yesterday' ? 'secondary' : 'light'}
              size="sm"
              className="rounded-pill px-3 border-0"
              onClick={() => setPeriod('yesterday')}
              style={{ fontSize: '12px', fontWeight: period === 'yesterday' ? '700' : 'normal' }}
            >
              Yesterday
            </Button>
            <Button
              variant={period === 'all' ? 'secondary' : 'light'}
              size="sm"
              className="rounded-pill px-3 border-0"
              onClick={() => setPeriod('all')}
              style={{ fontSize: '12px', fontWeight: period === 'all' ? '700' : 'normal' }}
            >
              All Time
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
                  {activeTab === 'undertime' && renderUndertimeTable()}
                  {activeTab === 'payroll' && renderPayrollTable()}
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
