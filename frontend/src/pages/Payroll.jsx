import React, { useState, useEffect } from 'react';
import { Row, Col, Card, Form, Button, Table, Badge, Spinner, Alert, Modal } from 'react-bootstrap';
import axios from 'axios';
import { Search, Check, Download, Settings, Users, FileText, Eye, Calendar, Zap, ZapOff } from 'lucide-react';
import TopBar from '../components/layout/TopBar';

const Payroll = () => {
  const [view, setView] = useState('generation'); // 'generation', 'configuration', 'payslips', 'schedule'
  const [step, setStep] = useState(1); // Start at Step 1
  const [employees, setEmployees] = useState([]);
  const [readinessSummary, setReadinessSummary] = useState({ ready_count: 0, incomplete_count: 0 });
  const [selectedIds, setSelectedIds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState(null);
  const [processedCount, setProcessedCount] = useState(0);
  const [dateRange, setDateRange] = useState({ start: '2026-04-01', end: '2026-04-15' });

  // Configuration State
  const [searchQuery, setSearchQuery] = useState('');
  const [editingEmployee, setEditingEmployee] = useState(null);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [configData, setConfigData] = useState({});

  // Payslips State
  const [payrollHistory, setPayrollHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [payslipSearch, setPayslipSearch] = useState('');
  const [historyPeriod, setHistoryPeriod] = useState('today'); // 'all', 'today', 'yesterday'
  const [selectedPayslip, setSelectedPayslip] = useState(null);
  const [showPayslipModal, setShowPayslipModal] = useState(false);

  // Automation Control State
  const [schedule, setSchedule] = useState([]);
  const [scheduleLoading, setScheduleLoading] = useState(false);
  const [isAutomationOn, setIsAutomationOn] = useState(false);

  const trackActivity = async (action, targetInfo, metadata = {}) => {
    try {
      await axios.post('http://localhost:8000/payroll/activity-logs/track', {
        module: 'Payroll',
        action,
        target_info: targetInfo,
        metadata
      });
    } catch (err) {
      console.error('Failed to track activity log', err);
    }
  };

  useEffect(() => {
    if (employees.length === 0) {
      fetchEmployees();
    }
  }, []);

  useEffect(() => {
    if (view === 'payslips') {
      fetchHistory();
    } else if (view === 'schedule') {
      fetchSchedule();
    }
  }, [view, historyPeriod]);

  const fetchEmployees = async () => {
    try {
      setLoading(true);
      const response = await axios.get('http://localhost:8000/payroll/processing/readiness');
      setEmployees(response.data.employees);
      setReadinessSummary({
        ready_count: response.data.ready_count,
        incomplete_count: response.data.incomplete_count
      });
      setLoading(false);
    } catch (err) {
      setError("Failed to fetch employee readiness. Please ensure the backend is running.");
      setLoading(false);
    }
  };

  const fetchHistory = async () => {
    try {
      setHistoryLoading(true);
      let url = 'http://localhost:8000/payroll/processing/history';
      if (historyPeriod !== 'all') {
        url += `?period=${historyPeriod}`;
      }
      const response = await axios.get(url);
      setPayrollHistory(response.data);
      setHistoryLoading(false);
    } catch (err) {
      console.error("Failed to fetch history", err);
      setHistoryLoading(false);
    }
  };

  const fetchSchedule = async () => {
    try {
      setScheduleLoading(true);
      const response = await axios.get('http://localhost:8000/payroll/processing/schedule');
      setSchedule(response.data);
      // Determine if automation is on based on any unprocessed cycle
      const anyAuto = response.data.some(s => !s.is_processed && s.automation_on);
      setIsAutomationOn(anyAuto);
      setScheduleLoading(false);
    } catch (err) {
      console.error("Failed to fetch schedule", err);
      setScheduleLoading(false);
    }
  };

  const handleToggleAutomation = async () => {
    const newState = !isAutomationOn;
    try {
      await axios.patch(`http://localhost:8000/payroll/processing/schedule/automation?enabled=${newState}`);
      setIsAutomationOn(newState);
      fetchSchedule(); 
    } catch (err) {
      alert("Failed to update automation status.");
    }
  };

  const handleRunPayroll = async () => {
    setIsProcessing(true);
    setError(null);
    try {
      const payload = {
        start_date: `${dateRange.start}T00:00:00`,
        end_date: `${dateRange.end}T23:59:59`,
        employee_ids: selectedIds,
      };
      const response = await axios.post('http://localhost:8000/payroll/processing/run-selective', payload);
      setProcessedCount(response.data.processed_count || 0);
      setIsProcessing(false);
      setStep(4); // Move to final step on success
      fetchHistory(); // Refresh history
    } catch (err) {
      setError("Failed to process payroll. The backend returned an error.");
      setIsProcessing(false);
      console.error(err);
    }
  };

  const toggleSelect = (id) => {
    setSelectedIds(prev => 
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  };

  const selectAll = () => {
    if (selectedIds.length === employees.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(employees.map(e => e.id));
    }
  };

  const handleEditConfig = async (emp) => {
    setEditingEmployee(emp);
    try {
      const response = await axios.get(`http://localhost:8000/payroll/employees/${emp.id}/payroll-config`);
      setConfigData(response.data || {});
      setShowConfigModal(true);
    } catch (err) {
      console.error("Failed to fetch config", err);
      alert("Error fetching payroll profile from HR.");
    }
  };

  const formatMoney = (value) =>
    `PHP ${Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  const formatDateLabel = (value) =>
    value ? new Date(value).toLocaleDateString() : 'N/A';

  // --- Helper Functions for Formatting & Validation ---
  const formatCurrencyInput = (value) => {
    if (!value && value !== 0) return '';
    // Remove non-numeric characters except decimal point
    const cleanValue = value.toString().replace(/[^0-9.]/g, '');
    if (!cleanValue) return '';
    
    const parts = cleanValue.split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    return parts.length > 1 ? `${parts[0]}.${parts[1].slice(0, 2)}` : parts[0];
  };

  const handleViewPayslip = (record) => {
    setSelectedPayslip(record);
    setShowPayslipModal(true);
    trackActivity(
      'Viewed payslip',
      `${record.employee_number} | ${record.full_name}`,
      {
        payslip_id: record._id,
        pay_period_start: record.pay_period_start,
        pay_period_end: record.pay_period_end
      }
    );
  };

  const filteredEmployees = employees.filter(emp => 
    emp.full_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    emp.employee_id.includes(searchQuery)
  );

  const filteredHistory = payrollHistory.filter(record => 
    record.full_name.toLowerCase().includes(payslipSearch.toLowerCase()) ||
    record.employee_number.includes(payslipSearch)
  );

  const getContractBadge = (type) => {
    // HR Rule: Map all temporary types to "Probationary"
    const isRegular = type === 'Regular';
    const displayLabel = isRegular ? 'Regular' : 'Probationary';
    const color = isRegular ? 'success' : 'warning';
    
    return (
      <Badge 
        bg={`${color}-subtle`} 
        className={`text-${color} border border-${color} px-3`}
        style={{ fontSize: '10px' }}
      >
        {displayLabel}
      </Badge>
    );
  };

  const getStatusBadge = (status) => {
    const colorMap = {
      'Approved': 'success',
      'Rejected': 'danger',
      'Pending': 'warning'
    };
    const color = colorMap[status] || 'secondary';
    return (
      <Badge 
        bg={`${color}-subtle`} 
        className={`text-${color} border border-${color} px-3`}
        style={{ fontSize: '11px', borderRadius: '50px' }}
      >
        {status?.toUpperCase() || 'PENDING'}
      </Badge>
    );
  };

  const renderGenerationContent = () => {
    switch (step) {
      case 1:
        return (
          <div>
            <h5 className="fw-bold mb-4" style={{ color: '#5A4343' }}>Step 1 : Select Payroll Period</h5>
            <Row>
              <Col md={6}>
                <Form.Group>
                  <Form.Label>Start Date</Form.Label>
                  <Form.Control type="date" value={dateRange.start} onChange={e => setDateRange({...dateRange, start: e.target.value})} />
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group>
                  <Form.Label>End Date</Form.Label>
                  <Form.Control type="date" value={dateRange.end} onChange={e => setDateRange({...dateRange, end: e.target.value})} />
                </Form.Group>
              </Col>
            </Row>
          </div>
        );
      case 2:
        return (
          <div>
            <h5 className="fw-bold mb-4" style={{ color: '#5A4343' }}>Step 2 : Employee Selection</h5>
            
            <div className="p-3 border rounded-3 mb-3 d-flex align-items-center gap-3">
              <input 
                type="checkbox"
                id="select-all-employees"
                className="form-check-input"
                style={{ transform: 'scale(1.2)' }}
                checked={employees.length > 0 && selectedIds.length === employees.length} 
                onChange={(e) => { e.stopPropagation(); selectAll(); }}
                onClick={(e) => e.stopPropagation()}
              />
              <label htmlFor="select-all-employees" className="ms-2 mb-0" style={{ cursor: 'pointer' }}>
                Select All
              </label>
            </div>
            
            <div className="d-flex justify-content-between align-items-center mb-3">
               <h6 className="fw-bold mb-0">Total: {employees.length} Employees</h6>
               <div className="d-flex gap-2">
                  <Badge bg="success-subtle" className="text-success border border-success px-3">{readinessSummary.ready_count} READY</Badge>
                  <Badge bg="danger-subtle" className="text-danger border border-danger px-3">{readinessSummary.incomplete_count} INCOMPLETE</Badge>
               </div>
            </div>

            <div className="d-flex flex-column gap-3">
              {loading ? <div className="text-center"><Spinner /></div> : employees.map((emp) => (
                  <label
                    key={emp.id}
                    className="p-3 border rounded-3 d-flex align-items-center gap-4 w-100 mb-0"
                    style={{ 
                      backgroundColor: !emp.is_ready ? '#FFF9F9' : (selectedIds.includes(emp.id) ? '#FFF5F5' : '#FFFFFF'),
                      borderColor: !emp.is_ready ? '#FFCACA' : (selectedIds.includes(emp.id) ? '#D29191' : '#F1E1E1'),
                      borderStyle: 'solid',
                      borderWidth: '1px',
                      cursor: emp.is_ready ? 'pointer' : 'not-allowed',
                      opacity: emp.is_ready ? 1 : 0.8
                    }}
                    onClick={(e) => {
                      e.preventDefault();
                      if (emp.is_ready) toggleSelect(emp.id);
                    }}
                  >
                    <input 
                      type="checkbox"
                      className="form-check-input"
                      style={{ transform: 'scale(1.2)', flexShrink: 0, pointerEvents: 'none' }}
                      checked={selectedIds.includes(emp.id)}
                      disabled={!emp.is_ready}
                      onChange={() => {}}
                      readOnly
                    />
                    <div className="flex-grow-1">
                    <Row className="align-items-center">
                      <Col md={2}>
                        <small className="d-block text-muted text-uppercase mb-1" style={{ fontSize: '10px', fontWeight: '700' }}>Emp No.</small>
                        <span className="fw-bold" style={{ fontSize: '14px' }}>{emp.employee_id}</span>
                      </Col>
                      <Col md={3}>
                        <small className="d-block text-muted text-uppercase mb-1" style={{ fontSize: '10px', fontWeight: '700' }}>Name</small>
                        <div className="d-flex align-items-center gap-2">
                          <span className="fw-bold" style={{ fontSize: '14px' }}>{emp.full_name}</span>
                          {getContractBadge(emp.contractType)}
                        </div>
                      </Col>
                      <Col md={4}>
                        {!emp.is_ready ? (
                          <div>
                            <small className="d-block text-danger text-uppercase mb-1" style={{ fontSize: '10px', fontWeight: '700' }}>ISSUES FOUND</small>
                            <div className="text-danger small fw-bold">
                              {emp.issues.join(', ')}
                            </div>
                          </div>
                        ) : (
                          <div className="text-success small fw-bold d-flex align-items-center gap-1">
                            <Check size={14} /> Ready for Payroll
                          </div>
                        )}
                      </Col>
                      <Col md={3} className="text-end">
                        <Badge 
                          bg={emp.is_ready ? 'success' : 'danger'} 
                          className={`px-3 py-1 ${emp.is_ready ? 'bg-success-subtle text-success border border-success' : 'bg-danger-subtle text-danger border border-danger'}`}
                          style={{ borderRadius: '6px', fontSize: '11px' }}
                        >
                          {emp.is_ready ? 'Eligible' : 'Ineligible'}
                        </Badge>
                      </Col>
                    </Row>
                  </div>
                </label> 
              ))}
            </div>
          </div>
        );
      case 3:
        return (
          <div className="text-center">
            <h5 className="fw-bold mb-3">Step 3: Compute & Confirm</h5>
            <p>You are about to run payroll for <strong className="text-danger">{selectedIds.length}</strong> selected employees.</p>
            <p>For the period: <strong>{dateRange.start}</strong> to <strong>{dateRange.end}</strong>.</p>
            {error && <Alert variant="danger">{error}</Alert>}
            <p className="text-muted mt-4">Please confirm to proceed.</p>
          </div>
        );
      case 4:
        return (
          <div className="text-center">
            <Check size={48} className="text-success" />
            <h5 className="fw-bold mt-3">Payroll Processed Successfully!</h5>
            <p>Successfully processed payroll for <strong>{processedCount}</strong> employees.</p>
            <Button variant="outline-primary" onClick={() => setStep(1)}>Run Another Payroll</Button>
          </div>
        );
      default:
        return null;
    }
  };

  const renderConfigurationContent = () => (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h5 className="fw-bold mb-0" style={{ color: '#5A4343' }}>Payroll Configuration</h5>
        <div className="position-relative w-25">
          <Search className="position-absolute top-50 start-0 translate-middle-y ms-3 text-muted" size={18} />
          <Form.Control 
            type="text" 
            placeholder="Search employee..." 
            className="rounded-pill ps-5 border-0 shadow-sm" 
            style={{ height: '40px' }}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      <div className="table-responsive">
        <Table hover className="align-middle">
          <thead>
            <tr className="text-muted" style={{ fontSize: '12px' }}>
              <th>EMPLOYEE ID</th>
              <th>NAME</th>
              <th>TYPE</th>
              <th>BASIC SALARY</th>
              <th>ALLOWANCES</th>
              <th>LOANS</th>
              <th className="text-end">ACTION</th>
            </tr>
          </thead>
          <tbody>
            {filteredEmployees.map(emp => (
              <tr key={emp.id}>
                <td className="fw-bold">{emp.employee_id}</td>
                <td className="fw-bold">{emp.lastName}, {emp.firstName}</td>
                <td>
                  {getContractBadge(emp.contractType)}
                </td>
                <td className="fw-bold text-dark">
                   ₱{(emp.basicSalary || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </td>
                <td className="text-success small fw-bold">
                   ₱{((emp.housingAllowance || 0) + (emp.transportAllowance || 0) + (emp.mealAllowance || 0) + (emp.otherAllowances || 0)).toLocaleString()}
                </td>
                <td className="text-danger small fw-bold">
                   ₱{((emp.sssLoan || 0) + (emp.pagIbigLoan || 0) + (emp.companyLoan || 0)).toLocaleString()}
                </td>
                <td className="text-end">
                  <Button 
                    variant="link" 
                    className="p-0 text-decoration-none" 
                    style={{ color: '#D29191' }}
                    onClick={() => handleEditConfig(emp)}
                  >
                    <Eye size={18} />
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      </div>

      <Modal show={showConfigModal} onHide={() => setShowConfigModal(false)} size="lg" centered>
        <Modal.Header closeButton className="border-0 pb-0">
          <Modal.Title className="fw-bold" style={{ color: '#5A4343' }}>
            Payroll Profile: {editingEmployee?.lastName}, {editingEmployee?.firstName}
          </Modal.Title>
        </Modal.Header>
        <Modal.Body className="p-4">
          <Form>
            {/* --- SECTION 1: EARNINGS --- */}
            <h6 className="fw-bold mb-3 border-bottom pb-2 text-primary d-flex justify-content-between">
              1. Monthly Earnings & Allowances 
              <Badge bg="secondary-subtle" className="text-secondary border border-secondary fw-normal" style={{ fontSize: '10px' }}>View Only</Badge>
            </h6>
            <Row className="mb-3">
              <Col md={4}>
                <Form.Group>
                  <Form.Label className="small fw-bold">Basic Salary</Form.Label>
                  <Form.Control 
                    type="text" 
                    value={formatCurrencyInput(configData.basicSalary)} 
                    readOnly
                    className="bg-light text-muted"
                  />
                </Form.Group>
              </Col>
              <Col md={2}>
                <Form.Group>
                  <Form.Label className="small fw-bold">Housing</Form.Label>
                  <Form.Control 
                    type="text" 
                    value={formatCurrencyInput(configData.housingAllowance)} 
                    readOnly
                    className="bg-light text-muted"
                  />
                </Form.Group>
              </Col>
              <Col md={2}>
                <Form.Group>
                  <Form.Label className="small fw-bold">Transport</Form.Label>
                  <Form.Control 
                    type="text" 
                    value={formatCurrencyInput(configData.transportAllowance)} 
                    readOnly
                    className="bg-light text-muted"
                  />
                </Form.Group>
              </Col>
              <Col md={2}>
                <Form.Group>
                  <Form.Label className="small fw-bold">Meal</Form.Label>
                  <Form.Control 
                    type="text" 
                    value={formatCurrencyInput(configData.mealAllowance)} 
                    readOnly
                    className="bg-light text-muted"
                  />
                </Form.Group>
              </Col>
              <Col md={2}>
                <Form.Group>
                  <Form.Label className="small fw-bold">Other</Form.Label>
                  <Form.Control 
                    type="text" 
                    value={formatCurrencyInput(configData.otherAllowances)} 
                    readOnly
                    className="bg-light text-muted"
                  />
                </Form.Group>
              </Col>
            </Row>

            {/* --- SECTION 2: STATUTORY (ALWAYS READ-ONLY) --- */}
            <h6 className="fw-bold mb-3 border-bottom pb-2 d-flex justify-content-between align-items-center mt-4">
              2. Statutory Deductions
              <Badge bg="info-subtle" className="text-info border border-info fw-normal" style={{ fontSize: '10px' }}>Auto-calculated by Law</Badge>
            </h6>
            <Row className="mb-3">
              <Col md={3}>
                <Form.Group>
                  <Form.Label className="small text-muted">SSS Contribution (EE, Monthly)</Form.Label>
                  <Form.Control type="text" value={formatCurrencyInput(configData.sssContribution)} readOnly className="bg-light text-muted" />
                </Form.Group>
              </Col>
              <Col md={3}>
                <Form.Group>
                  <Form.Label className="small text-muted">PhilHealth</Form.Label>
                  <Form.Control type="text" value={formatCurrencyInput(configData.philHealthContribution)} readOnly className="bg-light text-muted" />
                </Form.Group>
              </Col>
              <Col md={3}>
                <Form.Group>
                  <Form.Label className="small text-muted">Pag-IBIG</Form.Label>
                  <Form.Control type="text" value={formatCurrencyInput(configData.pagIbigContribution)} readOnly className="bg-light text-muted" />
                </Form.Group>
              </Col>
              <Col md={3}>
                <Form.Group>
                  <Form.Label className="small text-muted">Withholding Tax</Form.Label>
                  <Form.Control type="text" value="Auto Computed" readOnly className="bg-light text-muted" />
                </Form.Group>
              </Col>
            </Row>
            {(configData.sssEmployeeShare > 0 || configData.sssMPFEmployeeShare > 0) && (
              <div className="mt-2 mb-3 p-3 rounded-3 bg-light border">
                <small className="d-block text-muted fw-bold mb-2">SSS 2025 Breakdown</small>
                <Row>
                  <Col md={4}>
                    <small className="d-block text-muted">MSC</small>
                    <span className="fw-bold">{formatCurrencyInput(configData.sssMonthlySalaryCredit)}</span>
                  </Col>
                  <Col md={4}>
                    <small className="d-block text-muted">Regular SSS (EE)</small>
                    <span className="fw-bold">{formatCurrencyInput(configData.sssEmployeeShare)}</span>
                  </Col>
                  <Col md={4}>
                    <small className="d-block text-muted">MPF (EE)</small>
                    <span className="fw-bold">{formatCurrencyInput(configData.sssMPFEmployeeShare)}</span>
                  </Col>
                </Row>
                <small className="d-block text-muted mt-2">
                  Employer-side amounts are tracked separately: Regular SSS, EC, and MPF employer shares are not deducted from employee pay.
                </small>
              </div>
            )}
            <small className="d-block text-muted mt-n2 mb-3">
              Withholding tax is not shown as a fixed preview here because it depends on the actual taxable pay for the selected cutoff, including attendance, overtime, absences, and taxable allowances.
            </small>

            {/* --- SECTION 3: LOANS & RATES --- */}
            <h6 className="fw-bold mb-3 border-bottom pb-2 mt-4 text-danger d-flex justify-content-between align-items-center">
              3. Active Loans & Penalty Rates
              <Badge bg="secondary-subtle" className="text-secondary border border-secondary fw-normal" style={{ fontSize: '10px' }}>View Only</Badge>
            </h6>
            <Row className="mb-3">
              <Col md={4}>
                <Form.Group>
                  <Form.Label className="small fw-bold text-danger">SSS Loan</Form.Label>
                  <Form.Control 
                    type="text" 
                    value={formatCurrencyInput(configData.sssLoan)} 
                    readOnly
                    className="bg-light text-muted"
                  />
                </Form.Group>
              </Col>
              <Col md={4}>
                <Form.Group>
                  <Form.Label className="small fw-bold text-danger">Pag-IBIG Loan</Form.Label>
                  <Form.Control 
                    type="text" 
                    value={formatCurrencyInput(configData.pagIbigLoan)} 
                    readOnly
                    className="bg-light text-muted"
                  />
                </Form.Group>
              </Col>
              <Col md={4}>
                <Form.Group>
                  <Form.Label className="small fw-bold text-danger">Company Loan</Form.Label>
                  <Form.Control 
                    type="text" 
                    value={formatCurrencyInput(configData.companyLoan)} 
                    readOnly
                    className="bg-light text-muted"
                  />
                </Form.Group>
              </Col>
            </Row>
            <Row>
              <Col md={6}>
                <Form.Group>
                  <Form.Label className="small fw-bold">Absence Penalty (Per Day)</Form.Label>
                  <Form.Control 
                    type="text" 
                    value={formatCurrencyInput(configData.absencePenaltyRate)} 
                    readOnly
                    className="bg-light text-muted"
                  />
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group>
                  <Form.Label className="small fw-bold">Late Penalty (Per Hour)</Form.Label>
                  <Form.Control 
                    type="text" 
                    value={formatCurrencyInput(configData.latePenaltyRate)} 
                    readOnly
                    className="bg-light text-muted"
                  />
                </Form.Group>
              </Col>
            </Row>
          </Form>
        </Modal.Body>
        <Modal.Footer className="border-0">
          <Button variant="outline-secondary" className="rounded-pill px-4" onClick={() => setShowConfigModal(false)}>
            Close Profile
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );

  const renderPayslipsContent = () => (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h5 className="fw-bold mb-0" style={{ color: '#5A4343' }}>Payroll History & Payslips</h5>
        <div className="position-relative w-25">
          <Search className="position-absolute top-50 start-0 translate-middle-y ms-3 text-muted" size={18} />
          <Form.Control 
            type="text" 
            placeholder="Search history..." 
            className="rounded-pill ps-5 border-0 shadow-sm" 
            style={{ height: '40px' }}
            value={payslipSearch}
            onChange={(e) => setPayslipSearch(e.target.value)}
          />
        </div>
      </div>

      <div className="bg-light p-1 rounded-pill d-inline-flex gap-1 mb-4 shadow-sm border">
        <Button
          variant={historyPeriod === 'today' ? 'secondary' : 'light'}
          size="sm"
          className="rounded-pill px-3 border-0"
          onClick={() => setHistoryPeriod('today')}
          style={{ fontSize: '12px', fontWeight: historyPeriod === 'today' ? '700' : 'normal' }}
        >
          Today
        </Button>
        <Button
          variant={historyPeriod === 'yesterday' ? 'secondary' : 'light'}
          size="sm"
          className="rounded-pill px-3 border-0"
          onClick={() => setHistoryPeriod('yesterday')}
          style={{ fontSize: '12px', fontWeight: historyPeriod === 'yesterday' ? '700' : 'normal' }}
        >
          Yesterday
        </Button>
        <Button
          variant={historyPeriod === 'all' ? 'secondary' : 'light'}
          size="sm"
          className="rounded-pill px-3 border-0"
          onClick={() => setHistoryPeriod('all')}
          style={{ fontSize: '12px', fontWeight: historyPeriod === 'all' ? '700' : 'normal' }}
        >
          All Time
        </Button>
      </div>

      <div className="table-responsive">
        <Table hover className="align-middle">
          <thead>
            <tr className="text-muted" style={{ fontSize: '12px' }}>
              <th>EMPLOYEE</th>
              <th>PERIOD</th>
              <th>NET PAY</th>
              <th>STATUS</th>
              <th>PROCESSED AT</th>
              <th className="text-end">ACTION</th>
            </tr>
          </thead>
          <tbody>
            {historyLoading ? <tr><td colSpan="6" className="text-center py-5"><Spinner /></td></tr> : 
             filteredHistory.map(record => (
              <tr key={record._id}>
                <td>
                  <div className="fw-bold">{record.full_name}</div>
                  <small className="text-muted">{record.employee_number}</small>
                </td>
                <td>
                  <Badge bg="light" className="text-dark border">
                    {new Date(record.pay_period_start).toLocaleDateString()} - {new Date(record.pay_period_end).toLocaleDateString()}
                  </Badge>
                </td>
                <td className="fw-bold text-success">
                  ₱{record.net_pay.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </td>
                <td>
                  {getStatusBadge(record.status)}
                </td>
                <td className="text-muted" style={{ fontSize: '13px' }}>
                  {new Date(record.processed_at).toLocaleString()}
                </td>
                <td className="text-end">
                  <Button 
                    variant="outline-primary" 
                    size="sm" 
                    className="rounded-pill px-3"
                    onClick={() => handleViewPayslip(record)}
                  >
                    View Payslip
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      </div>

      <Modal show={showPayslipModal} onHide={() => setShowPayslipModal(false)} size="md" centered>
        <Modal.Header closeButton className="border-0">
          <Modal.Title className="fw-bold w-100 text-center" style={{ color: '#5A4343' }}>
            PAYSLIP
          </Modal.Title>
        </Modal.Header>
        <Modal.Body className="px-4 pb-5">
          {selectedPayslip && (
            <div id="printable-payslip">
              <div className="text-center mb-4 pb-3 border-bottom">
                <h6 className="fw-bold mb-1">Sia Payroll System</h6>
                <small className="text-muted">Electronic Salary Statement</small>
              </div>

              <Row className="mb-4">
                <Col xs={6}>
                  <small className="d-block text-muted text-uppercase fw-bold" style={{ fontSize: '10px' }}>Employee Name</small>
                  <span className="fw-bold">{selectedPayslip.full_name}</span>
                </Col>
                <Col xs={6} className="text-end">
                  <small className="d-block text-muted text-uppercase fw-bold" style={{ fontSize: '10px' }}>Employee No.</small>
                  <span className="fw-bold">{selectedPayslip.employee_number}</span>
                </Col>
              </Row>

              <div className="p-3 bg-light rounded-3 mb-4">
                <Row>
                  <Col xs={6}>
                    <small className="d-block text-muted" style={{ fontSize: '11px' }}>Pay Period</small>
                    <span style={{ fontSize: '13px' }}>{formatDateLabel(selectedPayslip.pay_period_start)} - {formatDateLabel(selectedPayslip.pay_period_end)}</span>
                  </Col>
                  <Col xs={6} className="text-end">
                    <small className="d-block text-muted" style={{ fontSize: '11px' }}>Department</small>
                    <span style={{ fontSize: '13px' }}>{selectedPayslip.department || 'N/A'}</span>
                  </Col>
                </Row>
              </div>

              <div className="mb-4">
                <h6 className="fw-bold mb-3 border-bottom pb-2" style={{ fontSize: '14px' }}>EARNINGS</h6>
                <div className="d-flex justify-content-between mb-1" style={{ fontSize: '13px' }}>
                  <span className="text-muted">Basic Salary</span>
                  <span>{formatMoney(selectedPayslip.basic_salary)}</span>
                </div>
                
                <div className="d-flex justify-content-between mb-1" style={{ fontSize: '13px' }}>
                  <span className="text-muted">Overtime Pay</span>
                  <span>{formatMoney(selectedPayslip.total_overtime)}</span>
                </div>

                {selectedPayslip.excess_days_pay > 0 && (
                  <div className="d-flex justify-content-between mb-1" style={{ fontSize: '13px' }}>
                    <span className="text-muted">Excess / Rest Day Pay</span>
                    <span>{formatMoney(selectedPayslip.excess_days_pay)}</span>
                  </div>
                )}

                {selectedPayslip.holiday_pay > 0 && (
                  <div className="d-flex justify-content-between mb-1" style={{ fontSize: '13px' }}>
                    <span className="text-muted">Regular Holiday Premium (100%)</span>
                    <span>{formatMoney(selectedPayslip.holiday_pay)}</span>
                  </div>
                )}

                {selectedPayslip.special_day_pay > 0 && (
                  <div className="d-flex justify-content-between mb-1" style={{ fontSize: '13px' }}>
                    <span className="text-muted">Special Day Premium (30%)</span>
                    <span>{formatMoney(selectedPayslip.special_day_pay)}</span>
                  </div>
                )}

                {selectedPayslip.worked_holiday_items?.length > 0 && (
                  <div className="mt-2 pt-2 border-top-dashed">
                    <small className="text-muted d-block mb-1" style={{ fontSize: '11px' }}>Worked Holidays</small>
                    {selectedPayslip.worked_holiday_items.map((item, idx) => (
                      <div key={`${item.date}-${idx}`} className="mb-1" style={{ fontSize: '12px' }}>
                        <span className="ps-2">{formatDateLabel(item.date)} | {item.name} ({item.type})</span>
                      </div>
                    ))}
                  </div>
                )}

                <div className="mt-2 pt-2 border-top-dashed">
                  <small className="text-muted d-block mb-1" style={{ fontSize: '11px' }}>Allowances</small>
                  <div className="d-flex justify-content-between mb-1" style={{ fontSize: '12px' }}>
                    <span className="ps-2">Housing</span>
                    <span>{formatMoney(selectedPayslip.housing_allowance)}</span>
                  </div>
                  <div className="d-flex justify-content-between mb-1" style={{ fontSize: '12px' }}>
                    <span className="ps-2">Transport</span>
                    <span>{formatMoney(selectedPayslip.transport_allowance)}</span>
                  </div>
                  <div className="d-flex justify-content-between mb-1" style={{ fontSize: '12px' }}>
                    <span className="ps-2">Meal</span>
                    <span>{formatMoney(selectedPayslip.meal_allowance)}</span>
                  </div>
                  <div className="d-flex justify-content-between mb-1" style={{ fontSize: '12px' }}>
                    <span className="ps-2">Other</span>
                    <span>{formatMoney(selectedPayslip.other_allowances)}</span>
                  </div>
                </div>

                <div className="d-flex justify-content-between mt-2 pt-2 border-top text-success fw-bold">
                  <span>Gross Pay</span>
                  <span>{formatMoney(selectedPayslip.gross_pay)}</span>
                </div>
              </div>

              <div className="mb-4">
                <h6 className="fw-bold mb-3 border-bottom pb-2" style={{ fontSize: '14px' }}>DEDUCTIONS</h6>
                <div className="d-flex justify-content-between mb-1" style={{ fontSize: '13px' }}>
                  <span className="text-muted">SSS Contribution</span>
                  <span>-{formatMoney(selectedPayslip.sss_deduction)}</span>
                </div>
                {(selectedPayslip.sss_employee_share > 0 || selectedPayslip.sss_mpf_employee_share > 0) && (
                  <div className="mt-2 pt-2 border-top-dashed">
                    <small className="text-muted d-block mb-1" style={{ fontSize: '11px' }}>SSS Breakdown</small>
                    <div className="d-flex justify-content-between mb-1" style={{ fontSize: '12px' }}>
                      <span className="ps-2">Regular SSS (EE)</span>
                      <span>-{formatMoney(selectedPayslip.sss_employee_share)}</span>
                    </div>
                    {selectedPayslip.sss_mpf_employee_share > 0 && (
                      <div className="d-flex justify-content-between mb-1" style={{ fontSize: '12px' }}>
                        <span className="ps-2">MPF (EE)</span>
                        <span>-{formatMoney(selectedPayslip.sss_mpf_employee_share)}</span>
                      </div>
                    )}
                    {(selectedPayslip.sss_employer_share > 0 || selectedPayslip.sss_mpf_employer_share > 0 || selectedPayslip.sss_ec_employer > 0) && (
                      <small className="text-muted d-block mt-2 ps-2" style={{ fontSize: '10px' }}>
                        Employer-side SSS/EC is tracked separately and not deducted from employee pay.
                      </small>
                    )}
                  </div>
                )}
                <div className="d-flex justify-content-between mb-1" style={{ fontSize: '13px' }}>
                  <span className="text-muted">PhilHealth</span>
                  <span>-{formatMoney(selectedPayslip.philhealth_deduction)}</span>
                </div>
                <div className="d-flex justify-content-between mb-1" style={{ fontSize: '13px' }}>
                  <span className="text-muted">Pag-IBIG</span>
                  <span>-{formatMoney(selectedPayslip.pagibig_deduction)}</span>
                </div>
                <div className="d-flex justify-content-between mb-1" style={{ fontSize: '13px' }}>
                  <span className="text-muted">Withholding Tax</span>
                  <span>-{formatMoney(selectedPayslip.withholding_tax)}</span>
                </div>
                
                <div className="d-flex justify-content-between mb-1" style={{ fontSize: '13px' }}>
                  <span className="text-muted text-danger">Absence Deduction</span>
                  <span className="text-danger">-{formatMoney(selectedPayslip.absence_deduction)}</span>
                </div>
                
                <div className="mt-2 pt-2 border-top-dashed">
                  <small className="text-muted d-block mb-1" style={{ fontSize: '11px' }}>Loans & Penalties</small>
                  <div className="d-flex justify-content-between mb-1" style={{ fontSize: '12px' }}>
                    <span className="ps-2">Total Loans</span>
                    <span>-{formatMoney(selectedPayslip.total_loans)}</span>
                  </div>
                  <div className="d-flex justify-content-between mb-1" style={{ fontSize: '12px' }}>
                    <span className="ps-2">Late Penalties</span>
                    <span>-{formatMoney(selectedPayslip.total_penalties - (selectedPayslip.undertime_deduction || 0))}</span>
                  </div>
                  {selectedPayslip.undertime_deduction > 0 && (
                    <div className="d-flex justify-content-between mb-1" style={{ fontSize: '12px' }}>
                      <span className="ps-2">Undertime Deduction</span>
                      <span>-{formatMoney(selectedPayslip.undertime_deduction)}</span>
                    </div>
                  )}
                </div>

                {selectedPayslip.total_late_hours > 0 && (
                  <div className="mt-2 pt-2 border-top-dashed">
                    <small className="text-muted d-block mb-1" style={{ fontSize: '11px' }}>
                      Late Details ({selectedPayslip.total_late_hours.toFixed(2)}h total)
                    </small>
                    {selectedPayslip.late_penalty_items?.map((item, idx) => (
                      <div key={`${item.date}-${idx}`} className="mb-1" style={{ fontSize: '12px' }}>
                        <span className="ps-2">{formatDateLabel(item.date)} | {item.late_time} ({Number(item.late_hours || 0).toFixed(2)}h)</span>
                      </div>
                    ))}
                  </div>
                )}

                <div className="d-flex justify-content-between mt-2 pt-2 border-top text-danger fw-bold">
                  <span>Deductions Subtotal</span>
                  <span>-{formatMoney(selectedPayslip.total_deductions)}</span>
                </div>

                <div className="d-flex justify-content-between mt-2 pt-2 border-top text-danger fw-bold">
                  <span>Total Deductions & Penalties</span>
                  <span>-{formatMoney((selectedPayslip.total_deductions || 0) + (selectedPayslip.total_penalties || 0))}</span>
                </div>
              </div>

              <div className="mb-4">
                <h6 className="fw-bold mb-3 border-bottom pb-2" style={{ fontSize: '14px' }}>ATTENDANCE SUMMARY</h6>
                <Row className="text-center g-2">
                  <Col xs={4}>
                    <div className="p-2 border rounded">
                      <small className="d-block text-muted" style={{ fontSize: '10px' }}>Worked</small>
                      <span className="fw-bold">{selectedPayslip.days_worked}d</span>
                    </div>
                  </Col>
                  <Col xs={4}>
                    <div className="p-2 border rounded">
                      <small className="d-block text-muted" style={{ fontSize: '10px' }}>Present</small>
                      <span className="fw-bold text-success">{selectedPayslip.days_present}d</span>
                    </div>
                  </Col>
                  <Col xs={4}>
                    <div className="p-2 border rounded">
                      <small className="d-block text-muted" style={{ fontSize: '10px' }}>Absent</small>
                      <span className="fw-bold text-danger">{selectedPayslip.days_absent}d</span>
                    </div>
                  </Col>
                </Row>
              </div>

              <div className="p-3 rounded-3 mt-4 text-white d-flex justify-content-between align-items-center" style={{ backgroundColor: '#5A4343' }}>
                <span className="fw-bold">NET TAKE HOME PAY</span>
                <h4 className="mb-0 fw-bold">{formatMoney(selectedPayslip.net_pay)}</h4>
              </div>
              
              {selectedPayslip.zero_net_reason && (
                <Alert variant="warning" className="mt-3 mb-0">
                  {selectedPayslip.zero_net_reason}
                  {((selectedPayslip.total_deductions || 0) + (selectedPayslip.total_penalties || 0)) > (selectedPayslip.gross_pay || 0) && (
                    <div className="mt-2">
                      Shortfall: {formatMoney(((selectedPayslip.total_deductions || 0) + (selectedPayslip.total_penalties || 0)) - (selectedPayslip.gross_pay || 0))}
                    </div>
                  )}
                </Alert>
              )}

              <div className="mt-4 text-center">
                <small className="text-muted" style={{ fontSize: '10px' }}>
                  This is a computer-generated document. No signature is required.
                  <br />Generated on {new Date(selectedPayslip.processed_at).toLocaleString()}
                </small>
              </div>
            </div>
          )}
          <div className="mt-5 text-center d-print-none">
            <Button
              variant="outline-secondary"
              className="rounded-pill px-4 me-2"
              onClick={async () => {
                if (selectedPayslip) {
                  await trackActivity(
                    'Downloaded payslip',
                    `${selectedPayslip.employee_number} | ${selectedPayslip.full_name}`,
                    {
                      payslip_id: selectedPayslip._id,
                      pay_period_start: selectedPayslip.pay_period_start,
                      pay_period_end: selectedPayslip.pay_period_end,
                      format: 'print'
                    }
                  );
                }
                window.print();
              }}
            >
              <Download size={18} className="me-2" /> Print PDF
            </Button>
          </div>
        </Modal.Body>
      </Modal>
    </div>
  );

  const renderScheduleContent = () => (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h5 className="fw-bold mb-0" style={{ color: '#5A4343' }}>Payroll Schedule 2026</h5>
        <Button variant={isAutomationOn ? "success" : "outline-secondary"} className="rounded-pill px-4 d-flex align-items-center gap-2 shadow-sm fw-bold" onClick={handleToggleAutomation}>
          {isAutomationOn ? <Zap size={18} /> : <ZapOff size={18} />} Automation: {isAutomationOn ? "ON" : "OFF"}
        </Button>
      </div>
      <div className="table-responsive">
        <Table hover className="align-middle border-top">
          <thead className="bg-light"><tr className="text-muted small" style={{ fontSize: '11px' }}><th>CYCLE</th><th>PERIOD</th><th>CUTOFF</th><th>PAY DATE</th><th>STATUS</th></tr></thead>
          <tbody>
            {schedule.map(s => (
              <tr key={s._id} style={{ opacity: s.is_processed ? 0.6 : 1 }}>
                <td className="fw-bold text-dark">{s.cycle_name}</td>
                <td><small>{formatDateLabel(s.period_start)} - {formatDateLabel(s.period_end)}</small></td>
                <td><Badge bg="light" className="text-dark border fw-normal">{formatDateLabel(s.cutoff_date)}</Badge></td>
                <td><Badge bg="primary-subtle" className="text-primary border border-primary fw-normal">{formatDateLabel(s.pay_date)}</Badge></td>
                <td><Badge bg={s.is_processed ? "success-subtle" : "warning-subtle"} className={s.is_processed ? "text-success border border-success px-3" : "text-warning border border-warning px-3"}>{s.is_processed ? "PROCESSED" : "WAITING"}</Badge></td>
              </tr>
            ))}
          </tbody>
        </Table>
      </div>
    </div>
  );

  const WizardProgress = () => (
    <div className="bg-white p-4 rounded-4 shadow-sm mb-4 position-relative">
      <div className="d-flex justify-content-between align-items-center px-5">
        {[1, 2, 3, 4].map((num, idx) => (
          <div key={num} className="d-flex flex-column align-items-center position-relative" style={{ zIndex: 2 }}>
            <div className={`rounded-circle d-flex align-items-center justify-content-center fw-bold mb-2`} style={{ width: '40px', height: '40px', backgroundColor: step >= num ? '#D29191' : '#FDF4F4', color: step >= num ? 'white' : '#D29191', border: step >= num ? 'none' : '2px solid #D29191' }}>
              {step > num ? <Check size={20} /> : num}
            </div>
            <span className="fw-bold" style={{ fontSize: '12px', color: step >= num ? '#5A4343' : '#A08E8E' }}>
              {['Period', 'Employee', 'Compute', 'Finance'][idx]}
            </span>
          </div>
        ))}
      </div>
      <div className="position-absolute" style={{ top: '44px', left: '10%', right: '10%', height: '2px', backgroundColor: '#FDF4F4', zIndex: 1 }}>
        <div style={{ width: `${((step - 1) / 3) * 100}%`, height: '100%', backgroundColor: '#D29191', transition: 'width 0.3s ease' }} />
      </div>
    </div>
  );

  return (
    <div className="main-content-sia">
      <TopBar title="Payroll Management" />
      <div className="d-flex gap-3 mb-4">
        <Button className="rounded-pill px-5 border-0 shadow-sm d-flex align-items-center gap-2" style={{ backgroundColor: view === 'generation' ? '#D29191' : '#FFFFFF', color: view === 'generation' ? 'white' : '#A08E8E', height: '50px', fontWeight: '600' }} onClick={() => setView('generation')}><Users size={18} />Generation</Button>
        <Button className="rounded-pill px-5 border-0 shadow-sm d-flex align-items-center gap-2" style={{ backgroundColor: view === 'schedule' ? '#D29191' : '#FFFFFF', color: view === 'schedule' ? 'white' : '#A08E8E', height: '50px', fontWeight: '600' }} onClick={() => setView('schedule')}><Calendar size={18} />Schedule</Button>
        <Button className="rounded-pill px-5 border-0 shadow-sm d-flex align-items-center gap-2" style={{ backgroundColor: view === 'configuration' ? '#D29191' : '#FFFFFF', color: view === 'configuration' ? 'white' : '#A08E8E', height: '50px', fontWeight: '600' }} onClick={() => setView('configuration')}><Settings size={18} />Configuration</Button>
        <Button className="rounded-pill px-5 border-0 shadow-sm d-flex align-items-center gap-2" style={{ backgroundColor: view === 'payslips' ? '#D29191' : '#FFFFFF', color: view === 'payslips' ? 'white' : '#A08E8E', height: '50px', fontWeight: '600' }} onClick={() => setView('payslips')}><FileText size={18} />Payslips</Button>
      </div>
      {view === 'generation' && <WizardProgress />}
      <Card className="border-0 shadow-sm rounded-4 p-4">
        <Card.Body>
          {view === 'generation' ? renderGenerationContent() : 
           view === 'schedule' ? renderScheduleContent() :
           view === 'configuration' ? renderConfigurationContent() : 
           renderPayslipsContent()}
        </Card.Body>
        {view === 'generation' && step < 4 && (
          <div className="d-flex justify-content-end gap-3 mt-5">
            <Button variant="outline-secondary" className="rounded-pill px-5 border-0" style={{ fontWeight: '600' }} onClick={() => setStep(prev => Math.max(1, prev - 1))} disabled={step === 1 || isProcessing}>Back</Button>
            <Button className="rounded-pill px-5 border-0 shadow-sm" style={{ backgroundColor: '#D29191', fontWeight: '600' }} onClick={step === 3 ? handleRunPayroll : () => setStep(prev => Math.min(4, prev + 1))} disabled={isProcessing}>{isProcessing ? <Spinner animation="border" size="sm" /> : (step === 3 ? 'Run Payroll' : 'Next Step')}</Button>
          </div>
        )}
      </Card>
    </div>
  );
};

export default Payroll;
