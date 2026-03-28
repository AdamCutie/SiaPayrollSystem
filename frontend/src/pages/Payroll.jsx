import React, { useState, useEffect } from 'react';
import { Row, Col, Card, Form, Button, Table, Badge, Spinner, Alert, Modal } from 'react-bootstrap';
import axios from 'axios';
import { Search, ChevronDown, Check, Download, Calendar, ArrowRight, Settings, Users, FileText, Edit, Eye } from 'lucide-react';
import TopBar from '../components/layout/TopBar';

const Payroll = () => {
  const [view, setView] = useState('generation'); // 'generation', 'configuration', 'payslips'
  const [step, setStep] = useState(1); // Start at Step 1
  const [employees, setEmployees] = useState([]);
  const [readinessSummary, setReadinessSummary] = useState({ ready_count: 0, incomplete_count: 0 });
  const [selectedIds, setSelectedIds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState(null);
  const [processedCount, setProcessedCount] = useState(0);
  const [dateRange, setDateRange] = useState({ start: '2026-03-01', end: '2026-03-15' });

  // Configuration State
  const [searchQuery, setSearchQuery] = useState('');
  const [editingEmployee, setEditingEmployee] = useState(null);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [configData, setConfigData] = useState({});
  const [isSavingConfig, setIsSavingConfig] = useState(false);

  // Payslips State
  const [payrollHistory, setPayrollHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [payslipSearch, setPayslipSearch] = useState('');
  const [selectedPayslip, setSelectedPayslip] = useState(null);
  const [showPayslipModal, setShowPayslipModal] = useState(false);

  useEffect(() => {
    if (employees.length === 0) {
      fetchEmployees();
    }
  }, []);

  useEffect(() => {
    if (view === 'payslips') {
      fetchHistory();
    }
  }, [view]);

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
      const response = await axios.get('http://localhost:8000/payroll/processing/history');
      setPayrollHistory(response.data);
      setHistoryLoading(false);
    } catch (err) {
      console.error("Failed to fetch history", err);
      setHistoryLoading(false);
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

  // Removed handleSaveConfig and onSalaryChange as they are no longer needed for a read-only view.

  const handleViewPayslip = (record) => {
    setSelectedPayslip(record);
    setShowPayslipModal(true);
  };

  const filteredEmployees = employees.filter(emp => 
    `${emp.firstName} ${emp.lastName}`.toLowerCase().includes(searchQuery.toLowerCase()) ||
    emp.employeeId.includes(searchQuery)
  );

  const filteredHistory = payrollHistory.filter(record => 
    record.full_name.toLowerCase().includes(payslipSearch.toLowerCase()) ||
    record.employee_number.includes(payslipSearch)
  );

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
                        <span className="fw-bold" style={{ fontSize: '14px' }}>{emp.full_name}</span>
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
            <h6 className="fw-bold mb-3 border-bottom pb-2 text-primary">1. Monthly Earnings & Allowances (from HR)</h6>
            <Row className="mb-3">
              <Col md={4}>
                <Form.Group>
                  <Form.Label className="small fw-bold">Basic Salary</Form.Label>
                  <Form.Control 
                    type="number" 
                    value={configData.basicSalary || ''} 
                    readOnly
                    className="bg-light"
                  />
                </Form.Group>
              </Col>
              <Col md={2}>
                <Form.Group>
                  <Form.Label className="small fw-bold">Housing</Form.Label>
                  <Form.Control 
                    type="number" 
                    value={configData.housingAllowance || ''} 
                    readOnly
                    className="bg-light"
                  />
                </Form.Group>
              </Col>
              <Col md={2}>
                <Form.Group>
                  <Form.Label className="small fw-bold">Transport</Form.Label>
                  <Form.Control 
                    type="number" 
                    value={configData.transportAllowance || ''} 
                    readOnly
                    className="bg-light"
                  />
                </Form.Group>
              </Col>
              <Col md={2}>
                <Form.Group>
                  <Form.Label className="small fw-bold">Meal</Form.Label>
                  <Form.Control 
                    type="number" 
                    value={configData.mealAllowance || ''} 
                    readOnly
                    className="bg-light"
                  />
                </Form.Group>
              </Col>
              <Col md={2}>
                <Form.Group>
                  <Form.Label className="small fw-bold">Other</Form.Label>
                  <Form.Control 
                    type="number" 
                    value={configData.otherAllowances || ''} 
                    readOnly
                    className="bg-light"
                  />
                </Form.Group>
              </Col>
            </Row>

            {/* --- SECTION 2: STATUTORY (READ-ONLY) --- */}
            <h6 className="fw-bold mb-3 border-bottom pb-2 d-flex justify-content-between align-items-center mt-4">
              2. Statutory Deductions
              <Badge bg="info-subtle" className="text-info border border-info fw-normal" style={{ fontSize: '10px' }}>Auto-calculated by Law</Badge>
            </h6>
            <Row className="mb-3">
              <Col md={3}>
                <Form.Group>
                  <Form.Label className="small text-muted">SSS Contribution</Form.Label>
                  <Form.Control type="number" value={configData.sssContribution || ''} readOnly className="bg-light text-muted" />
                </Form.Group>
              </Col>
              <Col md={3}>
                <Form.Group>
                  <Form.Label className="small text-muted">PhilHealth</Form.Label>
                  <Form.Control type="number" value={configData.philHealthContribution || ''} readOnly className="bg-light text-muted" />
                </Form.Group>
              </Col>
              <Col md={3}>
                <Form.Group>
                  <Form.Label className="small text-muted">Pag-IBIG</Form.Label>
                  <Form.Control type="number" value={configData.pagIbigContribution || ''} readOnly className="bg-light text-muted" />
                </Form.Group>
              </Col>
              <Col md={3}>
                <Form.Group>
                  <Form.Label className="small text-muted">Withholding Tax</Form.Label>
                  <Form.Control type="number" value={configData.withholdingTax || ''} readOnly className="bg-light text-muted" />
                </Form.Group>
              </Col>
            </Row>

            {/* --- SECTION 3: LOANS & RATES --- */}
            <h6 className="fw-bold mb-3 border-bottom pb-2 mt-4 text-danger">3. Active Loans & Penalty Rates (from HR)</h6>
            <Row className="mb-3">
              <Col md={4}>
                <Form.Group>
                  <Form.Label className="small fw-bold text-danger">SSS Loan</Form.Label>
                  <Form.Control 
                    type="number" 
                    value={configData.sssLoan || ''} 
                    readOnly
                    className="bg-light"
                  />
                </Form.Group>
              </Col>
              <Col md={4}>
                <Form.Group>
                  <Form.Label className="small fw-bold text-danger">Pag-IBIG Loan</Form.Label>
                  <Form.Control 
                    type="number" 
                    value={configData.pagIbigLoan || ''} 
                    readOnly
                    className="bg-light"
                  />
                </Form.Group>
              </Col>
              <Col md={4}>
                <Form.Group>
                  <Form.Label className="small fw-bold text-danger">Company Loan</Form.Label>
                  <Form.Control 
                    type="number" 
                    value={configData.companyLoan || ''} 
                    readOnly
                    className="bg-light"
                  />
                </Form.Group>
              </Col>
            </Row>
            <Row>
              <Col md={6}>
                <Form.Group>
                  <Form.Label className="small fw-bold">Absence Penalty (Per Day)</Form.Label>
                  <Form.Control 
                    type="number" 
                    value={configData.absencePenaltyRate || ''} 
                    readOnly
                    className="bg-light"
                  />
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group>
                  <Form.Label className="small fw-bold">Late Penalty (Per Hour)</Form.Label>
                  <Form.Control 
                    type="number" 
                    value={configData.latePenaltyRate || ''} 
                    readOnly
                    className="bg-light"
                  />
                </Form.Group>
              </Col>
            </Row>
          </Form>
        </Modal.Body>
        <Modal.Footer className="border-0">
          <Button variant="outline-secondary" className="rounded-pill px-5" onClick={() => setShowConfigModal(false)}>
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

      <div className="table-responsive">
        <Table hover className="align-middle">
          <thead>
            <tr className="text-muted" style={{ fontSize: '12px' }}>
              <th>EMPLOYEE</th>
              <th>PERIOD</th>
              <th>NET PAY</th>
              <th>PROCESSED AT</th>
              <th className="text-end">ACTION</th>
            </tr>
          </thead>
          <tbody>
            {historyLoading ? <tr><td colSpan="5" className="text-center py-5"><Spinner /></td></tr> : 
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
                    <span style={{ fontSize: '13px' }}>{new Date(selectedPayslip.pay_period_start).toLocaleDateString()} - {new Date(selectedPayslip.pay_period_end).toLocaleDateString()}</span>
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
                  <span>₱{selectedPayslip.basic_salary.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>
                {selectedPayslip.total_overtime > 0 && (
                  <div className="d-flex justify-content-between mb-1" style={{ fontSize: '13px' }}>
                    <span className="text-muted">Overtime Pay</span>
                    <span>₱{selectedPayslip.total_overtime.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                  </div>
                )}
                {(selectedPayslip.housing_allowance > 0 || selectedPayslip.transport_allowance > 0 || selectedPayslip.meal_allowance > 0 || selectedPayslip.other_allowances > 0) && (
                  <div className="mt-2 pt-2 border-top-dashed">
                    <small className="text-muted d-block mb-1" style={{ fontSize: '11px' }}>Allowances</small>
                    {selectedPayslip.housing_allowance > 0 && (
                      <div className="d-flex justify-content-between mb-1" style={{ fontSize: '12px' }}>
                        <span className="ps-2">• Housing</span>
                        <span>₱{selectedPayslip.housing_allowance.toLocaleString()}</span>
                      </div>
                    )}
                    {selectedPayslip.transport_allowance > 0 && (
                      <div className="d-flex justify-content-between mb-1" style={{ fontSize: '12px' }}>
                        <span className="ps-2">• Transport</span>
                        <span>₱{selectedPayslip.transport_allowance.toLocaleString()}</span>
                      </div>
                    )}
                    {selectedPayslip.meal_allowance > 0 && (
                      <div className="d-flex justify-content-between mb-1" style={{ fontSize: '12px' }}>
                        <span className="ps-2">• Meal</span>
                        <span>₱{selectedPayslip.meal_allowance.toLocaleString()}</span>
                      </div>
                    )}
                  </div>
                )}
                <div className="d-flex justify-content-between mt-2 pt-2 border-top text-success fw-bold">
                  <span>Gross Pay</span>
                  <span>₱{selectedPayslip.gross_pay.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>
              </div>

              <div className="mb-4">
                <h6 className="fw-bold mb-3 border-bottom pb-2" style={{ fontSize: '14px' }}>DEDUCTIONS</h6>
                <div className="d-flex justify-content-between mb-1" style={{ fontSize: '13px' }}>
                  <span className="text-muted">SSS Contribution</span>
                  <span>-₱{selectedPayslip.sss_deduction.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>
                <div className="d-flex justify-content-between mb-1" style={{ fontSize: '13px' }}>
                  <span className="text-muted">PhilHealth</span>
                  <span>-₱{selectedPayslip.philhealth_deduction.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>
                <div className="d-flex justify-content-between mb-1" style={{ fontSize: '13px' }}>
                  <span className="text-muted">Pag-IBIG</span>
                  <span>-₱{selectedPayslip.pagibig_deduction.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>
                <div className="d-flex justify-content-between mb-1" style={{ fontSize: '13px' }}>
                  <span className="text-muted">Withholding Tax</span>
                  <span>-₱{selectedPayslip.withholding_tax.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>
                {selectedPayslip.absence_deduction > 0 && (
                  <div className="d-flex justify-content-between mb-1" style={{ fontSize: '13px' }}>
                    <span className="text-muted text-danger">Absence Deduction</span>
                    <span className="text-danger">-₱{selectedPayslip.absence_deduction.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                  </div>
                )}
                
                {selectedPayslip.total_loans > 0 && (
                  <div className="d-flex justify-content-between mb-1" style={{ fontSize: '13px' }}>
                    <span className="text-muted">Loans</span>
                    <span>-₱{selectedPayslip.total_loans.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                  </div>
                )}
                
                {selectedPayslip.total_penalties > 0 && (
                  <div className="d-flex justify-content-between mb-1" style={{ fontSize: '13px' }}>
                    <span className="text-muted text-danger">Penalties (Absence/Late)</span>
                    <span className="text-danger">-₱{selectedPayslip.total_penalties.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                  </div>
                )}

                <div className="d-flex justify-content-between mt-2 pt-2 border-top text-danger fw-bold">
                  <span>Total Deductions</span>
                  <span>-₱{selectedPayslip.total_deductions.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
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
                <h4 className="mb-0 fw-bold">₱{selectedPayslip.net_pay.toLocaleString(undefined, { minimumFractionDigits: 2 })}</h4>
              </div>
              
              <div className="mt-4 text-center">
                <small className="text-muted" style={{ fontSize: '10px' }}>
                  This is a computer-generated document. No signature is required.
                  <br />Generated on {new Date(selectedPayslip.processed_at).toLocaleString()}
                </small>
              </div>
            </div>
          )}
          <div className="mt-5 text-center d-print-none">
            <Button variant="outline-secondary" className="rounded-pill px-4 me-2" onClick={() => window.print()}>
              <Download size={18} className="me-2" /> Print PDF
            </Button>
          </div>
        </Modal.Body>
      </Modal>
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
        <Button 
          className="rounded-pill px-5 border-0 shadow-sm d-flex align-items-center gap-2" 
          style={{ 
            backgroundColor: view === 'generation' ? '#D29191' : '#FFFFFF', 
            color: view === 'generation' ? 'white' : '#A08E8E',
            height: '50px', 
            fontWeight: '600' 
          }}
          onClick={() => setView('generation')}
        >
          <Users size={18} />
          Payroll Generation
        </Button>
        <Button 
          className="rounded-pill px-5 border-0 shadow-sm d-flex align-items-center gap-2" 
          style={{ 
            backgroundColor: view === 'configuration' ? '#D29191' : '#FFFFFF', 
            color: view === 'configuration' ? 'white' : '#A08E8E',
            height: '50px', 
            fontWeight: '600' 
          }}
          onClick={() => setView('configuration')}
        >
          <Settings size={18} />
          Payroll Configuration
        </Button>
        <Button 
          className="rounded-pill px-5 border-0 shadow-sm d-flex align-items-center gap-2" 
          style={{ 
            backgroundColor: view === 'payslips' ? '#D29191' : '#FFFFFF', 
            color: view === 'payslips' ? 'white' : '#A08E8E',
            height: '50px', 
            fontWeight: '600' 
          }}
          onClick={() => setView('payslips')}
        >
          <FileText size={18} />
          Payslips
        </Button>
      </div>

      {view === 'generation' && <WizardProgress />}

      <Card className="border-0 shadow-sm rounded-4 p-4">
        <Card.Body>
          {view === 'generation' ? renderGenerationContent() : 
           view === 'configuration' ? renderConfigurationContent() : 
           renderPayslipsContent()}
        </Card.Body>
        {view === 'generation' && step < 4 && (
          <div className="d-flex justify-content-end gap-3 mt-5">
            <Button variant="outline-secondary" className="rounded-pill px-5 border-0" style={{ fontWeight: '600' }} onClick={() => setStep(prev => Math.max(1, prev - 1))} disabled={step === 1 || isProcessing}>
              Back
            </Button>
            <Button className="rounded-pill px-5 border-0 shadow-sm" style={{ backgroundColor: '#D29191', fontWeight: '600' }} onClick={step === 3 ? handleRunPayroll : () => setStep(prev => Math.min(4, prev + 1))} disabled={isProcessing}>
              {isProcessing ? <Spinner as="span" animation="border" size="sm" role="status" aria-hidden="true" /> : (step === 3 ? 'Run Payroll' : 'Next Step')}
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
};

export default Payroll;
