import React, { useState, useEffect } from 'react';
import { Row, Col } from 'react-bootstrap';
import axios from 'axios';
import TopBar from '../components/layout/TopBar';
import StatCard from '../components/dashboard/StatCard';
import AttendanceTable from '../components/dashboard/AttendanceTable';
import PayrollChart from '../components/dashboard/PayrollChart';

const Dashboard = () => {
  // State to hold the backend data
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  // Fetch data from our FastAPI backend on component mount
  useEffect(() => {
    const fetchStats = async () => {
      try {
        // Calling our newly built Dashboard Overview API with trailing slash
        const response = await axios.get('http://localhost:8000/payroll/overview/');
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

      {/* Top Stat Cards - Populated with REAL Data */}
      <Row className="g-3 mb-4">
        <Col md={3}>
          <StatCard 
            title="Total Employees" 
            value={stats.employees.total} 
            subValue={stats.employees.regular} 
            subLabel="Regular" 
          />
        </Col>
        
        <Col md={3}>
          <StatCard title="Approval Status">
            <div className="d-flex justify-content-between text-center">
              <div><h4 className="fw-bold m-0">{stats.approvals.requested}</h4><small className="text-muted">Req</small></div>
              <div><h4 className="fw-bold m-0">{stats.approvals.approved}</h4><small className="text-muted">App</small></div>
              <div className="text-warning"><h4 className="fw-bold m-0">{stats.approvals.pending}</h4><small className="text-muted">Pen</small></div>
            </div>
          </StatCard>
        </Col>

        <Col md={3}>
          <StatCard title="Departments">
            <div className="d-flex flex-wrap gap-2 mt-1">
              {Object.keys(stats.departments).map(dept => (
                <span key={dept} className="badge rounded-pill bg-light text-dark border px-3 py-2" style={{ fontWeight: '500' }}>
                  {dept}: {stats.departments[dept]}
                </span>
              ))}
            </div>
          </StatCard>
        </Col>

        <Col md={3} className="d-flex flex-column gap-2">
          <div className="bg-white p-3 rounded-4 shadow-sm border-start border-4 border-primary">
            <h5 className="fw-bold m-0">₱ {stats.payouts.total_payout.toLocaleString(undefined, {minimumFractionDigits: 2})}</h5>
            <small className="text-muted text-uppercase" style={{ fontSize: '10px' }}>Total Payout</small>
          </div>
          <div className="bg-white p-3 rounded-4 shadow-sm border-start border-4 border-danger">
            <h5 className="fw-bold m-0 text-danger">₱ {stats.payouts.delayed_payout.toLocaleString(undefined, {minimumFractionDigits: 2})}</h5>
            <small className="text-muted text-uppercase" style={{ fontSize: '10px' }}>Delayed Payout</small>
          </div>
        </Col>
      </Row>

      {/* Payroll History Chart */}
      <PayrollChart />

      {/* Employee Work Log Table */}
      <div className="mb-4">
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h6 className="fw-bold m-0">Employee List</h6>
          <small className="text-primary cursor-pointer">View All</small>
        </div>
        <AttendanceTable />
      </div>
    </div>
  );
};

export default Dashboard;
