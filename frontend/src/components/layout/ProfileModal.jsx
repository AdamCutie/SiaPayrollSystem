import React, { useState, useEffect } from 'react';
import { Modal, Row, Col, Card, Badge, ListGroup, Spinner, Form } from 'react-bootstrap';
import { User, Mail, Briefcase, Calendar, MapPin, Phone, ShieldCheck, DollarSign, X, LogOut } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import ImageUpload from '../common/ImageUpload';
import api from '../../api/auth';

const ProfileModal = () => {
  const { user, isProfileOpen, setIsProfileOpen, logout } = useAuth();
  const [profileData, setProfileData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedMonth, setSelectedMonth] = useState((new Date().getMonth() + 1).toString());
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear().toString());

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        setLoading(true);
        const response = await api.get(`/employees/profile/${user.employee_id}`);
        setProfileData(response.data);
      } catch (err) {
        console.error("Error fetching profile:", err);
        setError("Failed to load profile data.");
      } finally {
        setLoading(false);
      }
    };

    if (isProfileOpen && user?.employee_id) {
      fetchProfile();
    }
  }, [isProfileOpen, user]);

  const handleClose = () => setIsProfileOpen(false);

  const handleUploadSuccess = (newUrl, newOffset) => {
    setProfileData(prev => ({
      ...prev,
      profile_picture_url: newUrl,
      profile_picture_offset_y: newOffset
    }));
  };

  return (
    <Modal 
      show={isProfileOpen} 
      onHide={handleClose} 
      size="xl" 
      centered 
      contentClassName="border-0 shadow-lg rounded-5"
    >
      <Modal.Body className="p-0 position-relative">
        <button 
          onClick={handleClose}
          className="btn border-0 position-absolute top-0 end-0 m-3 z-3 text-white-50 hover-white"
          style={{ transition: '0.3s' }}
        >
          <X size={24} />
        </button>

        {loading ? (
          <div className="p-5 text-center">
            <Spinner animation="border" variant="primary" />
            <p className="mt-2 text-muted">Fetching your profile...</p>
          </div>
        ) : error ? (
          <div className="p-5 text-center text-danger">{error}</div>
        ) : profileData ? (
          <Row className="g-0">
            {/* Left Sidebar: Profile Identity */}
            <Col lg={4}>
              <div 
                className="h-100 p-5 text-center d-flex flex-column align-items-center justify-content-center" 
                style={{ background: 'linear-gradient(180deg, #A8867F 0%, #D4B2A7 100%)', borderRadius: '30px 0 0 30px' }}
              >
                <ImageUpload 
                  currentImageUrl={profileData.profile_picture_url} 
                  initialOffsetY={profileData.profile_picture_offset_y}
                  onUploadSuccess={handleUploadSuccess}
                />
                
                <h3 className="text-white fw-bold mb-1 mt-4">{profileData.identity.firstName} {profileData.identity.lastName}</h3>
                <p className="text-white-50 mb-3">{profileData.identity.position}</p>
                <Badge bg="white" text="dark" className="rounded-pill px-4 py-2 shadow-sm">
                  {profileData.identity.contractType}
                </Badge>

                <div className="mt-5 w-100 text-start px-3">
                  <div className="d-flex align-items-center mb-3 text-white">
                    <Mail size={18} className="me-3 opacity-75" />
                    <span className="small">{profileData.identity.email}</span>
                  </div>
                  <div className="d-flex align-items-center mb-3 text-white">
                    <Phone size={18} className="me-3 opacity-75" />
                    <span className="small">{profileData.identity.contactNo}</span>
                  </div>
                  <div className="d-flex align-items-center text-white mb-4">
                    <MapPin size={18} className="me-3 opacity-75" />
                    <span className="small">{profileData.identity.address}</span>
                  </div>

                  <button 
                    onClick={logout}
                    className="btn btn-outline-light w-100 rounded-pill d-flex align-items-center justify-content-center gap-2 py-2 mt-4"
                    style={{ borderWidth: '1.5px', fontSize: '14px', fontWeight: '500' }}
                  >
                    <LogOut size={16} /> Logout
                  </button>
                </div>
              </div>
            </Col>

            {/* Right Content: Details & History */}
            <Col lg={8}>
              <div className="p-4 p-md-5">
                <h5 className="fw-bold mb-4">Employment Details</h5>
                <Row className="g-4 mb-5">
                  <Col md={6}>
                    <div className="p-3 bg-light rounded-4 border">
                      <div className="d-flex align-items-center mb-1">
                        <Briefcase size={16} className="me-2 text-muted" />
                        <span className="text-muted small text-uppercase fw-bold">Department</span>
                      </div>
                      <div className="fw-bold">{profileData.identity.department}</div>
                    </div>
                  </Col>
                  <Col md={6}>
                    <div className="p-3 bg-light rounded-4 border">
                      <div className="d-flex align-items-center mb-1">
                        <Calendar size={16} className="me-2 text-muted" />
                        <span className="text-muted small text-uppercase fw-bold">Joined Date</span>
                      </div>
                      <div className="fw-bold">{new Date(profileData.identity.hiredDate).toLocaleDateString()}</div>
                    </div>
                  </Col>
                  <Col md={6}>
                    <div className="p-3 bg-light rounded-4 border">
                      <div className="d-flex align-items-center mb-1">
                        <DollarSign size={16} className="me-2 text-muted" />
                        <span className="text-muted small text-uppercase fw-bold">Base Salary</span>
                      </div>
                      <div className="fw-bold text-success">PHP {profileData.identity.baseSalary?.toLocaleString()}</div>
                    </div>
                  </Col>
                  <Col md={6}>
                    <div className="p-3 bg-light rounded-4 border">
                      <div className="d-flex align-items-center mb-1">
                        <ShieldCheck size={16} className="me-2 text-muted" />
                        <span className="text-muted small text-uppercase fw-bold">System Role</span>
                      </div>
                      <div className="fw-bold text-capitalize">{user.role}</div>
                    </div>
                  </Col>
                </Row>

                <div className="d-flex justify-content-between align-items-center mb-3">
                  <h5 className="fw-bold mb-0">Recent Payslips</h5>
                  <div className="d-flex gap-2">
                    <div style={{ width: '130px' }}>
                      <Form.Select 
                        size="sm"
                        className="rounded-pill border-0 shadow-sm px-3"
                        style={{ backgroundColor: '#FFF5F5', color: '#D29191', fontWeight: '600', height: '32px' }}
                        value={selectedMonth}
                        onChange={(e) => setSelectedMonth(e.target.value)}
                      >
                        <option value="">Month</option>
                        {['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'].map((m, idx) => (
                          <option key={m} value={idx + 1}>{m}</option>
                        ))}
                      </Form.Select>
                    </div>
                    <div style={{ width: '100px' }}>
                      <Form.Select 
                        size="sm"
                        className="rounded-pill border-0 shadow-sm px-3"
                        style={{ backgroundColor: '#FFF5F5', color: '#D29191', fontWeight: '600', height: '32px' }}
                        value={selectedYear}
                        onChange={(e) => setSelectedYear(e.target.value)}
                      >
                        {[2024, 2025, 2026].map(y => (
                          <option key={y} value={y}>{y}</option>
                        ))}
                      </Form.Select>
                    </div>
                  </div>
                </div>

                <div className="table-responsive rounded-4 border overflow-hidden">
                  <table className="table table-hover align-middle mb-0">
                    <thead className="bg-light">
                      <tr>
                        <th className="ps-4 py-3 small text-uppercase">Period</th>
                        <th className="small text-uppercase">Net Pay</th>
                        <th className="text-center small text-uppercase">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(() => {
                        const filteredHistory = profileData.payroll_history.filter(pay => {
                          const payDate = new Date(pay.pay_period_end);
                          const monthMatch = !selectedMonth || (payDate.getMonth() + 1).toString() === selectedMonth;
                          const yearMatch = !selectedYear || payDate.getFullYear().toString() === selectedYear;
                          return monthMatch && yearMatch;
                        });

                        return filteredHistory.length > 0 ? (
                          filteredHistory.map((pay) => (
                            <tr key={pay.id}>
                              <td className="ps-4 py-3">
                                <div className="small fw-medium">
                                  {new Date(pay.pay_period_start).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} - {new Date(pay.pay_period_end).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                                </div>
                              </td>
                              <td className="fw-bold">₱{pay.net_pay.toLocaleString()}</td>
                              <td className="text-center">
                                <Badge 
                                  bg={pay.status === 'Approved' ? 'success-subtle' : 
                                      pay.status === 'Completed' ? 'success' : 'warning-subtle'} 
                                  className={`rounded-pill px-3 ${pay.status === 'Approved' ? 'text-success' : 
                                              pay.status === 'Completed' ? 'text-white' : 'text-warning'}`}
                                >
                                  {pay.status}
                                </Badge>
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan="3" className="text-center py-4 text-muted small">No history available for this period</td>
                          </tr>
                        );
                      })()}
                    </tbody>
                  </table>
                </div>
              </div>
            </Col>
          </Row>
        ) : null}
      </Modal.Body>
    </Modal>
  );
};

export default ProfileModal;
