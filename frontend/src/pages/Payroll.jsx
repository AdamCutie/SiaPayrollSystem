import React, { useState, useEffect } from 'react';
import { Row, Col, Card, Form, Button, Table, Badge, Spinner, Alert, Modal } from 'react-bootstrap';
import axios from 'axios';
import { Search, Check, Download, Settings, Users, FileText, Eye, Calendar, Zap, ZapOff, Trash2 } from 'lucide-react';
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

  // Retro Adjustment State
  const [showRetroModal, setShowRetroModal] = useState(false);
  const [retroData, setRetroData] = useState({ amount: '', reason: '' });
  const [retroEmployee, setRetroEmployee] = useState(null);
  const [employeeAdjustments, setEmployeeAdjustments] = useState([]);
  const [adjustmentsLoading, setAdjustmentsLoading] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  // Payslips State
  const [payrollHistory, setPayrollHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [payslipSearch, setPayslipSearch] = useState('');
  const [historyPeriod, setHistoryPeriod] = useState('today'); // 'all', 'today', 'yesterday'
  const [selectedPayslipMonth, setSelectedPayslipMonth] = useState('');
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
  }, [view, historyPeriod, selectedPayslipMonth]);

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
      const params = [];
      if (selectedPayslipMonth) {
        params.push(`month=${selectedPayslipMonth}`);
      } else if (historyPeriod && historyPeriod !== 'all') {
        params.push(`period=${historyPeriod}`);
      }
      
      if (params.length > 0) {
        url += `?${params.join('&')}`;
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

  const fetchEmployeeAdjustments = async (employeeId) => {
    try {
      setAdjustmentsLoading(true);
      const response = await axios.get(`http://localhost:8000/payroll/processing/adjustments/${employeeId}`);
      setEmployeeAdjustments(response.data);
      setAdjustmentsLoading(false);
    } catch (err) {
      console.error("Failed to fetch adjustments", err);
      setAdjustmentsLoading(false);
    }
  };

  const handleAddRetro = async () => {
    if (!retroEmployee || !retroData.amount) return;
    try {
      await axios.post('http://localhost:8000/payroll/processing/adjustments', {
        employee_id: retroEmployee.id,
        employee_number: retroEmployee.employee_id,
        amount: parseFloat(retroData.amount),
        reason: retroData.reason || 'Manual Adjustment'
      });
      // Refresh the list immediately
      fetchEmployeeAdjustments(retroEmployee.id);
      setRetroData({ amount: '', reason: '' });
      alert("Retroactive adjustment added! It will be applied on the next payroll run for this employee.");
    } catch (err) {
      alert("Failed to add adjustment.");
    }
  };

  const handleDeleteAdjustment = async (adjId) => {
    if (!window.confirm("Are you sure you want to delete this pending adjustment?")) return;
    try {
      await axios.delete(`http://localhost:8000/payroll/processing/adjustments/${adjId}`);
      fetchEmployeeAdjustments(retroEmployee.id);
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to delete adjustment.");
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
                  <div className="d-flex justify-content-end gap-2">
                    <Button 
                      variant="link" 
                      className="p-0 text-decoration-none" 
                      style={{ color: '#D29191' }}
                      onClick={() => {
                        setRetroEmployee(emp);
                        setRetroData({ amount: '', reason: '' });
                        fetchEmployeeAdjustments(emp.id);
                        setShowRetroModal(true);
                      }}
                      title="Add Retroactive Adjustment"
                    >
                      <Zap size={18} />
                    </Button>
                    <Button 
                      variant="link" 
                      className="p-0 text-decoration-none" 
                      style={{ color: '#D29191' }}
                      onClick={() => handleEditConfig(emp)}
                      title="View Profile"
                    >
                      <Eye size={18} />
                    </Button>
                  </div>
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
                  <Form.Control 
                    type="text" 
                    value="Payroll Calculation" 
                    readOnly 
                    className="bg-light fw-bold text-center" 
                    style={{ color: '#D29191', fontSize: '12px' }} 
                  />
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
                Withholding tax is not displayed as a fixed amount in the profile because it is <strong>dynamically calculated</strong> during each payroll run. The exact amount depends on the employee's actual taxable earnings for that period (including basic pay, overtime, night differential, and absences).
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

      <div className="d-flex justify-content-between align-items-center mb-4">
        <div className="d-flex gap-2">
          {[
            { label: 'Today', value: 'today' },
            { label: 'Yesterday', value: 'yesterday' },
            { label: 'Last 7 Days', value: 'lastweek' },
            { label: 'All Time', value: 'all' }
          ].map((btn) => (
            <Button
              key={btn.value}
              onClick={() => { setHistoryPeriod(btn.value); setSelectedPayslipMonth(''); }}
              className="rounded-pill px-4 shadow-sm border-0"
              style={{ 
                backgroundColor: !selectedPayslipMonth && historyPeriod === btn.value ? '#D29191' : '#FFFFFF',
                color: !selectedPayslipMonth && historyPeriod === btn.value ? 'white' : '#A08E8E',
                fontWeight: '600', fontSize: '13px'
              }}
            >
              {btn.label}
            </Button>
          ))}
        </div>

        <div style={{ width: '200px' }}>
          <Form.Select 
            value={selectedPayslipMonth} 
            onChange={(e) => { setSelectedPayslipMonth(e.target.value); setHistoryPeriod(''); }}
            className="rounded-pill border-0 shadow-sm px-4"
            style={{ fontSize: '13px', fontWeight: '600', height: '40px' }}
          >
            <option value="">Specific Month</option>
            {['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'].map((m, idx) => (
              <option key={m} value={idx + 1}>{m}</option>
            ))}
          </Form.Select>
        </div>
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

      <Modal show={showPayslipModal} onHide={() => setShowPayslipModal(false)} size="xl" centered scrollable>
        <Modal.Header closeButton className="border-0 bg-light">
          <Modal.Title className="fw-bold w-100 text-center text-uppercase" style={{ color: '#5A4343', letterSpacing: '1px' }}>
            Electronic Salary Statement
          </Modal.Title>
        </Modal.Header>
        <Modal.Body className="p-0">
          {selectedPayslip && (
            <div id="printable-payslip" className="p-4" style={{ backgroundColor: '#fff', color: '#000', fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif" }}>
              {/* --- HEADER SECTION --- */}
              <div className="text-center mb-4">
                <h4 className="fw-bold mb-1">Sia Payroll System</h4>
                <div className="text-muted small">
                  Payslip for the Period {formatDateLabel(selectedPayslip.pay_period_start)} - {formatDateLabel(selectedPayslip.pay_period_end)}
                </div>
                {selectedPayslip.pay_date && (
                  <div className="fw-bold small text-primary mt-1">
                    Scheduled Payday: {formatDateLabel(selectedPayslip.pay_date)}
                  </div>
                )}
              </div>

              <div className="border border-dark mb-4 p-3 bg-light">
                <Row className="g-3" style={{ fontSize: '12px' }}>
                  <Col md={4}>
                    <div className="mb-2"><strong>Employee Code:</strong> <span className="ms-1">{selectedPayslip.employee_number}</span></div>
                    <div><strong>Employee Name:</strong> <span className="ms-1 text-uppercase">{selectedPayslip.full_name}</span></div>
                  </Col>
                  <Col md={4}>
                    <div className="mb-2"><strong>Designation:</strong> <span className="ms-1">{selectedPayslip.department || 'Staff'}</span></div>
                    <div><strong>Hourly Salary:</strong> <span className="ms-1">{selectedPayslip.hourly_rate ? Number(selectedPayslip.hourly_rate).toFixed(2) : '---'}</span></div>
                  </Col>
                  <Col md={4}>
                    <div className="mb-2"><strong>SSS No:</strong> <span className="ms-1">{selectedPayslip.sss_number || '---'}</span></div>
                    <div className="mb-2"><strong>Phil Health No:</strong> <span className="ms-1">{selectedPayslip.philhealth_number || '---'}</span></div>
                    <div><strong>Pag-IBIG No:</strong> <span className="ms-1">{selectedPayslip.pagibig_number || '---'}</span></div>
                  </Col>                </Row>
              </div>

              {/* --- MAIN EARNINGS & DEDUCTIONS TABLE --- */}
              <div className="border border-dark mb-4">
                <Row className="g-0">
                  {/* EARNINGS COLUMN */}
                  <Col md={6} className="border-end border-dark">
                    <div className="bg-dark text-white p-1 text-center fw-bold small">EARNINGS</div>
                    <div className="d-flex border-bottom border-dark bg-light fw-bold small p-1">
                      <div className="flex-grow-1">Description</div>
                      <div className="text-end" style={{ width: '80px' }}>Hrs</div>
                      <div className="text-end" style={{ width: '100px' }}>Total</div>
                    </div>

                    {/* TAXABLE EARNINGS */}
                    <div className="bg-dark text-white p-1 fw-bold" style={{ fontSize: '10px' }}>TAXABLE EARNINGS</div>
                    <div className="p-2" style={{ minHeight: '150px', fontSize: '12px' }}>
                      <div className="d-flex mb-1">
                        <div className="flex-grow-1">BASIC PAY</div>
                        <div className="text-end" style={{ width: '80px' }}>---</div>
                        <div className="text-end" style={{ width: '100px' }}>{formatMoney(selectedPayslip.basic_salary).replace('PHP ', '')}</div>
                      </div>
                      {selectedPayslip.total_overtime > 0 && (
                        <div className="d-flex mb-1">
                          <div className="flex-grow-1">OVERTIME PAY</div>
                          <div className="text-end" style={{ width: '80px' }}>{selectedPayslip.total_overtime_hours ? Number(selectedPayslip.total_overtime_hours).toFixed(2) : '---'}</div>
                          <div className="text-end" style={{ width: '100px' }}>{formatMoney(selectedPayslip.total_overtime).replace('PHP ', '')}</div>
                        </div>
                      )}
                      {selectedPayslip.total_nd_pay > 0 && (
                        <div className="d-flex mb-1">
                          <div className="flex-grow-1">NIGHT DIFFERENTIAL</div>
                          <div className="text-end" style={{ width: '80px' }}>{selectedPayslip.total_nd_hours ? Number(selectedPayslip.total_nd_hours).toFixed(2) : '---'}</div>
                          <div className="text-end" style={{ width: '100px' }}>{formatMoney(selectedPayslip.total_nd_pay).replace('PHP ', '')}</div>
                        </div>
                      )}
                      {selectedPayslip.retro_pay !== 0 && (
                        <div className="d-flex mb-1">
                          <div className="flex-grow-1">RETROACTIVE ADJUSTMENT</div>
                          <div className="text-end" style={{ width: '80px' }}>---</div>
                          <div className="text-end" style={{ width: '100px' }}>{formatMoney(selectedPayslip.retro_pay).replace('PHP ', '')}</div>
                        </div>
                      )}
                      {selectedPayslip.holiday_pay > 0 && (
                        <div className="d-flex mb-1">
                          <div className="flex-grow-1">REGULAR HOLIDAY PREMIUM (100%)</div>
                          <div className="text-end" style={{ width: '80px' }}>---</div>
                          <div className="text-end" style={{ width: '100px' }}>{formatMoney(selectedPayslip.holiday_pay).replace('PHP ', '')}</div>
                        </div>
                      )}
                      {selectedPayslip.special_day_pay > 0 && (
                        <div className="d-flex mb-1">
                          <div className="flex-grow-1">SPECIAL DAY PREMIUM (30%)</div>
                          <div className="text-end" style={{ width: '80px' }}>---</div>
                          <div className="text-end" style={{ width: '100px' }}>{formatMoney(selectedPayslip.special_day_pay).replace('PHP ', '')}</div>
                        </div>
                      )}
                      {selectedPayslip.excess_days_pay > 0 && (
                        <div className="d-flex mb-1">
                          <div className="flex-grow-1">EXCESS / REST DAY PAY</div>
                          <div className="text-end" style={{ width: '80px' }}>---</div>
                          <div className="text-end" style={{ width: '100px' }}>{formatMoney(selectedPayslip.excess_days_pay).replace('PHP ', '')}</div>
                        </div>
                      )}
                    </div>
                    
                    <div className="d-flex border-top border-bottom border-dark p-1 fw-bold small">
                      <div className="flex-grow-1">TOTAL TAXABLE EARNINGS (A)</div>
                      <div className="text-end" style={{ width: '100px' }}>
                        {(
                          (selectedPayslip.basic_salary || 0) + 
                          (selectedPayslip.total_overtime || 0) + 
                          (selectedPayslip.total_nd_pay || 0) + 
                          (selectedPayslip.holiday_pay || 0) + 
                          (selectedPayslip.special_day_pay || 0) + 
                          (selectedPayslip.excess_days_pay || 0)
                        ).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </div>
                    </div>

                    {/* NON-TAXABLE EARNINGS */}
                    <div className="bg-dark text-white p-1 fw-bold" style={{ fontSize: '10px' }}>NON-TAXABLE EARNINGS</div>
                    <div className="p-2" style={{ minHeight: '100px', fontSize: '12px' }}>
                      {selectedPayslip.housing_allowance > 0 && (
                        <div className="d-flex mb-1"><div className="flex-grow-1">HOUSING ALLOWANCE</div><div className="text-end" style={{ width: '100px' }}>{formatMoney(selectedPayslip.housing_allowance).replace('PHP ', '')}</div></div>
                      )}
                      {selectedPayslip.transport_allowance > 0 && (
                        <div className="d-flex mb-1"><div className="flex-grow-1">TRANSPORT ALLOWANCE</div><div className="text-end" style={{ width: '100px' }}>{formatMoney(selectedPayslip.transport_allowance).replace('PHP ', '')}</div></div>
                      )}
                      {selectedPayslip.meal_allowance > 0 && (
                        <div className="d-flex mb-1"><div className="flex-grow-1">MEAL ALLOWANCE</div><div className="text-end" style={{ width: '100px' }}>{formatMoney(selectedPayslip.meal_allowance).replace('PHP ', '')}</div></div>
                      )}
                      {selectedPayslip.other_allowances > 0 && (
                        <div className="d-flex mb-1"><div className="flex-grow-1">OTHER ALLOWANCES</div><div className="text-end" style={{ width: '100px' }}>{formatMoney(selectedPayslip.other_allowances).replace('PHP ', '')}</div></div>
                      )}
                    </div>
                    <div className="d-flex border-top border-bottom border-dark p-1 fw-bold small">
                      <div className="flex-grow-1">TOTAL NON-TAXABLE EARNINGS (B)</div>
                      <div className="text-end" style={{ width: '100px' }}>
                        {(
                          (selectedPayslip.housing_allowance || 0) + 
                          (selectedPayslip.transport_allowance || 0) + 
                          (selectedPayslip.meal_allowance || 0) + 
                          (selectedPayslip.other_allowances || 0)
                        ).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </div>
                    </div>

                    <div className="d-flex p-1 fw-bold small mt-auto border-top border-dark bg-light">
                      <div className="flex-grow-1">GROSS EARNINGS (G) (A+B)</div>
                      <div className="text-end" style={{ width: '100px' }}>
                        {selectedPayslip.gross_pay.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </div>
                    </div>
                  </Col>

                  {/* DEDUCTIONS COLUMN */}
                  <Col md={6}>
                    <div className="bg-dark text-white p-1 text-center fw-bold small">DEDUCTIONS</div>
                    <div className="d-flex border-bottom border-dark bg-light fw-bold small p-1">
                      <div className="flex-grow-1">Description</div>
                      <div className="text-end" style={{ width: '100px' }}>Total</div>
                    </div>

                    {/* MANDATORY GOVT CONTRIBUTIONS */}
                    <div className="bg-dark text-white p-1 fw-bold" style={{ fontSize: '10px' }}>MANDATORY GOVT CONTRIBUTIONS</div>
                    <div className="p-2" style={{ minHeight: '120px', fontSize: '12px' }}>
                      <div className="d-flex mb-1">
                        <div className="flex-grow-1">SSS CONTRIBUTION EMPLOYEE SHARE</div>
                        <div className="text-end" style={{ width: '100px' }}>{formatMoney(selectedPayslip.sss_deduction).replace('PHP ', '')}</div>
                      </div>
                      <div className="d-flex mb-1">
                        <div className="flex-grow-1">PHIC CONTRIBUTION EMPLOYEE SHARE</div>
                        <div className="text-end" style={{ width: '100px' }}>{formatMoney(selectedPayslip.philhealth_deduction).replace('PHP ', '')}</div>
                      </div>
                      <div className="d-flex mb-1">
                        <div className="flex-grow-1">HDMF CONTRIBUTION EMPLOYEE SHARE</div>
                        <div className="text-end" style={{ width: '100px' }}>{formatMoney(selectedPayslip.pagibig_deduction).replace('PHP ', '')}</div>
                      </div>
                    </div>
                    <div className="d-flex border-top border-bottom border-dark p-1 fw-bold small">
                      <div className="flex-grow-1">TOTAL MANDATORY GOVT CONT (D)</div>
                      <div className="text-end" style={{ width: '100px' }}>
                        {(
                          (selectedPayslip.sss_deduction || 0) + 
                          (selectedPayslip.philhealth_deduction || 0) + 
                          (selectedPayslip.pagibig_deduction || 0)
                        ).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </div>
                    </div>

                    {/* OTHER DEDUCTIONS */}
                    <div className="bg-dark text-white p-1 fw-bold" style={{ fontSize: '10px' }}>OTHER DEDUCTIONS</div>
                    <div className="p-2" style={{ minHeight: '80px', fontSize: '12px' }}>
                      {selectedPayslip.absence_deduction > 0 && (
                        <div className="d-flex mb-1"><div className="flex-grow-1">ABSENCE DEDUCTION</div><div className="text-end" style={{ width: '100px' }}>{formatMoney(selectedPayslip.absence_deduction).replace('PHP ', '')}</div></div>
                      )}
                      {selectedPayslip.total_loans > 0 && (
                        <div className="d-flex mb-1"><div className="flex-grow-1">TOTAL LOANS REPAYMENT</div><div className="text-end" style={{ width: '100px' }}>{formatMoney(selectedPayslip.total_loans).replace('PHP ', '')}</div></div>
                      )}
                      {selectedPayslip.total_penalties > 0 && (
                        <div className="d-flex mb-1"><div className="flex-grow-1">LATE / UNDERTIME PENALTIES</div><div className="text-end" style={{ width: '100px' }}>{formatMoney(selectedPayslip.total_penalties).replace('PHP ', '')}</div></div>
                      )}
                    </div>
                    <div className="d-flex border-top border-bottom border-dark p-1 fw-bold small">
                      <div className="flex-grow-1">TOTAL OTHER DEDUCTIONS (E)</div>
                      <div className="text-end" style={{ width: '100px' }}>
                        {(
                          (selectedPayslip.absence_deduction || 0) + 
                          (selectedPayslip.total_loans || 0) + 
                          (selectedPayslip.total_penalties || 0)
                        ).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </div>
                    </div>

                    {/* TAXES */}
                    <div className="bg-dark text-white p-1 fw-bold" style={{ fontSize: '10px' }}>TAXES</div>
                    <div className="p-2" style={{ minHeight: '40px', fontSize: '12px' }}>
                      <div className="d-flex mb-1">
                        <div className="flex-grow-1">WITHHOLDING TAX</div>
                        <div className="text-end" style={{ width: '100px' }}>{formatMoney(selectedPayslip.withholding_tax).replace('PHP ', '')}</div>
                      </div>
                    </div>
                    <div className="d-flex border-top border-bottom border-dark p-1 fw-bold small">
                      <div className="flex-grow-1">TOTAL TAXES (F)</div>
                      <div className="text-end" style={{ width: '100px' }}>
                        {selectedPayslip.withholding_tax.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </div>
                    </div>

                    <div className="d-flex p-1 fw-bold small border-top border-dark bg-light">
                      <div className="flex-grow-1">TOTAL DEDUCTIONS (H) (D+E+F)</div>
                      <div className="text-end" style={{ width: '100px' }}>
                        {(
                          (selectedPayslip.total_deductions || 0) + 
                          (selectedPayslip.total_penalties || 0)
                        ).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </div>
                    </div>
                  </Col>
                </Row>

                {/* NET TAKE HOME PAY BANNER */}
                <div className="d-flex align-items-center justify-content-between p-2 border-top border-dark" style={{ backgroundColor: '#00F5D4', color: '#000', breakAfter: 'page' }}>
                  <div className="fw-bold" style={{ letterSpacing: '2px' }}>NET EARNINGS (G-H)</div>
                  <h3 className="mb-0 fw-bold">{formatMoney(selectedPayslip.net_pay)}</h3>
                </div>
              </div>

              {/* CSS for print-only optimization */}
              <style>
                {`
                  @media print {
                    @page {
                      size: A4;
                      margin: 10mm;
                    }
                    body {
                      visibility: hidden;
                      margin: 0 !important;
                      padding: 0 !important;
                    }
                    #printable-payslip, #printable-payslip * {
                      visibility: visible;
                    }
                    #printable-payslip {
                      position: absolute;
                      left: 0;
                      top: 0;
                      width: 100%;
                      padding: 0 !important;
                      margin: 0 !important;
                      background-color: white !important;
                      -webkit-print-color-adjust: exact !important;
                      print-color-adjust: exact !important;
                    }
                    /* Ensure no extra pages from modal backdrop or headers */
                    .modal-header, .modal-footer, .navbar, .sidebar, .btn, .d-print-none, .modal-backdrop {
                      display: none !important;
                    }
                    .page-break {
                      break-after: page;
                      page-break-after: always;
                    }
                  }
                `}
              </style>

              {/* --- RECURRING DEDUCTION DETAILS --- */}
              <div className="mb-4">
                <Row className="g-0 border border-dark">
                  <Col md={6} className="border-end border-dark">
                    <div className="bg-dark text-white p-1 text-center fw-bold" style={{ fontSize: '10px' }}>RECURRING DEDUCTION DETAILS (GOVERNMENT LOANS)</div>
                    <Table bordered size="sm" className="mb-0 border-0" style={{ fontSize: '9px' }}>
                      <thead className="bg-light">
                        <tr>
                          <th>Govt Loan</th>
                          <th>Loan Date</th>
                          <th>Loan Amount</th>
                          <th>Amount Paid</th>
                          <th>Balance</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td>SSS Loan</td>
                          <td>---</td>
                          <td>---</td>
                          <td className="fw-bold">₱{Number(selectedPayslip.sss_loan || 0).toLocaleString()}</td>
                          <td>---</td>
                        </tr>
                        <tr>
                          <td>Pag-IBIG Loan</td>
                          <td>---</td>
                          <td>---</td>
                          <td className="fw-bold">₱{Number(selectedPayslip.pagibig_loan || 0).toLocaleString()}</td>
                          <td>---</td>
                        </tr>
                      </tbody>
                    </Table>
                  </Col>
                  <Col md={6}>
                    <div className="bg-dark text-white p-1 text-center fw-bold" style={{ fontSize: '10px' }}>RECURRING DEDUCTION DETAILS (COMPANY PAYABLES)</div>
                    <Table bordered size="sm" className="mb-0 border-0" style={{ fontSize: '9px' }}>
                      <thead className="bg-light">
                        <tr>
                          <th>Company</th>
                          <th>Advances/Loans</th>
                          <th>Loan Date</th>
                          <th>Amount Paid</th>
                          <th>Balance</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td>SIA System</td>
                          <td>Company Loan</td>
                          <td>---</td>
                          <td className="fw-bold">₱{Number(selectedPayslip.company_loan || 0).toLocaleString()}</td>
                          <td>---</td>
                        </tr>
                      </tbody>
                    </Table>
                  </Col>
                </Row>
              </div>

              {/* --- SUPPLEMENTARY DETAILS --- */}
              <div className="row g-4 mt-2">
                <Col md={6}>
                   <h6 className="fw-bold small border-bottom border-dark pb-1 mb-2 text-uppercase">Supplementary Details (Time & Adjustments)</h6>
                   <div style={{ fontSize: '11px' }}>
                      {selectedPayslip.retro_items?.length > 0 && (
                        <div className="mb-2">
                          <strong>Retroactive Adjustments:</strong>
                          {selectedPayslip.retro_items.map((item, idx) => (
                            <div key={idx} className="ps-2">• ₱{Number(item.amount).toLocaleString()}: {item.reason}</div>
                          ))}
                        </div>
                      )}
                      {selectedPayslip.worked_holiday_items?.length > 0 && (
                        <div className="mb-2">
                          <strong>Holidays Worked:</strong>
                          {selectedPayslip.worked_holiday_items.map((item, idx) => (
                            <div key={idx} className="ps-2">• {item.name} ({item.type}) - {formatDateLabel(item.date)}</div>
                          ))}
                        </div>
                      )}
                      {selectedPayslip.late_penalty_items?.length > 0 && (
                        <div>
                          <strong>Late Incidents ({selectedPayslip.total_late_hours.toFixed(2)}h total):</strong>
                          {selectedPayslip.late_penalty_items.map((item, idx) => (
                            <div key={idx} className="ps-2">• {formatDateLabel(item.date)}: {item.late_time} ({Number(item.late_hours || 0).toFixed(2)}h)</div>
                          ))}
                        </div>
                      )}
                      {(!selectedPayslip.worked_holiday_items?.length && !selectedPayslip.late_penalty_items?.length) && (
                        <div className="text-muted italic">No special time-based adjustments this period.</div>
                      )}
                   </div>
                </Col>
                <Col md={6}>
                  <h6 className="fw-bold small border-bottom border-dark pb-1 mb-2 text-uppercase">Attendance Summary</h6>
                  <Table bordered size="sm" className="text-center border-dark mb-4" style={{ fontSize: '11px' }}>
                    <thead className="bg-light">
                      <tr>
                        <th>Days Worked</th>
                        <th>Present</th>
                        <th>Absent</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td className="fw-bold">{selectedPayslip.days_worked}</td>
                        <td className="fw-bold text-success">{selectedPayslip.days_present}</td>
                        <td className="fw-bold text-danger">{selectedPayslip.days_absent}</td>
                      </tr>
                    </tbody>
                  </Table>

                  <h6 className="fw-bold small border-bottom border-dark pb-1 mb-2 text-uppercase">Year-To-Date Payroll Data</h6>
                  {selectedPayslip.ytd_data ? (
                    <Table bordered size="sm" className="border-dark" style={{ fontSize: '11px' }}>
                      <tbody>
                        <tr>
                          <td className="bg-light fw-bold" style={{ width: '40%' }}>YTD Taxable Income</td>
                          <td className="text-end fw-bold">₱{Number(selectedPayslip.ytd_data.ytd_taxable_income || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                          <td className="bg-light fw-bold" style={{ width: '40%' }}>YTD SSS Contri.</td>
                          <td className="text-end fw-bold">₱{Number(selectedPayslip.ytd_data.ytd_sss_contribution || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                        </tr>
                        <tr>
                          <td className="bg-light fw-bold">YTD Non-Taxable</td>
                          <td className="text-end fw-bold">₱{Number(selectedPayslip.ytd_data.ytd_non_taxable_income || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                          <td className="bg-light fw-bold">YTD PHI Contri.</td>
                          <td className="text-end fw-bold">₱{Number(selectedPayslip.ytd_data.ytd_phi_contribution || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                        </tr>
                        <tr>
                          <td className="bg-light fw-bold">YTD Total Earnings</td>
                          <td className="text-end fw-bold">₱{Number((selectedPayslip.ytd_data.ytd_taxable_income || 0) + (selectedPayslip.ytd_data.ytd_non_taxable_income || 0)).toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                          <td className="bg-light fw-bold">YTD HDMF Contri.</td>
                          <td className="text-end fw-bold">₱{Number(selectedPayslip.ytd_data.ytd_hdmf_contribution || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                        </tr>
                        <tr>
                          <td colSpan={2}></td>
                          <td className="bg-light fw-bold">YTD Wtax</td>
                          <td className="text-end fw-bold">₱{Number(selectedPayslip.ytd_data.ytd_wtax || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                        </tr>
                      </tbody>
                    </Table>
                  ) : (
                    <div className="text-muted small italic">YTD data not available for this legacy record.</div>
                  )}
                </Col>
              </div>

              <div className="mt-5 text-center text-muted" style={{ fontSize: '10px' }}>
                <p className="mb-1">This is a system-generated electronic payslip for SIA Payroll System. No signature is required.</p>
                <p>Generated on: {new Date(selectedPayslip.processed_at).toLocaleString()}</p>
              </div>
            </div>
          )}
        </Modal.Body>
        <Modal.Footer className="border-0 bg-light d-print-none">
          <Button
            variant="dark"
            className="rounded-pill px-5"
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
            <Download size={18} className="me-2" /> Print Electronic Payslip
          </Button>
          <Button variant="outline-secondary" className="rounded-pill px-4" onClick={() => setShowPayslipModal(false)}>
            Close
          </Button>
        </Modal.Footer>
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

      {/* --- RETROACTIVE ADJUSTMENT MODAL --- */}
      <Modal show={showRetroModal} onHide={() => {
        setShowRetroModal(false);
        setEmployeeAdjustments([]);
        setShowHistory(false);
      }} centered>
        <Modal.Header closeButton className="border-0">
          <Modal.Title className="fw-bold" style={{ color: '#5A4343' }}>
            Retroactive Adjustment
          </Modal.Title>
        </Modal.Header>
        <Modal.Body className="px-4 pb-4">
          <div className="mb-4">
            <p className="text-muted small mb-3">
              Add a one-time adjustment for <strong>{retroEmployee?.full_name}</strong>. 
              This will be added to the next payroll run.
            </p>
            <Form>
              <Row>
                <Col md={4}>
                  <Form.Group className="mb-3">
                    <Form.Label className="small fw-bold">Amount (PHP)</Form.Label>
                    <Form.Control 
                      type="number" 
                      placeholder="e.g. 1500" 
                      value={retroData.amount}
                      onChange={(e) => setRetroData({...retroData, amount: e.target.value})}
                    />
                  </Form.Group>
                </Col>
                <Col md={8}>
                  <Form.Group className="mb-3">
                    <Form.Label className="small fw-bold">Reason / Description</Form.Label>
                    <Form.Control 
                      type="text" 
                      placeholder="e.g. Overtime backpay" 
                      value={retroData.reason}
                      onChange={(e) => setRetroData({...retroData, reason: e.target.value})}
                    />
                  </Form.Group>
                </Col>
              </Row>
              <div className="text-end">
                <Button 
                  size="sm"
                  className="rounded-pill px-4" 
                  style={{ backgroundColor: '#D29191', border: 'none' }}
                  onClick={handleAddRetro}
                  disabled={!retroData.amount}
                >
                  Add Adjustment
                </Button>
              </div>
            </Form>
          </div>

          <hr className="my-4" />

          <div className="d-flex justify-content-between align-items-center mb-3">
            <h6 className="fw-bold small mb-0 text-uppercase" style={{ letterSpacing: '1px' }}>Adjustment List</h6>
            <Form.Check 
              type="switch"
              id="show-history-switch"
              label={<span className="small text-muted">Show Processed History</span>}
              checked={showHistory}
              onChange={(e) => setShowHistory(e.target.checked)}
            />
          </div>
          {adjustmentsLoading ? <div className="text-center py-3"><Spinner size="sm" /></div> : (
            <div className="table-responsive" style={{ maxHeight: '250px' }}>
              <Table bordered hover size="sm" style={{ fontSize: '11px' }}>
                <thead className="bg-light">
                  <tr>
                    <th>Date</th>
                    <th>Reason</th>
                    <th>Amount</th>
                    <th>Status</th>
                    <th className="text-center">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {employeeAdjustments.filter(a => showHistory || !a.is_applied).length === 0 ? (
                    <tr><td colSpan="5" className="text-center text-muted py-3">No pending adjustments found.</td></tr>
                  ) : employeeAdjustments.filter(a => showHistory || !a.is_applied).map((adj) => (
                    <tr key={adj._id}>
                      <td>{new Date(adj.created_at).toLocaleDateString()}</td>
                      <td>{adj.reason}</td>
                      <td className={`fw-bold ${adj.amount >= 0 ? 'text-success' : 'text-danger'}`}>
                        ₱{Number(adj.amount).toLocaleString()}
                      </td>
                      <td>
                        <Badge bg={adj.is_applied ? 'success-subtle' : 'warning-subtle'} className={adj.is_applied ? 'text-success border border-success' : 'text-warning border border-warning'}>
                          {adj.is_applied ? 'PROCESSED' : 'PENDING'}
                        </Badge>
                      </td>
                      <td className="text-center">
                        {!adj.is_applied && (
                          <Button 
                            variant="link" 
                            className="p-0 text-danger" 
                            onClick={() => handleDeleteAdjustment(adj._id)}
                          >
                            <Trash2 size={14} />
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>
          )}
        </Modal.Body>
        <Modal.Footer className="border-0 bg-light">
          <Button variant="outline-secondary" className="rounded-pill px-4" onClick={() => setShowRetroModal(false)}>Cancel</Button>
          <Button 
            className="rounded-pill px-4" 
            style={{ backgroundColor: '#D29191', border: 'none' }}
            onClick={handleAddRetro}
            disabled={!retroData.amount}
          >
            Save Adjustment
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
};

export default Payroll;
