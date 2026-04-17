import React, { useEffect, useState } from 'react';
import { Card, Form, Button, Row, Col, Spinner, Alert } from 'react-bootstrap';
import TopBar from '../components/layout/TopBar';
import axios from 'axios';
import { Calendar, Database, RefreshCw } from 'lucide-react';

const Settings = () => {
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState(null);
  const [hrSyncing, setHrSyncing] = useState(false);
  const [savingHrConfig, setSavingHrConfig] = useState(false);
  const [hrSyncStatus, setHrSyncStatus] = useState(null);
  const [hrSyncError, setHrSyncError] = useState(null);
  const [autoSyncEnabled, setAutoSyncEnabled] = useState(false);
  const [autoSyncInterval, setAutoSyncInterval] = useState(15);

  const fetchHrSyncStatus = async () => {
    try {
      const response = await axios.get('http://localhost:8000/payroll/sync/hr/status');
      setHrSyncStatus(response.data);
      setAutoSyncEnabled(Boolean(response.data.auto_sync_enabled));
      setAutoSyncInterval(response.data.interval_minutes || 15);
      setHrSyncError(null);
    } catch (err) {
      setHrSyncError('Failed to load HR sync status.');
    }
  };

  useEffect(() => {
    fetchHrSyncStatus();
  }, []);

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

  const handleManualHrSync = async () => {
    try {
      setHrSyncing(true);
      setHrSyncError(null);
      await axios.post('http://localhost:8000/payroll/sync/hr/run');
      await fetchHrSyncStatus();
      setHrSyncing(false);
    } catch (err) {
      setHrSyncError('Failed to run HR sync.');
      setHrSyncing(false);
    }
  };

  const handleSaveHrSyncConfig = async () => {
    try {
      setSavingHrConfig(true);
      setHrSyncError(null);
      await axios.post('http://localhost:8000/payroll/sync/hr/config', {
        auto_sync_enabled: autoSyncEnabled,
        interval_minutes: Number(autoSyncInterval) || 15,
      });
      await fetchHrSyncStatus();
      setSavingHrConfig(false);
    } catch (err) {
      setHrSyncError('Failed to update HR sync settings.');
      setSavingHrConfig(false);
    }
  };

  return (
    <div className="main-content-sia">
      <TopBar title="Settings" />

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

      <Card className="border-0 shadow-sm rounded-4 p-4 mt-4">
        <Card.Body>
          <div className="d-flex align-items-center gap-3 mb-4">
            <div
              className="rounded-3 d-flex align-items-center justify-content-center"
              style={{ width: '40px', height: '40px', backgroundColor: '#4B8B8B', color: 'white' }}
            >
              <Database size={24} />
            </div>
            <h5 className="fw-bold m-0" style={{ color: '#5A4343' }}>HR Data Sync</h5>
          </div>

          <p className="text-muted mb-4" style={{ fontSize: '14px' }}>
            Mirror read-only HR data into the payroll database so payroll processing can run against synced collections instead of the live HR database.
          </p>

          {hrSyncError && (
            <Alert variant="danger" className="rounded-4 mb-4 border-0 shadow-sm">
              {hrSyncError}
            </Alert>
          )}

          {hrSyncStatus && (
            <div className="bg-light p-4 rounded-4 mb-4">
              <Row className="g-3">
                <Col md={3}>
                  <small className="text-muted d-block">Status</small>
                  <span className="fw-bold text-capitalize">{hrSyncStatus.status || 'Unknown'}</span>
                </Col>
                <Col md={3}>
                  <small className="text-muted d-block">Mode</small>
                  <span className="fw-bold text-capitalize">{hrSyncStatus.mode || 'N/A'}</span>
                </Col>
                <Col md={3}>
                  <small className="text-muted d-block">Auto Sync</small>
                  <span className="fw-bold">{hrSyncStatus.auto_sync_enabled ? 'Enabled' : 'Disabled'}</span>
                </Col>
                <Col md={3}>
                  <small className="text-muted d-block">Last Completed</small>
                  <span className="fw-bold">
                    {hrSyncStatus.completed_at ? new Date(hrSyncStatus.completed_at).toLocaleString() : 'Never'}
                  </span>
                </Col>
              </Row>
            </div>
          )}

          <div className="bg-light p-4 rounded-4 mb-4">
            <Row className="g-3 align-items-end">
              <Col md={6}>
                <Form.Group>
                  <Form.Label className="fw-semibold">Automatic HR Sync</Form.Label>
                  <Form.Check
                    type="switch"
                    id="auto-sync-hr"
                    label={autoSyncEnabled ? 'Enabled' : 'Disabled'}
                    checked={autoSyncEnabled}
                    onChange={(e) => setAutoSyncEnabled(e.target.checked)}
                  />
                </Form.Group>
              </Col>
              <Col md={3}>
                <Form.Group>
                  <Form.Label className="fw-semibold">Interval (Minutes)</Form.Label>
                  <Form.Control
                    type="number"
                    min="1"
                    value={autoSyncInterval}
                    onChange={(e) => setAutoSyncInterval(e.target.value)}
                    disabled={!autoSyncEnabled}
                  />
                </Form.Group>
              </Col>
              <Col md={3} className="text-md-end">
                <Button
                  className="rounded-pill px-4 border-0 shadow-sm"
                  style={{ backgroundColor: '#4B8B8B', fontWeight: '600' }}
                  onClick={handleSaveHrSyncConfig}
                  disabled={savingHrConfig}
                >
                  {savingHrConfig ? 'Saving...' : 'Save Auto Sync'}
                </Button>
              </Col>
            </Row>
          </div>

          {hrSyncStatus?.results?.length > 0 && (
            <div className="bg-white border rounded-4 p-3 mb-4">
              {hrSyncStatus.results.map((result) => (
                <div key={result.target} className="d-flex justify-content-between align-items-center py-2 border-bottom">
                  <div>
                    <div className="fw-bold text-capitalize">{result.target.replaceAll('_', ' ')}</div>
                    <small className="text-muted">{result.target_collection}</small>
                  </div>
                  <div className="text-end">
                    <small className="d-block text-muted">
                      Inserted {result.inserted} | Updated {result.updated} | Unchanged {result.unchanged}
                      {result.archived > 0 && ` | Archived ${result.archived}`}
                      {result.recovered > 0 && ` | Recovered ${result.recovered}`}
                    </small>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="d-flex justify-content-between align-items-center">
            <div>
              <h6 className="fw-bold mb-1">Manual HR Sync</h6>
              <small className="text-muted">Targets employees, payroll configurations, attendance, leaves, overtime requests, and undertime records.</small>
            </div>
            <div className="d-flex gap-2">
              <Button
                variant="outline-secondary"
                className="rounded-pill px-4"
                onClick={fetchHrSyncStatus}
                disabled={hrSyncing}
              >
                Refresh Status
              </Button>
              <Button
                className="rounded-pill px-5 border-0 shadow-sm d-flex align-items-center gap-2"
                style={{ backgroundColor: '#4B8B8B', fontWeight: '600', height: '45px' }}
                onClick={handleManualHrSync}
                disabled={hrSyncing}
              >
                {hrSyncing ? (
                  <><Spinner size="sm" animation="border" /> Syncing...</>
                ) : (
                  <><RefreshCw size={18} /> Run HR Sync</>
                )}
              </Button>
            </div>
          </div>
        </Card.Body>
      </Card>
    </div>
  );
};

export default Settings;
