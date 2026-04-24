import React, { useState, useEffect, useRef } from 'react';
import { Form, ListGroup, Badge } from 'react-bootstrap';
import { Search, UserCircle } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import api from '../../api/auth';

const TopBar = ({ title }) => {
  const { setIsProfileOpen } = useAuth();
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState('');
  const [employees, setEmployees] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1); // -1 means no selection
  const searchRef = useRef(null);

  // 1. Fetch employees for the suggestion list
  useEffect(() => {
    const fetchEmployees = async () => {
      try {
        const response = await api.get('/employees/list');
        setEmployees(response.data);
      } catch (err) {
        console.error("Error fetching employees for search:", err);
      }
    };
    fetchEmployees();
  }, []);

  // 2. Handle search input changes
  useEffect(() => {
    if (searchTerm.trim().length > 1) {
      const filtered = employees.filter(emp => 
        `${emp.firstName} ${emp.lastName}`.toLowerCase().includes(searchTerm.toLowerCase()) ||
        emp.employeeId.toLowerCase().includes(searchTerm.toLowerCase())
      ).slice(0, 5); 
      setSuggestions(filtered);
      setShowSuggestions(true);
      setSelectedIndex(-1); // Reset selection when typing
    } else {
      setSuggestions([]);
      setShowSuggestions(false);
      setSelectedIndex(-1);
    }
  }, [searchTerm, employees]);

  // 3. Handle clicks outside to close suggestions
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (searchRef.current && !searchRef.current.contains(event.target)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleKeyDown = (e) => {
    if (!showSuggestions || suggestions.length === 0) {
      if (e.key === 'Enter') {
        executeSearch(searchTerm);
      }
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => (prev < suggestions.length - 1 ? prev + 1 : prev));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => (prev > 0 ? prev - 1 : -1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      // If something is highlighted by arrows, use it. Otherwise, use the first suggestion.
      const targetIndex = selectedIndex >= 0 ? selectedIndex : 0;
      const selectedEmp = suggestions[targetIndex];
      if (selectedEmp) {
        setSearchTerm(`${selectedEmp.firstName} ${selectedEmp.lastName}`);
        executeSearch(`${selectedEmp.firstName} ${selectedEmp.lastName}`);
      }
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
    }
  };

  const executeSearch = (term) => {
    if (term.trim()) {
      const query = term.trim();
      setSearchTerm(''); // Clear the bar immediately
      setShowSuggestions(false);
      setSelectedIndex(-1);
      navigate(`/employee?search=${encodeURIComponent(query)}`);
    }
  };

  return (
    <div className="d-flex justify-content-between align-items-center mb-4">
      <h2 className="fw-bold m-0">{title}</h2>
      
      <div className="position-relative" ref={searchRef}>
        <div className="d-flex align-items-center gap-3 bg-white p-2 rounded-pill shadow-sm px-4">
          <Search size={18} className="text-muted" />
          <Form.Control 
            type="text" 
            placeholder="Search name or ID..." 
            className="border-0 shadow-none" 
            style={{ width: '250px', backgroundColor: 'transparent' }} 
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => searchTerm.trim().length > 1 && setShowSuggestions(true)}
          />
          <div className="border-start ps-3 ms-2">
            <UserCircle 
              size={32} 
              className="text-muted cursor-pointer" 
              onClick={() => setIsProfileOpen(true)}
              style={{ cursor: 'pointer' }}
            />
          </div>
        </div>

        {/* Suggestions Dropdown */}
        {showSuggestions && suggestions.length > 0 && (
          <ListGroup 
            className="position-absolute w-100 mt-2 shadow-lg rounded-4 overflow-hidden border-0" 
            style={{ zIndex: 1000, top: '100%' }}
          >
            {suggestions.map((emp, index) => (
              <ListGroup.Item 
                key={emp.id} 
                action 
                active={index === selectedIndex}
                onClick={() => {
                  setSearchTerm(`${emp.firstName} ${emp.lastName}`);
                  executeSearch(`${emp.firstName} ${emp.lastName}`);
                }}
                className={`d-flex justify-content-between align-items-center py-3 border-0 border-bottom ${index === selectedIndex ? 'bg-light' : ''}`}
                style={{ 
                  backgroundColor: index === selectedIndex ? '#F8F9FA' : 'white',
                  color: 'inherit'
                }}
              >
                <div>
                  <div className="fw-bold" style={{ fontSize: '14px' }}>{emp.firstName} {emp.lastName}</div>
                  <small className="text-muted" style={{ fontSize: '12px' }}>{emp.department}</small>
                </div>
                <Badge bg="light" text="dark" className="rounded-pill border">{emp.employeeId}</Badge>
              </ListGroup.Item>
            ))}
          </ListGroup>
        )}
      </div>
    </div>
  );
};

export default TopBar;
