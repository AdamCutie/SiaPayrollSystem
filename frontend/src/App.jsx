import React from 'react';
import { Container, Row, Col, Card, Table, Form, Nav } from 'react-bootstrap';
import { LayoutDashboard, Users, CreditCard, Calendar, FileText, Search, UserCircle } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const data = [
  { name: '01 Mar', value: 4800 }, { name: '02 Mar', value: 5200 },
  { name: '03 Mar', value: 6500 }, { name: '04 Mar', value: 4200 },
  { name: '05 Mar', value: 3800 }, { name: '06 Mar', value: 6000 },
  { name: '07 Mar', value: 3500 },
];

export default function App() {
  return (
    <div className="d-flex" style={{ backgroundColor: '#F9F9F9', minHeight: '100vh' }}>
      {/* SIDEBAR - Fixed Width and Vertical Layout */}
      <div className="sidebar" style={{ width: '260px', backgroundColor: '#FDF4F4', position: 'fixed', height: '100vh', borderRight: '1px solid #eee' }}>
        <div className="p-4 text-center mt-3">
          <h4 className="fw-bold" style={{ color: '#D29191' }}>Sia Essentials</h4>
        </div>
        
        {/* Nav with flex-column ensures links stack DOWN */}
        <Nav className="flex-column gap-1 mt-4">
          <small className="text-uppercase fw-bold text-muted ms-4 mb-2" style={{ fontSize: '11px' }}>Main</small>
          <Nav.Link className="nav-link-sia active"><LayoutDashboard size={20}/> Dashboard</Nav.Link>
          
          <div className="mt-4 flex-column d-flex">
            <small className="text-uppercase fw-bold text-muted ms-4 mb-2" style={{ fontSize: '11px' }}>Management</small>
            <Nav.Link className="nav-link-sia"><Users size={20}/> Employee</Nav.Link>
            <Nav.Link className="nav-link-sia"><CreditCard size={20}/> Payroll</Nav.Link>
            <Nav.Link className="nav-link-sia"><Calendar size={20}/> Attendance</Nav.Link>
            <Nav.Link className="nav-link-sia"><FileText size={20}/> Leaves</Nav.Link>
          </div>
        </Nav>
      </div>

      {/* MAIN CONTENT AREA */}
      <div className="flex-grow-1" style={{ marginLeft: '260px', padding: '40px' }}>
        <div className="d-flex justify-content-between align-items-center mb-4">
          <h2 className="fw-bold">Overview</h2>
          <div className="d-flex align-items-center gap-3 bg-white p-2 rounded-pill shadow-sm px-4">
            <Search size={18} className="text-muted" />
            <Form.Control type="text" placeholder="Search..." className="border-0 shadow-none" style={{ width: '250px' }} />
            <UserCircle size={30} className="text-muted border-start ps-2" />
          </div>
        </div>

        {/* TOP STATS CARDS */}
        <Row className="mb-4 g-3">
          <Col md={3}>
            <Card className="border-0 shadow-sm p-3 h-100 rounded-4">
              <small className="text-muted fw-bold">TOTAL EMPLOYEES</small>
              <div className="d-flex justify-content-between align-items-end mt-3">
                <h2 className="fw-bold m-0">6</h2>
                <div className="text-end">
                  <h5 className="m-0 fw-bold">4</h5>
                  <small className="text-muted">Regular</small>
                </div>
              </div>
            </Card>
          </Col>
          <Col md={3}>
            <Card className="border-0 shadow-sm p-3 text-center h-100 rounded-4">
              <small className="text-muted fw-bold text-uppercase">Approval Status</small>
              <div className="d-flex justify-content-around mt-3">
                <div><h4 className="fw-bold m-0">282</h4><small>Req</small></div>
                <div><h4 className="fw-bold m-0">78</h4><small>App</small></div>
                <div className="text-warning"><h4 className="fw-bold m-0">6</h4><small>Pen</small></div>
              </div>
            </Card>
          </Col>
          <Col md={3}>
            <Card className="border-0 shadow-sm p-3 h-100 rounded-4">
              <small className="text-muted fw-bold">DEPARTMENTS</small>
              <div className="d-flex flex-wrap gap-2 mt-2">
                {['IT', 'HR', 'SALES', 'FINANCE'].map(d => (
                  <span key={d} className="badge bg-light text-dark border px-2 py-1">{d}</span>
                ))}
              </div>
            </Card>
          </Col>
          <Col md={3} className="d-flex flex-column gap-2">
            <div className="bg-white p-3 rounded-4 shadow-sm border-start border-4 border-primary">
              <h5 className="m-0 fw-bold">₱ 5,020.00</h5>
              <small className="text-muted">TOTAL PAYOUT</small>
            </div>
            <div className="bg-white p-3 rounded-4 shadow-sm border-start border-4 border-danger">
              <h5 className="m-0 fw-bold text-danger">₱ 500.00</h5>
              <small className="text-muted">DELAYED PAYOUT</small>
            </div>
          </Col>
        </Row>

        {/* PAYROLL HISTORY CHART */}
        <Card className="border-0 shadow-sm p-4 mb-4 rounded-4">
          <h6 className="fw-bold mb-4">PAYROLL HISTORY</h6>
          <div style={{ width: '100%', height: 280 }}>
            <ResponsiveContainer>
              <BarChart data={data}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eee" />
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fill: '#999', fontSize: 12}} />
                <YAxis axisLine={false} tickLine={false} tick={{fill: '#999', fontSize: 12}} />
                <Tooltip cursor={{fill: 'rgba(0,0,0,0.02)'}} />
                <Bar dataKey="value" fill="#4B8B8B" radius={[4, 4, 0, 0]} barSize={40} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* EMPLOYEE LIST TABLE */}
        <Card className="border-0 shadow-sm rounded-4 overflow-hidden">
          <Table hover responsive className="m-0 align-middle">
            <thead style={{ backgroundColor: '#FFF5F5' }}>
              <tr className="text-muted" style={{ fontSize: '13px' }}>
                <th className="ps-4 py-3">Date</th>
                <th>Employee No.</th>
                <th>Department</th>
                <th>Position</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody style={{ fontSize: '14px' }}>
              <tr>
                <td className="ps-4">01/20/2026</td>
                <td className="fw-bold">2026-001</td>
                <td>Finance</td>
                <td>CEO</td>
                <td><span className="badge bg-success-subtle text-success border border-success px-3 py-2">Approved</span></td>
              </tr>
            </tbody>
          </Table>
        </Card>
      </div>
    </div>
  );
}
