import React from 'react';
import { Card } from 'react-bootstrap';

const StatCard = ({ title, value, subValue, subLabel, children }) => {
  return (
    <Card className="border-0 shadow-sm p-3 h-100 rounded-4">
      <Card.Body className="p-0">
        <small className="text-muted fw-bold text-uppercase" style={{ fontSize: '11px' }}>{title}</small>
        {children ? (
          <div className="mt-3">{children}</div>
        ) : (
          <div className="d-flex justify-content-between align-items-end mt-3">
            <h2 className="fw-bold m-0">{value}</h2>
            {subValue !== undefined && (
              <div className="text-end">
                <h5 className="m-0 fw-bold">{subValue}</h5>
                <small className="text-muted" style={{ fontSize: '10px' }}>{subLabel}</small>
              </div>
            )}
          </div>
        )}
      </Card.Body>
    </Card>
  );
};

export default StatCard;
