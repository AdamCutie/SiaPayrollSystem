import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { User, Lock, AlertCircle } from 'lucide-react';
import sheEssentialsLogo from '../assets/sheessentials-logo.jpg';

const Login = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await login(username, password);
      navigate('/dashboard');
    } catch (err) {
      console.error('Login error:', err);
      setError('Invalid username or password. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-page-sia d-flex align-items-center justify-content-center p-3" style={{ 
      minHeight: '100vh', 
      backgroundColor: '#F0F2F5',
      background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)'
    }}>
      <div className="login-card-sia shadow-lg w-100" style={{ 
        maxWidth: '450px', 
        borderRadius: '30px', 
        overflow: 'hidden', 
        backgroundColor: '#fff',
        border: 'none'
      }}>
        
        {/* Header Section with Gradient */}
        <div className="login-header-sia text-center p-4 p-md-5 position-relative" style={{ 
          background: 'linear-gradient(180deg, #A8867F 0%, #D4B2A7 100%)',
          color: 'white',
          paddingBottom: '60px !important'
        }}>
          {/* Polished Elliptical Logo Frame */}
          <div className="logo-frame-sia bg-white d-inline-flex align-items-center justify-content-center mb-3 shadow" style={{ 
            width: '160px', 
            height: '110px', 
            borderRadius: '100px', // Creates the oval/elliptical shape
            padding: '15px',
            border: '4px solid rgba(255,255,255,0.2)'
          }}>
            <img 
              src={sheEssentialsLogo} 
              alt="Sheessentials" 
              className="img-fluid"
              style={{ width: '100%', height: 'auto', objectFit: 'contain' }}
            />
          </div>
          <h2 className="fw-bold mb-1 mt-2" style={{ fontSize: '1.75rem' }}>Welcome Back</h2>
          <p className="mb-0 opacity-75 small text-uppercase fw-bold" style={{ letterSpacing: '1.5px' }}>HR Management System</p>
        </div>

        {/* Form Section */}
        <div className="p-4 p-md-5">
          {error && (
            <div className="alert alert-danger d-flex align-items-center mb-4 py-3" style={{ 
              borderRadius: '16px', 
              backgroundColor: '#FFF1F0', 
              border: '1px solid #FFA39E',
              color: '#CF1322',
              fontSize: '14px'
            }}>
              <AlertCircle size={20} className="me-3 flex-shrink-0" />
              <div className="fw-medium">{error}</div>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="mb-4">
              <label className="form-label fw-bold text-muted small text-uppercase mb-2 ps-1" style={{ letterSpacing: '0.8px', fontSize: '11px' }}>Username</label>
              <div className="input-group">
                <span className="input-group-text bg-light border-0 ps-3 pe-0 text-muted" style={{ borderRadius: '15px 0 0 15px' }}>
                  <User size={20} />
                </span>
                <input 
                  type="text" 
                  className="form-control bg-light border-0 p-3" 
                  placeholder="admin"
                  style={{ borderRadius: '0 15px 15px 0', fontSize: '15px', outline: 'none', boxShadow: 'none' }}
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="mb-4">
              <label className="form-label fw-bold text-muted small text-uppercase mb-2 ps-1" style={{ letterSpacing: '0.8px', fontSize: '11px' }}>Password</label>
              <div className="input-group">
                <span className="input-group-text bg-light border-0 ps-3 pe-0 text-muted" style={{ borderRadius: '15px 0 0 15px' }}>
                  <Lock size={20} />
                </span>
                <input 
                  type="password" 
                  className="form-control bg-light border-0 p-3" 
                  placeholder="Enter your password"
                  style={{ borderRadius: '0 15px 15px 0', fontSize: '15px', outline: 'none', boxShadow: 'none' }}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="d-flex justify-content-between align-items-center mb-4 ps-1">
              <div className="form-check">
                <input className="form-check-input" type="checkbox" id="rememberMe" style={{ borderColor: '#D4B2A7', cursor: 'pointer' }} />
                <label className="form-check-label small text-muted" htmlFor="rememberMe" style={{ cursor: 'pointer' }}>
                  Remember me
                </label>
              </div>
              <a href="#" className="small text-decoration-none fw-bold" style={{ color: '#A8867F', transition: '0.2s' }}>Forgot Password?</a>
            </div>

            <button 
              type="submit" 
              className="btn w-100 py-3 fw-bold text-uppercase mt-2" 
              style={{ 
                backgroundColor: '#A8867F', 
                color: 'white', 
                borderRadius: '15px',
                letterSpacing: '1.5px',
                fontSize: '14px',
                transition: 'all 0.3s ease',
                boxShadow: '0 6px 20px rgba(168, 134, 127, 0.4)',
                border: 'none'
              }}
              disabled={isLoading}
              onMouseOver={(e) => e.currentTarget.style.transform = 'translateY(-2px)'}
              onMouseOut={(e) => e.currentTarget.style.transform = 'translateY(0)'}
            >
              {isLoading ? (
                <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
              ) : 'Login'}
            </button>
          </form>

          <div className="text-center mt-5">
            <p className="text-muted mb-0" style={{ fontSize: '12px', opacity: 0.8 }}>
              © 2026 <span className="fw-bold">Essentials Beauty</span> HR System.
              <br />All rights reserved.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
