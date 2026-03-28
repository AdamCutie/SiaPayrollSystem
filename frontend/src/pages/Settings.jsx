import React, { useState } from 'react';
import { Card, Form, Button, Row, Col, Spinner, Alert } from 'react-bootstrap';
import TopBar from '../components/layout/TopBar';
import axios from 'axios';
import { Calendar, RefreshCw } from 'lucide-react';

const Settings = () => {
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState(null);

  const handleSyncHolidays = async () => {
    try {
      setSyncing(true);
      setSyncResult(null);
      const year = new Date().getFullYear();
      const response = await axios.post(`http://localhost:8000/payroll/holidays/sync?year=${year}`);
      setSyncResult({ type: 'success', message: response.data.message });
      setSyncing(false);
    } catch (err) {
      setSyncResult({ type: 'danger', message: 'Failed to sync holidays. Please try again later.' });
      setSyncing(false);
    }
  };

  return (
    <div className="main-content-sia">
      <TopBar title="Settings" />

      {/* Global Defaults */}
      <Card className="border-0 shadow-sm rounded-4 p-4 mb-4">
        <Card.Body>
          <h5 className="fw-bold mb-4" style={{ color: '#5A4343' }}>Global System Defaults</h5>
          {/* ... existing form content ... */}
          <Form>
            <Row>
              <Col md={4}>
                <Form.Group className="mb-3">
                  <Form.Label>Average Salary</Form.Label>
                  <Form.Control type="number" placeholder="Enter average salary" defaultValue="500" />
                </Form.Group>
              </Col>
              <Col md={4}>
                <Form.Group className="mb-3">
                  <Form.Label>Deduction Per Hour (Late)</Form.Label>
                  <Form.Control type="number" placeholder="Enter deduction for lateness" defaultValue="600" />
                </Form.Group>
              </Col>
              <Col md={4}>
                <Form.Group className="mb-3">
                  <Form.Label>Deduction Per Hour (Absent)</Form.Label>
                  <Form.Control type="number" placeholder="Enter deduction for absence" defaultValue="600" />
                </Form.Group>
              </Col>
            </Row>
            <div className="mt-3 text-end">
              <Button variant="outline-primary" className="rounded-pill px-4" type="submit">
                Save Defaults
              </Button>
            </div>
          </Form>
        </Card.Body>
      </Card>

      {/* Holiday Automation Section */}
      <Card className="border-0 shadow-sm rounded-4 p-4">
        <Card.Body>
          <div className="d-flex align-items-center gap-3 mb-4">
            <div 
              className="rounded-3 d-flex align-items-center justify-content-center" 
              style={{ width: '40px', height: '40px', backgroundColor: '#D29191', color: 'white' }}
            >
              <Calendar size={24} />
            </div>
            <h5 className="fw-bold m-0" style={{ color: '#5A4343' }}>Holiday Automation</h5>
          </div>

          <p className="text-muted mb-4" style={{ fontSize: '14px' }}>
            Automatically sync your payroll calendar with official Philippines public holidays. This ensures that attendance and payroll runs correctly identify holiday pay and excused absences.
          </p>

          {syncResult && (
            <Alert variant={syncResult.type} className="rounded-4 mb-4 border-0 shadow-sm">
              {syncResult.message}
            </Alert>
          )}

          <div className="bg-light p-4 rounded-4 d-flex justify-content-between align-items-center">
            <div>
              <h6 className="fw-bold mb-1">External Holiday API (Nager.Date)</h6>
              <small className="text-muted">Source: Public Holidays Service - PH</small>
            </div>
            <Button 
              className="rounded-pill px-5 border-0 shadow-sm d-flex align-items-center gap-2" 
              style={{ backgroundColor: '#D29191', fontWeight: '600', height: '45px' }}
              onClick={handleSyncHolidays}
              disabled={syncing}
            >
              {syncing ? (
                <><Spinner size="sm" animation="border" /> Syncing...</>
              ) : (
                <><RefreshCw size={18} /> Sync 2026 PH Holidays</>
              )}
            </Button>
          </div>
        </Card.Body>
      </Card>
    </div>
  );
};

export default Settings;
