import React from 'react';
import { Form } from 'react-bootstrap';
import { Search, UserCircle } from 'lucide-react';

const TopBar = ({ title }) => {
  return (
    <div className="d-flex justify-content-between align-items-center mb-4">
      <h2 className="fw-bold m-0">{title}</h2>
      
      <div className="d-flex align-items-center gap-3 bg-white p-2 rounded-pill shadow-sm px-4">
        <Search size={18} className="text-muted" />
        <Form.Control 
          type="text" 
          placeholder="Search for anything..." 
          className="border-0 shadow-none" 
          style={{ width: '250px', backgroundColor: 'transparent' }} 
        />
        <div className="border-start ps-3 ms-2">
          <UserCircle size={32} className="text-muted cursor-pointer" />
        </div>
      </div>
    </div>
  );
};

export default TopBar;
