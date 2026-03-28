import React from 'react';
import { Card } from 'react-bootstrap';

const DepartmentCard = ({ name, count }) => {
  return (
    <Card className="sia-card h-100 border-0 shadow-sm rounded-4 py-3 px-4" style={{ minWidth: '220px' }}>
      <div className="d-flex align-items-center gap-3">
        <div 
          className="rounded-circle d-flex align-items-center justify-content-center fw-bold text-white" 
          style={{ width: '45px', height: '45px', backgroundColor: '#D29191', fontSize: '14px' }}
        >
          {count}
        </div>
        <div>
          <h6 className="m-0 fw-bold" style={{ color: '#5A4343', fontSize: '14px' }}>{name}</h6>
          <small className="text-muted" style={{ fontSize: '11px' }}>Employees</small>
        </div>
      </div>
    </Card>
  );
};

export default DepartmentCard;
