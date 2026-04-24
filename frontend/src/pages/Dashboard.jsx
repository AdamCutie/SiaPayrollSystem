import React, { useState, useEffect } from 'react';
import { Row, Col } from 'react-bootstrap';
import api from '../api/auth';
import TopBar from '../components/layout/TopBar';
import StatCard from '../components/dashboard/StatCard';
import AttendanceTable from '../components/dashboard/AttendanceTable';
import PayrollChart from '../components/dashboard/PayrollChart';
import { useNavigate } from 'react-router-dom';

const Dashboard = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await api.get('/overview/');
        setStats(response.data);
        setLoading(false);
      } catch (error) {
        console.error("Error fetching dashboard stats:", error);
        setLoading(false);
      }
    };
    fetchStats();
  }, []);

  if (loading) return <div className="p-5 text-center">Loading Dashboard...</div>;
  if (!stats) return <div className="p-5 text-center text-danger">Failed to load data from backend. Ensure the FastAPI server is running.</div>;

  return (
    <div className="main-content-sia">
      <TopBar title="Overview" />

      <Row className="g-4 mb-4">
        <Col md={3}>
          <StatCard title="Total Employees">
            <div className="d-flex justify-content-around text-center">
              <div><h4 className="fw-bold m-0">{stats.employees.total}</h4><small className="text-muted">Total</small></div>
              <div><h4 className="fw-bold m-0">{stats.employees.regular}</h4><small className="text-muted">Regular</small></div>
              <div className="text-warning"><h4 className="fw-bold m-0">{stats.employees.probationary || 0}</h4><small className="text-muted">Probationary</small></div>
            </div>
          </StatCard>
        </Col>

        <Col md={3}>
          <StatCard title="Request Status">
            <div className="d-flex justify-content-around text-center">
              <div><h4 className="fw-bold m-0">{stats.approvals.requested}</h4><small className="text-muted">Requested</small></div>
              <div><h4 className="fw-bold m-0">{stats.approvals.approved}</h4><small className="text-muted">Approved</small></div>
              <div className="text-warning"><h4 className="fw-bold m-0">{stats.approvals.pending}</h4><small className="text-muted">Pending</small></div>
              <div className="text-danger"><h4 className="fw-bold m-0">{stats.approvals.rejected || 0}</h4><small className="text-muted">Rejected</small></div>
            </div>
          </StatCard>
        </Col>

        <Col md={6}>
          <StatCard title="Departments">
            <div className="d-flex flex-wrap gap-2 mt-1 justify-content-center">
              {Object.keys(stats.departments).map(dept => (
                <span key={dept} className="badge rounded-pill bg-light text-dark border px-3 py-2" style={{ fontWeight: '500' }}>
                  {dept}
                </span>
              ))}
            </div>
          </StatCard>
        </Col>
      </Row>

      <Row className="g-4 mb-4">
        <Col md={4}>
          <div className="bg-white p-4 rounded-4 shadow-sm text-center border-bottom border-4 border-success">
            <small className="text-muted text-uppercase" style={{ fontSize: '12px' }}>Total Payout</small>
            <h2 className="fw-bold m-0 mt-1">PHP {stats.payouts.total_payout.toLocaleString(undefined, { minimumFractionDigits: 2 })}</h2>
          </div>
        </Col>
        <Col md={4}>
          <div className="bg-white p-4 rounded-4 shadow-sm text-center border-bottom border-4 border-warning">
            <small className="text-muted text-uppercase" style={{ fontSize: '12px' }}>Delayed Payout</small>
            <h2 className="fw-bold m-0 mt-1 text-warning">PHP {stats.payouts.delayed_payout.toLocaleString(undefined, { minimumFractionDigits: 2 })}</h2>
          </div>
        </Col>
        <Col md={4}>
          <div className="bg-white p-4 rounded-4 shadow-sm text-center border-bottom border-4 border-danger">
            <small className="text-muted text-uppercase" style={{ fontSize: '12px' }}>Rejected Payout</small>
            <h2 className="fw-bold m-0 mt-1 text-danger">PHP {stats.payouts.rejected_payout.toLocaleString(undefined, { minimumFractionDigits: 2 })}</h2>
          </div>
        </Col>
      </Row>

      <PayrollChart />

      <div className="mt-4">
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h6 className="fw-bold m-0">Employee logs</h6>
          <small
            className="text-primary fw-bold"
            style={{ cursor: 'pointer', textDecoration: 'underline' }}
            onClick={() => navigate('/attendance')}
          >
            View All
          </small>
        </div>
        <AttendanceTable />
      </div>
    </div>
  );
};

export default Dashboard;
