import React, { useEffect, useMemo, useState } from 'react';
import { Row, Col, Card, Badge, Form, Table, Spinner, Alert } from 'react-bootstrap';
import {
  ArrowLeftRight,
  Calculator,
  CheckCircle2,
  Download,
  Eye,
  Filter,
  Landmark,
  RefreshCw,
  ShieldCheck,
  Users2
} from 'lucide-react';
import axios from 'axios';
import TopBar from '../components/layout/TopBar';

const syncCards = [
  {
    title: 'Synchronization with HR',
    icon: Users2,
    tint: '#FFF4F1',
    border: '#F0D3C8',
    items: [
      'Approvals from HR are mirrored into payroll monitoring.',
      'Leave and attendance updates that change payroll are logged.',
      'Both teams can trace who approved or changed a record.'
    ]
  },
  {
    title: 'Synchronization with Finance',
    icon: Landmark,
    tint: '#F4F7FF',
    border: '#D8E3FF',
    items: [
      'Payroll totals and payout-ready figures can be tracked.',
      'Computation changes are visible before and after release.',
      'Finance-facing sync events are logged for transparency.'
    ]
  }
];

const categoryIcons = {
  Approval: CheckCircle2,
  'Payslip View': Eye,
  'Payslip Download': Download,
  'Payroll Change': Calculator,
  'HR Sync': RefreshCw,
  'Finance Sync': ArrowLeftRight,
  'System Activity': ShieldCheck
};

const getCategoryFromLog = (entry) => {
  const action = (entry.action || '').toLowerCase();
  const module = (entry.module || '').toLowerCase();

  if (action.includes('approve')) return 'Approval';
  if (action.includes('viewed') && action.includes('payslip')) return 'Payslip View';
  if ((action.includes('download') || action.includes('print')) && action.includes('payslip')) return 'Payslip Download';
  if (action.includes('sync') || module.includes('synchron')) return module.includes('finance') || action.includes('finance')
    ? 'Finance Sync'
    : 'HR Sync';
  if (action.includes('configuration') || action.includes('payroll') || action.includes('compute') || action.includes('recomput')) {
    return 'Payroll Change';
  }
  return 'System Activity';
};

const getCategoryBadge = (category) => {
  const styles = {
    Approval: 'success',
    'Payslip View': 'info',
    'Payslip Download': 'primary',
    'Payroll Change': 'warning',
    'HR Sync': 'secondary',
    'Finance Sync': 'dark',
    'System Activity': 'danger'
  };

  const tone = styles[category] || 'secondary';
  return (
    <Badge bg={`${tone}-subtle`} className={`text-${tone} border border-${tone} px-3 py-2`}>
      {category}
    </Badge>
  );
};

const ActivityLogs = () => {
  const [categoryFilter, setCategoryFilter] = useState('All');
  const [timeFilter, setTimeFilter] = useState('today');
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await axios.get(`http://localhost:8000/payroll/activity-logs?limit=200&period=${timeFilter}`);
        setLogs(response.data || []);
      } catch (err) {
        console.error(err);
        setError('Failed to load activity logs.');
      } finally {
        setLoading(false);
      }
    };

    fetchLogs();
  }, [timeFilter]);

  const filteredLogs = useMemo(() => {
    const normalized = logs.map((entry) => ({
      ...entry,
      category: getCategoryFromLog(entry)
    }));
    if (categoryFilter === 'All') return normalized;
    return normalized.filter((entry) => entry.category === categoryFilter);
  }, [categoryFilter, logs]);

  const counts = useMemo(
    () => ({
      approvals: filteredLogs.filter((entry) => entry.category === 'Approval').length,
      payslipAccess: filteredLogs.filter(
        (entry) => entry.category === 'Payslip View' || entry.category === 'Payslip Download'
      ).length,
      computationChanges: filteredLogs.filter((entry) => entry.category === 'Payroll Change').length,
      systemEvents: filteredLogs.filter(
        (entry) =>
          entry.category === 'System Activity' ||
          entry.category === 'HR Sync' ||
          entry.category === 'Finance Sync'
      ).length
    }),
    [filteredLogs]
  );

  const timeFilterLabels = {
    today: "today's activities",
    yesterday: "yesterday's activities",
    week: "last 7 days",
    month: "last 30 days",
    all: "all time"
  };

  return (
    <div className="main-content-sia">
      <TopBar title="Activity logs" />

      <Row className="g-4 mb-4">
        <Col xl={8}>
          <Card className="border-0 shadow-sm rounded-4 h-100">
            <Card.Body className="p-4">
              <div className="d-flex justify-content-between align-items-start gap-3 flex-wrap">
                <div>
                  <small
                    className="text-uppercase fw-bold"
                    style={{ color: '#A08E8E', fontSize: '11px', letterSpacing: '1px' }}
                  >
                    Shared Between HR and Payroll
                  </small>
                  <h4 className="fw-bold mt-2 mb-2" style={{ color: '#5A4343' }}>
                    Transparent activity tracking with vice versa visibility
                  </h4>
                  <p className="text-muted mb-0" style={{ maxWidth: '720px' }}>
                    Both HR and Payroll can see actions performed, approvals, payroll computation
                    changes, payslip access, and synchronization events in one shared log.
                  </p>
                </div>
                <Badge bg="light" className="text-dark border px-3 py-2">
                  HR & Payroll Visible
                </Badge>
              </div>
            </Card.Body>
          </Card>
        </Col>
        <Col xl={4}>
          <Card
            className="border-0 shadow-sm rounded-4 h-100"
            style={{ background: 'linear-gradient(135deg, #fff7f7 0%, #fff 100%)' }}
          >
            <Card.Body className="p-4">
              <div className="d-flex align-items-center gap-3 mb-3">
                <div
                  className="rounded-circle d-flex align-items-center justify-content-center"
                  style={{ width: '48px', height: '48px', backgroundColor: '#FDECEC', color: '#D29191' }}
                >
                  <Filter size={22} />
                </div>
                <div>
                  <div className="fw-bold">Log focus</div>
                  <small className="text-muted">Track access, approvals, and synced changes</small>
                </div>
              </div>
              <div className="d-flex flex-column gap-2">
                <Form.Select
                  value={timeFilter}
                  onChange={(e) => setTimeFilter(e.target.value)}
                  className="border-0 shadow-sm"
                  style={{ height: '46px' }}
                >
                  <option value="today">Today's activities</option>
                  <option value="yesterday">Yesterday's activities</option>
                  <option value="week">Last 7 days</option>
                  <option value="month">Last 30 days</option>
                  <option value="all">All time (Recent 200)</option>
                </Form.Select>
                <Form.Select
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  className="border-0 shadow-sm"
                  style={{ height: '46px' }}
                >
                  <option value="All">All categories</option>
                  <option value="Approval">Approvals</option>
                  <option value="Payslip View">Payslip views</option>
                  <option value="Payslip Download">Payslip downloads</option>
                  <option value="Payroll Change">Payroll computation changes</option>
                  <option value="HR Sync">HR synchronization</option>
                  <option value="Finance Sync">Finance synchronization</option>
                  <option value="System Activity">System activities</option>
                </Form.Select>
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      <Row className="g-4 mb-4">
        <Col md={6} xl={3}>
          <Card className="border-0 shadow-sm rounded-4 h-100">
            <Card.Body className="p-4">
              <small className="text-muted text-uppercase fw-bold" style={{ fontSize: '11px' }}>
                Approvals
              </small>
              <h3 className="fw-bold mt-2 mb-1">{counts.approvals}</h3>
              <div className="text-muted small">Who approved payslips and release-related actions.</div>
            </Card.Body>
          </Card>
        </Col>
        <Col md={6} xl={3}>
          <Card className="border-0 shadow-sm rounded-4 h-100">
            <Card.Body className="p-4">
              <small className="text-muted text-uppercase fw-bold" style={{ fontSize: '11px' }}>
                Payslip Access
              </small>
              <h3 className="fw-bold mt-2 mb-1">{counts.payslipAccess}</h3>
              <div className="text-muted small">Who viewed or downloaded payslips.</div>
            </Card.Body>
          </Card>
        </Col>
        <Col md={6} xl={3}>
          <Card className="border-0 shadow-sm rounded-4 h-100">
            <Card.Body className="p-4">
              <small className="text-muted text-uppercase fw-bold" style={{ fontSize: '11px' }}>
                Computation Changes
              </small>
              <h3 className="fw-bold mt-2 mb-1">{counts.computationChanges}</h3>
              <div className="text-muted small">Changes in payroll computations and impacted records.</div>
            </Card.Body>
          </Card>
        </Col>
        <Col md={6} xl={3}>
          <Card className="border-0 shadow-sm rounded-4 h-100">
            <Card.Body className="p-4">
              <small className="text-muted text-uppercase fw-bold" style={{ fontSize: '11px' }}>
                System Events
              </small>
              <h3 className="fw-bold mt-2 mb-1">{counts.systemEvents}</h3>
              <div className="text-muted small">Activities that happened in the system and sync modules.</div>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      <Row className="g-4 mb-4">
        {syncCards.map(({ title, icon: Icon, tint, border, items }) => (
          <Col md={6} key={title}>
            <Card className="border-0 shadow-sm rounded-4 h-100">
              <Card.Body className="p-4">
                <div className="d-flex align-items-center gap-3 mb-3">
                  <div
                    className="rounded-circle d-flex align-items-center justify-content-center"
                    style={{ width: '48px', height: '48px', backgroundColor: tint, color: '#5A4343' }}
                  >
                    <Icon size={22} />
                  </div>
                  <div>
                    <h5 className="fw-bold mb-1">{title}</h5>
                    <small className="text-muted">Shared transparency across connected teams</small>
                  </div>
                </div>
                <div
                  className="rounded-4 p-3"
                  style={{ backgroundColor: tint, border: `1px solid ${border}` }}
                >
                  {items.map((item) => (
                    <div key={item} className="small mb-2 text-muted">
                      {item}
                    </div>
                  ))}
                </div>
              </Card.Body>
            </Card>
          </Col>
        ))}
      </Row>

      <Card className="border-0 shadow-sm rounded-4">
        <Card.Body className="p-4">
          <div className="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-3">
            <div>
              <h5 className="fw-bold mb-1" style={{ color: '#5A4343' }}>System activity history</h5>
              <small className="text-muted">
                A simple record of approvals, payslip access, payroll changes, and synchronization events.
              </small>
            </div>
            <Badge bg="light" className="text-dark border px-3 py-2">
              {filteredLogs.length} {timeFilterLabels[timeFilter]} shown
            </Badge>
          </div>

          {loading ? (
            <div className="text-center py-5">
              <Spinner animation="border" variant="secondary" />
            </div>
          ) : error ? (
            <Alert variant="danger">{error}</Alert>
          ) : filteredLogs.length === 0 ? (
            <div className="text-center py-5 text-muted">No activity logs found.</div>
          ) : (
            <Table hover responsive className="align-middle">
              <thead className="bg-light">
                <tr>
                  <th>Action</th>
                  <th>Performed By</th>
                  <th>Target</th>
                  <th>When</th>
                  <th>Visibility</th>
                </tr>
              </thead>
              <tbody>
                {filteredLogs.map((entry) => {
                  const Icon = categoryIcons[entry.category] || ShieldCheck;

                  return (
                    <tr key={entry._id}>
                      <td>
                        <div className="d-flex align-items-start gap-3">
                          <div
                            className="rounded-circle d-flex align-items-center justify-content-center flex-shrink-0"
                            style={{
                              width: '38px',
                              height: '38px',
                              backgroundColor: '#FFF4F4',
                              color: '#D29191'
                            }}
                          >
                            <Icon size={18} />
                          </div>
                          <div>
                            <div className="fw-bold mb-1">{entry.action}</div>
                            <div className="d-flex align-items-center gap-2 flex-wrap">
                              {getCategoryBadge(entry.category)}
                              <Badge bg="light" className="text-dark border px-3 py-2 text-capitalize">
                                {entry.source}
                              </Badge>
                              <Badge bg="light" className="text-muted border px-3 py-2">
                                {entry.module}
                              </Badge>
                            </div>
                          </div>
                        </div>
                      </td>
                      <td>
                        <div className="fw-bold">{entry.actorName || 'System'}</div>
                        <small className="text-muted">{entry.actorEmployeeId || entry.actorEmail || entry.actorRole || '-'}</small>
                      </td>
                      <td className="text-muted">{entry.targetInfo || '-'}</td>
                      <td className="text-muted">{new Date(entry.timestamp).toLocaleString()}</td>
                      <td>
                        <Badge bg="success-subtle" className="text-success border border-success px-3 py-2">
                          {entry.visibility}
                        </Badge>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </Table>
          )}
        </Card.Body>
      </Card>
    </div>
  );
};

export default ActivityLogs;
