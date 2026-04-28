import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { User, Lock, AlertCircle, Eye, EyeOff, CheckCircle2 } from 'lucide-react';
import sheEssentialsLogo from '../assets/sheessentials-logo.jpg';

const Login = () => {
  const [username, setUsername] = useState(localStorage.getItem('rememberedUsername') || '');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(!!localStorage.getItem('rememberedUsername'));
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isLoaded, setIsLoaded] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    setIsLoaded(true);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await login(username, password);
      
      if (rememberMe) {
        localStorage.setItem('rememberedUsername', username);
      } else {
        localStorage.removeItem('rememberedUsername');
      }
      
      navigate('/dashboard');
    } catch (err) {
      console.error('Login error:', err);
      setError('Invalid username or password. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleForgotPassword = (e) => {
    e.preventDefault();
    alert('Please contact your HR administrator to reset your password.');
  };

  return (
    <div className="login-page-sia d-flex align-items-center justify-content-center p-3" style={{ 
      minHeight: '100vh', 
      backgroundColor: '#F0F2F5',
      background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%), url("https://www.transparenttextures.com/patterns/cubes.png")',
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    }}>
      <style>
        {`
          @keyframes fadeInDown {
            from { opacity: 0; transform: translateY(-20px); }
            to { opacity: 1; transform: translateY(0); }
          }
          @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
          }
          .animate-fade-in-down {
            animation: fadeInDown 0.8s ease-out;
          }
          .animate-fade-in-up {
            animation: fadeInUp 0.8s ease-out;
          }
          .login-card-sia {
            transition: all 0.3s ease;
            backdrop-filter: blur(10px);
            margin: auto;
          }
          .login-card-sia:hover {
            transform: translateY(-5px);
            box-shadow: 0 20px 40px rgba(0,0,0,0.12) !important;
          }
          .input-group-custom {
            transition: all 0.2s ease;
            border: 2px solid transparent;
            border-radius: 15px;
            background-color: #f8f9fa;
          }
          .input-group-custom:focus-within {
            border-color: #A8867F;
            background-color: #fff;
            box-shadow: 0 0 0 4px rgba(168, 134, 127, 0.1);
          }
          .form-control:focus {
            box-shadow: none;
            background-color: transparent;
          }
          .btn-login {
            background: linear-gradient(45deg, #A8867F 0%, #C4A49D 100%);
            border: none;
            transition: all 0.3s ease;
          }
          .btn-login:hover {
            background: linear-gradient(45deg, #96756D 0%, #B3938C 100%);
            transform: scale(1.02);
            box-shadow: 0 8px 25px rgba(168, 134, 127, 0.4) !important;
          }
          .btn-login:active {
            transform: scale(0.98);
          }
          
          /* Responsive Adjustments */
          @media (max-width: 576px) {
            .login-page-sia {
              padding: 0 !important; /* Remove padding on mobile to let card touch edges */
            }
            .login-card-sia {
              max-width: 100% !important;
              width: 100% !important;
              height: 100vh !important;
              border-radius: 0 !important; /* Full screen look */
              display: flex;
              flex-direction: column;
              border: none !important;
            }
            .login-header-sia {
              padding: 3rem 1.5rem !important;
              flex-shrink: 0;
            }
            .login-form-container {
              padding: 2rem 1.5rem !important;
              flex-grow: 1;
              display: flex;
              flex-direction: column;
              justify-content: center;
              background-color: #fff;
            }
            .logo-container-sia {
              width: 160px !important;
              height: 80px !important;
            }
            h2 {
              font-size: 1.4rem !important;
            }
            .login-page-sia {
              background: #fff !important; /* Simplify background on mobile */
            }
          }
        `}
      </style>

      <div className={`login-card-sia shadow-lg w-100 ${isLoaded ? 'animate-fade-in-up' : ''}`} style={{ 
        maxWidth: '450px', 
        borderRadius: '30px', 
        overflow: 'hidden', 
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        border: '1px solid rgba(255, 255, 255, 0.3)'
      }}>
        
        {/* Header Section */}
        <div className="login-header-sia text-center p-4 p-md-5 position-relative" style={{ 
          background: 'linear-gradient(180deg, #A8867F 0%, #D4B2A7 100%)',
          color: 'white',
        }}>
          {/* Decorative shapes */}
          <div style={{ position: 'absolute', top: '-20px', right: '-20px', width: '100px', height: '100px', borderRadius: '50%', background: 'rgba(255,255,255,0.1)' }}></div>
          <div style={{ position: 'absolute', bottom: '10px', left: '-30px', width: '80px', height: '80px', borderRadius: '50%', background: 'rgba(255,255,255,0.05)' }}></div>

          {/* Oval Logo Section */}
          <div className="mb-4 d-inline-flex align-items-center justify-content-center logo-container-sia" style={{ 
            width: '200px', 
            height: '100px',
            backgroundColor: 'white',
            borderRadius: '100% / 100%', // Creates a perfect oval
            padding: '10px 20px',
            zIndex: 2,
            position: 'relative',
            transition: 'all 0.3s ease',
            boxShadow: '0 8px 16px rgba(0,0,0,0.1)',
            border: '4px solid rgba(255,255,255,0.2)',
            overflow: 'hidden'
          }}>
            <img 
              src={sheEssentialsLogo} 
              alt="Sheessentials" 
              className="img-fluid"
              style={{ 
                width: '100%', 
                height: 'auto', 
                objectFit: 'contain'
              }}
            />
          </div>

          <h2 className="fw-bold mb-1" style={{ fontSize: '1.8rem', letterSpacing: '-0.5px' }}>Welcome Back</h2>
          <p className="mb-0 opacity-80 small text-uppercase fw-semibold" style={{ letterSpacing: '2px', fontSize: '10px' }}>HR Management System</p>
        </div>

        {/* Form Section */}
        <div className="login-form-container p-4 p-md-5">
          {error && (
            <div className="alert alert-danger d-flex align-items-center mb-4 py-3 animate-fade-in-down" style={{ 
              borderRadius: '16px', 
              backgroundColor: '#FFF1F0', 
              border: '1px solid #FFA39E',
              color: '#CF1322',
              fontSize: '14px'
            }}>
              <AlertCircle size={18} className="me-2 flex-shrink-0" />
              <div className="fw-medium">{error}</div>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="mb-4">
              <label className="form-label fw-bold text-muted small text-uppercase mb-2 ps-1" style={{ letterSpacing: '0.8px', fontSize: '11px' }}>Username (Email)</label>
              <div className={`input-group input-group-custom ${username && !username.includes('@') ? 'border-warning' : ''}`}>
                <span className="input-group-text bg-transparent border-0 ps-3 pe-2 text-muted">
                  <User size={18} />
                </span>
                <input 
                  type="text" 
                  className="form-control bg-transparent border-0 p-3" 
                  placeholder="Enter email address"
                  style={{ fontSize: '15px' }}
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                />
              </div>
              {username && !username.includes('@') && (
                <div className="text-warning mt-2 ps-1 animate-fade-in-down" style={{ fontSize: '11px', fontWeight: '500' }}>
                  <AlertCircle size={12} className="me-1" /> Username typically includes '@' (e.g., user@example.com)
                </div>
              )}
            </div>

            <div className="mb-4">
              <label className="form-label fw-bold text-muted small text-uppercase mb-2 ps-1" style={{ letterSpacing: '0.8px', fontSize: '11px' }}>Password</label>
              <div className="input-group input-group-custom">
                <span className="input-group-text bg-transparent border-0 ps-3 pe-2 text-muted">
                  <Lock size={18} />
                </span>
                <input 
                  type={showPassword ? "text" : "password"} 
                  className="form-control bg-transparent border-0 p-3" 
                  placeholder="Enter password"
                  style={{ fontSize: '15px' }}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <button 
                  type="button" 
                  className="btn border-0 text-muted pe-3"
                  onClick={() => setShowPassword(!showPassword)}
                  style={{ boxShadow: 'none' }}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <div className="d-flex justify-content-between align-items-center mb-4 ps-1">
              <div className="form-check custom-checkbox">
                <input 
                  className="form-check-input" 
                  type="checkbox" 
                  id="rememberMe" 
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  style={{ 
                    cursor: 'pointer', 
                    accentColor: '#A8867F',
                    width: '18px',
                    height: '18px'
                  }} 
                />
                <label className="form-check-label small text-muted ms-1" htmlFor="rememberMe" style={{ cursor: 'pointer', userSelect: 'none' }}>
                  Remember me
                </label>
              </div>
              <a href="#" onClick={handleForgotPassword} className="small text-decoration-none fw-bold" style={{ color: '#A8867F', transition: '0.2s' }}>Forgot Password?</a>
            </div>

            <button 
              type="submit" 
              className="btn btn-login w-100 py-3 fw-bold text-uppercase mt-2 text-white" 
              style={{ 
                borderRadius: '15px',
                letterSpacing: '1.5px',
                fontSize: '14px',
                boxShadow: '0 6px 20px rgba(168, 134, 127, 0.3)',
              }}
              disabled={isLoading}
            >
              {isLoading ? (
                <div className="d-flex align-items-center justify-content-center">
                  <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                  <span>Authenticating...</span>
                </div>
              ) : (
                <div className="d-flex align-items-center justify-content-center">
                  <span>Login to Dashboard</span>
                </div>
              )}
            </button>
          </form>

          <div className="text-center mt-5">
            <div className="d-flex align-items-center justify-content-center mb-2 opacity-50">
              <div style={{ height: '1px', width: '30px', backgroundColor: '#000' }}></div>
              <CheckCircle2 size={12} className="mx-2" />
              <div style={{ height: '1px', width: '30px', backgroundColor: '#000' }}></div>
            </div>
            <p className="text-muted mb-0" style={{ fontSize: '11px', opacity: 0.7, letterSpacing: '0.5px' }}>
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

