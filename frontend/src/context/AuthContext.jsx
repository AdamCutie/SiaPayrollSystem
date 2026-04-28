import React, { createContext, useContext, useState, useEffect } from 'react';
import { authApi } from '../api/auth';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  useEffect(() => {
    // Check for existing session
    const token = localStorage.getItem('token');
    const role = localStorage.getItem('role');
    const email = localStorage.getItem('email');
    const employee_id = localStorage.getItem('employee_id');
    
    if (token) {
      setUser({ token, role, email, employee_id });
    }
    setLoading(false);
  }, []);

  const login = async (username, password) => {
    try {
      const data = await authApi.login(username, password);
      // Backend returns { access_token, token_type, role, employee_id }
      const session = {
        token: data.access_token,
        role: data.role,
        email: username,
        employee_id: data.employee_id
      };
      
      localStorage.setItem('token', session.token);
      localStorage.setItem('role', session.role);
      localStorage.setItem('email', session.email);
      localStorage.setItem('employee_id', session.employee_id);
      
      setIsProfileOpen(false); // Explicitly ensure profile is closed on fresh login
      setUser(session);
      return session;
    } catch (error) {
      throw error;
    }
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    localStorage.removeItem('email');
    localStorage.removeItem('employee_id');
    setIsProfileOpen(false); // Explicitly close profile on logout
    setUser(null);
  };

  const value = {
    user,
    login,
    logout,
    isAuthenticated: !!user,
    isAdmin: user?.role === 'admin',
    isProfileOpen,
    setIsProfileOpen
  };

  if (loading) {
    return null; 
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
